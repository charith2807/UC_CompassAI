"""Polite, robots.txt-aware crawler for ucumberlands.edu.

Usage:  python -m crawler.crawl [--dry-run]

Ethics rules enforced in code:
  * robots.txt is read per host and honoured (incl. wildcard rules).
  * at most 1 request per second globally (more if a host sets a crawl-delay;
    hosts asking for > MAX_ACCEPTED_CRAWL_DELAY seconds are skipped and logged).
  * descriptive User-Agent with contact address.
  * only public, unauthenticated pages; login / directory / personal-data
    sections are excluded before any request is made.
  * every decision (fetched / skipped / error) goes to data/crawl_log.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.robotparser as robotparser
from datetime import datetime, timezone
from urllib.parse import urldefrag, urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from . import config as C

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": C.USER_AGENT})

_last_request = 0.0
_robots: dict[str, "HostRules"] = {}


# --------------------------------------------------------------------------- #
# logging
# --------------------------------------------------------------------------- #
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(url: str, action: str, status, reason: str = "") -> None:
    new = not C.CRAWL_LOG.exists()
    with C.CRAWL_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp_utc", "url", "action", "http_status", "reason"])
        w.writerow([now(), url, action, status, reason])


# --------------------------------------------------------------------------- #
# polite fetching
# --------------------------------------------------------------------------- #
def throttle(extra_delay: float = 0.0) -> None:
    global _last_request
    wait = max(C.MIN_DELAY_SECONDS, extra_delay) - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def polite_get(url: str, delay: float = 0.0, stream: bool = False) -> requests.Response:
    throttle(delay)
    return SESSION.get(url, timeout=C.REQUEST_TIMEOUT, stream=stream, allow_redirects=True)


class HostRules:
    """robots.txt for one host (stdlib parser + own wildcard handling)."""

    def __init__(self, host: str):
        self.host = host
        self.parser = robotparser.RobotFileParser()
        self.wildcards: list[re.Pattern] = []
        self.allow_all = False
        self.deny_all = False
        self.crawl_delay = 0.0
        self._load()

    def _load(self) -> None:
        url = f"https://{self.host}/robots.txt"
        try:
            r = polite_get(url)
        except requests.RequestException as e:
            self.deny_all = True
            log(url, "robots", "ERR", f"unreachable, treating as disallow-all: {e}")
            return
        log(url, "robots", r.status_code, "fetched robots.txt")
        if r.status_code == 404:
            self.allow_all = True
            return
        if r.status_code != 200:
            self.deny_all = True
            return
        lines = r.text.splitlines()
        self.parser.parse(lines)
        d = self.parser.crawl_delay(C.USER_AGENT) or self.parser.crawl_delay("*")
        self.crawl_delay = float(d or 0)
        # stdlib treats '*' literally inside paths; add regexes for those rules.
        group = False
        for line in lines:
            line = line.split("#")[0].strip()
            if not line or ":" not in line:
                continue
            k, v = [x.strip() for x in line.split(":", 1)]
            if k.lower() == "user-agent":
                group = v == "*"
            elif group and k.lower() == "disallow" and "*" in v:
                pat = re.escape(v).replace(r"\*", ".*")
                self.wildcards.append(re.compile("^" + pat))

    def allowed(self, url: str) -> bool:
        if self.deny_all:
            return False
        if self.allow_all:
            return True
        path = urlparse(url).path or "/"
        if any(p.match(path) for p in self.wildcards):
            return False
        return self.parser.can_fetch(C.USER_AGENT, url)


def rules_for(url: str) -> HostRules:
    host = urlparse(url).netloc.lower()
    if host not in _robots:
        _robots[host] = HostRules(host)
    return _robots[host]


def host_ok(url: str) -> tuple[bool, str]:
    host = urlparse(url).netloc.lower()
    if not (host == C.ALLOWED_HOST_SUFFIX or host.endswith("." + C.ALLOWED_HOST_SUFFIX)):
        return False, "off-domain"
    rules = rules_for(url)
    if rules.crawl_delay > C.MAX_ACCEPTED_CRAWL_DELAY:
        return False, f"host crawl-delay {rules.crawl_delay:.0f}s too long; skipped"
    if not rules.allowed(url):
        return False, "disallowed by robots.txt"
    return True, ""


# --------------------------------------------------------------------------- #
# seed selection
# --------------------------------------------------------------------------- #
def load_sitemap() -> list[str]:
    r = polite_get(C.SITEMAP_URL)
    log(C.SITEMAP_URL, "sitemap", r.status_code, "fetched")
    r.raise_for_status()
    root = ElementTree.fromstring(r.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text.strip() for e in root.findall(".//s:loc", ns) if e.text]
    # sitemap index -> follow children
    if root.tag.endswith("sitemapindex"):
        out: list[str] = []
        for child in locs:
            rr = polite_get(child)
            log(child, "sitemap", rr.status_code, "child sitemap")
            if rr.ok:
                sub = ElementTree.fromstring(rr.content)
                out += [e.text.strip() for e in sub.findall(".//s:loc", ns) if e.text]
        return out
    return locs


def classify(url: str) -> tuple[bool, str]:
    parts = [p for p in urlparse(url).path.split("/") if p]
    section = parts[0] if parts else "(home)"
    if section in C.EXCLUDE_SECTIONS:
        return False, C.EXCLUDE_SECTIONS[section]
    if section == "(home)":
        return True, "homepage"
    if section in C.INCLUDE_SECTIONS:
        return True, f"in-scope section: {section}"
    return False, f"out of scope: section '{section}'"


def priority(url: str) -> tuple[int, int]:
    u = url.lower()
    hit = any(w in u for w in C.PRIORITY_WORDS)
    depth = len([p for p in urlparse(u).path.split("/") if p])
    return (0 if hit else 1, depth)       # core topics first, shallow pages first


def build_seeds(urls: list[str]) -> list[str]:
    decisions, keep = [], []
    for u in sorted(set(urls)):
        ok, why = classify(u)
        decisions.append((u, "include" if ok else "exclude", why))
        if ok:
            keep.append(u)
    with C.SEED_DECISIONS.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["url", "decision", "reason"])
        w.writerows(decisions)
    keep.sort(key=priority)
    return keep


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #
def doc_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def meta_path(did: str):
    return C.RAW / f"{did}.meta.json"


def save(url: str, resp: requests.Response, body: bytes, ctype: str) -> dict:
    did = doc_id(url)
    ext = "pdf" if "pdf" in ctype else "html"
    (C.RAW / f"{did}.{ext}").write_bytes(body)
    meta = {
        "doc_id": did,
        "url": url,
        "final_url": resp.url,
        "http_status": resp.status_code,
        "crawled_at": now(),
        "content_type": ctype,
        "content_hash": hashlib.sha256(body).hexdigest(),
        "last_modified": resp.headers.get("Last-Modified", ""),
        "etag": resp.headers.get("ETag", ""),
        "raw_file": f"{did}.{ext}",
        "bytes": len(body),
    }
    meta_path(did).write_text(json.dumps(meta, indent=2))
    return meta


def fetch(url: str, kind: str) -> dict | None:
    """Fetch one URL politely. Returns meta dict or None."""
    ok, why = host_ok(url)
    if not ok:
        log(url, "skipped", "", why)
        return None
    did = doc_id(url)
    if meta_path(did).exists():                      # resume support
        log(url, "cached", "", "already downloaded")
        return json.loads(meta_path(did).read_text())
    try:
        resp = polite_get(url, delay=rules_for(url).crawl_delay, stream=True)
    except requests.RequestException as e:
        log(url, "error", "ERR", str(e))
        return None
    final_ok, why = host_ok(resp.url)               # redirect target must also be allowed
    if not final_ok:
        log(url, "skipped", resp.status_code, f"redirected to {resp.url}: {why}")
        resp.close()
        return None
    if "login" in urlparse(resp.url).path.lower():
        log(url, "skipped", resp.status_code, f"redirected to login page {resp.url}")
        resp.close()
        return None
    if resp.status_code != 200:
        log(url, "skipped", resp.status_code, "non-200 response")
        resp.close()
        return None
    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    wanted = ("application/pdf",) if kind == "pdf" else ("text/html", "application/xhtml+xml")
    if ctype not in wanted:
        log(url, "skipped", resp.status_code, f"unsupported content-type {ctype}")
        resp.close()
        return None
    body = b""
    for chunk in resp.iter_content(65536):
        body += chunk
        if len(body) > C.MAX_BYTES:
            log(url, "skipped", resp.status_code, "file too large")
            resp.close()
            return None
    meta = save(url, resp, body, ctype)
    log(url, "fetched", resp.status_code, f"{ctype} {len(body)} bytes")
    return meta


# --------------------------------------------------------------------------- #
# PDF discovery
# --------------------------------------------------------------------------- #
def pdf_links(meta: dict) -> list[str]:
    html = (C.RAW / meta["raw_file"]).read_bytes()
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        href = urldefrag(urljoin(meta["final_url"], a["href"]))[0]
        if urlparse(href).path.lower().endswith(".pdf"):
            out.append(href)
    return out


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="only build seed list")
    args = ap.parse_args()

    C.RAW.mkdir(parents=True, exist_ok=True)
    C.PROCESSED.mkdir(parents=True, exist_ok=True)

    host_ok(C.SITE)                                   # loads main robots.txt
    urls = load_sitemap()
    seeds = build_seeds(urls)
    inc = len(seeds)
    print(f"sitemap URLs: {len(urls)} | in scope: {inc} | excluded: {len(set(urls)) - inc}")
    if args.dry_run:
        return

    pdfs: dict[str, str] = {}                         # pdf url -> page it was found on
    for p in C.EXTRA_PDF_SEEDS:
        pdfs.setdefault(p, "manual seed (public document named in proposal)")
    fetched = 0
    overflow: list[str] = []
    for url in seeds:
        if fetched >= C.MAX_HTML_PAGES:
            overflow.append(url)
            continue
        meta = fetch(url, "html")
        if not meta:
            continue
        fetched += 1
        for p in pdf_links(meta):
            pdfs.setdefault(p, url)
        if fetched % 20 == 0:
            print(f"  html pages: {fetched}")

    # Pages beyond the corpus budget are only scanned for links to public PDFs
    # (nothing is stored), so the 5-PDF minimum is not missed by page ordering.
    for url in overflow:
        ok, why = host_ok(url)
        if not ok:
            log(url, "skipped", "", why)
            continue
        try:
            r = polite_get(url, delay=rules_for(url).crawl_delay)
        except requests.RequestException as e:
            log(url, "error", "ERR", str(e))
            continue
        log(url, "link-scan", r.status_code, "scanned for PDF links only; not stored")
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
            continue
        soup = BeautifulSoup(r.content, "lxml")
        for a in soup.find_all("a", href=True):
            href = urldefrag(urljoin(r.url, a["href"]))[0]
            if urlparse(href).path.lower().endswith(".pdf"):
                pdfs.setdefault(href, url)

    print(f"html pages: {fetched} | candidate PDFs found: {len(pdfs)}")
    got = 0
    for p, src in sorted(pdfs.items(), key=lambda kv: priority(kv[0])):
        if got >= C.MAX_PDFS:
            log(p, "skipped", "", "pdf budget reached")
            continue
        if fetch(p, "pdf"):
            got += 1
    print(f"pdfs downloaded: {got}")
    (C.DATA / "pdf_sources.json").write_text(json.dumps(pdfs, indent=2))


if __name__ == "__main__":
    main()
