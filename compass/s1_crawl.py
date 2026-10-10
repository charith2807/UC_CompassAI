"""Stage 1 - Crawl: politely download public, student-facing pages and PDFs.

Reads:  the live sitemap.xml (+ config.EXTRA_SEEDS)
Writes: data/raw/{doc_id}.html | .pdf
        data/raw/manifest.jsonl   (one JSON line per fetched document)
Run:    python -m compass.s1_crawl --max-pages 30
"""
import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from compass import config


def doc_id_for(url: str) -> str:
    """Deterministic ID: the same URL always gets the same ID across re-crawls."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


# What the sitemap contains (2,122 URLs, by first path segment):
#   712 /directory (staff profiles: PII), 508 /news, 494 /blog, 113 /stories
#   165 /academics, 50 /student-life, 18 /admissions, 12 /tuition-aid, 6 /admission-aid
# An allow-list is safer than a block-list: new or surprising sections stay
# out until someone opts them in.
ALLOWED_SECTIONS = {
    "(home)", "about", "academics", "admissions", "admission-aid", "tuition-aid",
    "student-life", "current-students", "prospective-students", "parents",
    "privacy-policy", "graduate-education-resources",
}
BLOCKED_WORDS = ("login", "directory", "faculty-staff")  # PII or auth


def is_in_scope(url: str) -> bool:
    """Decide whether a URL belongs in the student-information corpus."""
    parsed = urlparse(url)
    host, path = parsed.netloc.lower(), parsed.path.lower()
    if parsed.scheme != "https" or not (host == "ucumberlands.edu" or host.endswith(".ucumberlands.edu")):
        return False
    if any(word in path for word in BLOCKED_WORDS):
        return False
    if path.endswith(".pdf"):
        return True  # PDFs live under /sites/default/files/..., not a section path
    return host == "www.ucumberlands.edu" and section_of(url) in ALLOWED_SECTIONS


def section_of(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[0] if path else "(home)"


def interleave_by_section(urls: list[str]) -> list[str]:
    """Round-robin across sections so a small crawl samples every section
    instead of taking the first 30 /academics pages."""
    groups = defaultdict(list)
    for url in urls:
        groups[section_of(url)].append(url)
    ordered = []
    while any(groups.values()):
        for section in sorted(groups):
            if groups[section]:
                ordered.append(groups[section].pop(0))
    return ordered


def normalize_url(url: str) -> str:
    """Drop #fragments and trailing slashes so one page has exactly one URL."""
    url, _ = urldefrag(url)
    return url.rstrip("/") if urlparse(url).path not in ("", "/") else url


class PoliteSession:
    """requests.Session that obeys robots.txt (per host) and waits between requests."""

    def __init__(self):
        self.http = requests.Session()
        self.http.headers["User-Agent"] = config.USER_AGENT
        self.robots = {}

    def allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self.robots:
            rp = RobotFileParser(f"https://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None  # unreachable robots.txt -> be conservative below
            self.robots[host] = rp
        rp = self.robots[host]
        return rp is not None and rp.can_fetch(config.USER_AGENT, url)

    def get(self, url: str):
        time.sleep(config.REQUEST_DELAY_SECONDS)  # never more than 1 request/second
        try:
            return self.http.get(url, timeout=20)
        except requests.RequestException as e:
            print(f"  ! error {url}: {e}")
            return None


def sitemap_urls(session: PoliteSession) -> list[str]:
    resp = session.get(config.SITEMAP_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "xml")
    return [normalize_url(loc.text.strip()) for loc in soup.find_all("loc")]


def pdf_links(html: bytes, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        url = normalize_url(urljoin(base_url, a["href"]))
        if urlparse(url).path.lower().endswith(".pdf"):
            links.append(url)
    return links


def save(resp, url: str, kind: str) -> dict:
    doc_id = doc_id_for(url)
    path = config.RAW_DIR / f"{doc_id}.{kind}"
    path.write_bytes(resp.content)
    return {
        "doc_id": doc_id,
        "url": url,
        "final_url": normalize_url(resp.url),
        "kind": kind,
        "section": section_of(url),
        "bytes": len(resp.content),
        "sha256": hashlib.sha256(resp.content).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": str(path.relative_to(config.ROOT)),
    }


def crawl(max_pages: int, max_pdfs: int) -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = PoliteSession()
    skipped = Counter()

    all_urls = sitemap_urls(session) + [normalize_url(u) for u in config.EXTRA_SEEDS]
    candidates = interleave_by_section([u for u in dict.fromkeys(all_urls) if is_in_scope(u)])
    print(f"sitemap+seeds: {len(all_urls)} URLs, in scope: {len(candidates)}")

    records, pdf_queue, seen_hashes = [], [], set()
    pages = pdfs = 0
    queue = list(candidates)
    while queue:
        url = queue.pop(0)
        is_pdf_url = urlparse(url).path.lower().endswith(".pdf")
        if (is_pdf_url and pdfs >= max_pdfs) or (not is_pdf_url and pages >= max_pages):
            continue
        if not session.allowed(url):
            skipped["robots.txt"] += 1
            continue
        resp = session.get(url)
        if resp is None or resp.status_code != 200:
            skipped[f"http {getattr(resp, 'status_code', 'error')}"] += 1
            continue
        if not is_in_scope(normalize_url(resp.url)):
            skipped["redirected out of scope"] += 1
            continue

        ctype = resp.headers.get("Content-Type", "")
        kind = "pdf" if "application/pdf" in ctype else "html" if "text/html" in ctype else None
        if kind is None:
            skipped[f"type {ctype.split(';')[0]}"] += 1
            continue
        content_hash = hashlib.sha256(resp.content).hexdigest()
        if content_hash in seen_hashes:
            skipped["duplicate content"] += 1
            continue
        seen_hashes.add(content_hash)

        records.append(save(resp, url, kind))
        if kind == "pdf":
            pdfs += 1
        else:
            pages += 1
            for link in pdf_links(resp.content, resp.url):
                if link not in pdf_queue and link not in candidates and is_in_scope(link):
                    pdf_queue.append(link)
                    queue.append(link)
        print(f"  [{pages:>3} html | {pdfs:>2} pdf] {kind:4} {url}")

    with open(config.MANIFEST, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"\nsaved {len(records)} documents ({pages} html, {pdfs} pdf) -> {config.MANIFEST.relative_to(config.ROOT)}")
    print(f"PDF links discovered on pages: {len(pdf_queue)}")
    print("by section:", dict(Counter(r["section"] for r in records).most_common()))
    print("skipped:", dict(skipped) or "none")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-pdfs", type=int, default=10)
    args = parser.parse_args()
    crawl(args.max_pages, args.max_pdfs)
