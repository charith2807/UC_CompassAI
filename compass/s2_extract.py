"""Stage 2 - Extract: turn raw HTML/PDF bytes into clean, structured text.

Reads:  data/raw/manifest.jsonl + data/raw/{doc_id}.html|.pdf  (crawled)
        data/manual_sources.jsonl + data/raw/manual/*.pdf     (downloaded by hand)
Writes: data/normalized/{doc_id}.json
        {doc_id, url, title, kind, fetched_at, sha256, text, pii_redacted,
         page_type, effective_date}
        text is markdown: "#"-headings kept, tables as "| a | b |" rows,
        PDFs get one "## Page N" heading per page.
Run:    python -m compass.s2_extract
"""
import hashlib
import json
import re
from datetime import datetime, timezone

import pymupdf
import trafilatura
from bs4 import BeautifulSoup

from compass import config, pii

MIN_CHARS = 200  # anything shorter is almost certainly a stub or a failed extraction
# A "PDF" that starts with the site's own menu is a saved web page, not a document.
# Two files named "Cooperating Teacher Guide" and "CACREP Vital Statistics" were exactly that.
WEB_PAGE_MARKERS = ("Skip to main content", "Main navigation")


def clean(text: str) -> str:
    text = re.sub(r"<sup>(.*?)</sup>", r"^\1", text)    # footnote markers: $9,875 ^1
    text = re.sub(r"<[^>]+>", "", text)                  # any other leftover tags
    text = re.sub(r"([._])\1{3,}", " ", text)            # TOC dot leaders, blank-form lines
    text = re.sub(r"[ \t]+\n", "\n", text)               # trailing spaces
    text = re.sub(r"\n{3,}", "\n\n", text)               # collapse blank lines
    return text.strip()


def page_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""
    return title.split("|")[0].strip() or "(untitled)"


def unlink_course_lists(html: str) -> str:
    """Program pages list each course as a link to the catalog. Trafilatura treats
    link-heavy blocks as navigation and silently dropped every course list
    (PhD in IT: 16 courses in the HTML, 0 in the text). Replacing those links with
    their plain text keeps the courses; real nav menus still look like nav."""
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=re.compile(r"catalog\.ucumberlands\.edu/preview_")):
        a.unwrap()
    return str(soup)


def extract_html(raw: bytes) -> tuple[str, str]:
    html = unlink_course_lists(raw.decode("utf-8", errors="ignore"))
    # Trafilatura finds the main content block and drops nav menus, footers and
    # cookie banners - the "boilerplate" that would otherwise be in every chunk.
    text = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_images=False,
        favor_recall=True,  # prefer keeping a bit of noise over losing content
    ) or ""
    return page_title(html), clean(text)


# Calendars print each date on its own line with the event on the next line.
# Flattened, "Monday, August 24, 2026 / Classes Begin / Tuesday, September 1, 2026 /
# Last Day to Register" let the LLM pair Sept 1 with "Classes Begin". Join each date
# with the line below it so the pair can never be separated.
DATE_LINE = re.compile(
    r"^\s*(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+[A-Za-z]+,?\s+\d{1,2}(\s*-\s*\d{1,2})?,?\s+\d{4}\s*$")


def join_date_lines(text: str) -> str:
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if DATE_LINE.match(lines[i]) and nxt and not DATE_LINE.match(nxt):
            out.append(f"{lines[i].strip()}: {nxt}")
            i += 2
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def extract_pdf(raw: bytes, url: str) -> tuple[str, str]:
    # Embedded PDF titles are unreliable (these say "Home | University of the
    # Cumberlands"), so the file name is used instead.
    title = url.rsplit("/", 1)[-1].removesuffix(".pdf").replace("-", " ").replace("_", " ")
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        pages = [f"## Page {i}\n\n{join_date_lines(page.get_text('text'))}" for i, page in enumerate(pdf, start=1)]
    return title, clean("\n\n".join(pages))


PAGE_TYPES = [  # first match wins; used for metadata filtering ("only search financial pages")
    ("calendar", lambda u, t: "academic calendar" in t),
    ("policy", lambda u, t: any(w in t for w in ("handbook", "policy", "title ix", "complaint", "hazing", "consent", "accessibility"))),
    ("program", lambda u, t: re.search(r"/academics/(undergraduate|graduate|executive|certificate)/", u)),
    ("financial", lambda u, t: re.search(r"/(tuition-aid|admission-aid/financial|student-financial-center|sfc)", u)),
    ("admissions", lambda u, t: re.search(r"/(admissions|admission-aid)", u) or "kctcs" in t),
    ("student-life", lambda u, t: "/student-life" in u or "what to bring" in t),
    ("about", lambda u, t: re.search(r"/(about|privacy-policy)", u)),
]


def page_type(url: str, title: str) -> str:
    return next((name for name, rule in PAGE_TYPES if rule(url, title.lower())), "general")


def effective_date(title: str, text: str) -> str | None:
    """Best-effort "which period does this page describe?" so answers can show content
    age (a 2025-26 cost table cited in 2026-27 looks verified but is stale)."""
    head = f"{title}\n{text[:3000]}"
    for pattern in (r"\b(20\d\d)\s*[-–]\s*(20)?(\d\d)\b(?=\s*(academic|year|catalog|student handbook|$))",
                    r"\b(Fall|Spring|Summer) (20\d\d)\b",
                    r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (20\d\d)\b",
                    r"[Rr]evised:? (\d{1,2}/\d{1,2}/(20)?\d\d)"):
        m = re.search(pattern, head, re.IGNORECASE | re.MULTILINE)
        if m:
            if m.lastindex and m.lastindex >= 3 and m.group(3) and m.group(1).isdigit():
                return f"{m.group(1)}-20{m.group(3)}"
            return m.group(0).replace("Revised", "revised").strip()
    return None


def manual_records() -> list[dict]:
    """Hand-downloaded PDFs, described like crawl-manifest rows so the rest of the
    pipeline can't tell the difference. The URL is what answers will cite."""
    if not config.MANUAL_SOURCES.exists():
        return []
    records = []
    for src in map(json.loads, open(config.MANUAL_SOURCES)):
        path = config.MANUAL_DIR / src["file"]
        if not path.exists():
            print(f"  ! listed in manual_sources but missing: {path.name}")
            continue
        raw = path.read_bytes()
        records.append({
            "doc_id": hashlib.sha1(src["url"].encode("utf-8")).hexdigest()[:12],  # same rule as stage 1
            "url": src["url"], "kind": "pdf", "title": src["title"],
            "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(raw).hexdigest(), "path": str(path.relative_to(config.ROOT)),
        })
    return records


def main() -> None:
    config.NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    for old in config.NORMALIZED_DIR.glob("*.json"):  # dropped documents must not linger
        old.unlink()
    records = [json.loads(line) for line in open(config.MANIFEST)] + manual_records()
    kept, dropped = 0, []
    for r in records:
        raw = (config.ROOT / r["path"]).read_bytes()
        if r["kind"] == "pdf":
            title, text = extract_pdf(raw, r["url"])
            title = r.get("title", title)
        else:
            title, text = extract_html(raw)

        if r["kind"] == "pdf" and all(m in text[:3000] for m in WEB_PAGE_MARKERS):
            dropped.append((r["url"], "saved web page, not a document"))
            continue
        if len(text) < MIN_CHARS:
            dropped.append((r["url"], f"only {len(text)} chars"))
            continue
        # Personal identifiers are redacted; official university contacts are kept (compass/pii.py).
        text, pii_found = pii.redact(text, pii.CORPUS_KINDS)
        doc = {k: r[k] for k in ("doc_id", "url", "kind", "fetched_at", "sha256")}
        doc.update(title=title, text=text, pii_redacted=pii_found,
                   page_type=page_type(r["url"], title), effective_date=effective_date(title, text))
        (config.NORMALIZED_DIR / f"{r['doc_id']}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        kept += 1
        print(f"  {r['kind']:4} {len(text):>7,} chars  {title[:60]}")

    print(f"\nnormalized {kept}/{len(records)} documents -> {config.NORMALIZED_DIR.relative_to(config.ROOT)}/")
    for url, reason in dropped:
        print(f"  dropped ({reason}): {url}")


if __name__ == "__main__":
    main()
