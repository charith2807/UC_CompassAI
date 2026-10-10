"""Turn raw HTML/PDF into one normalized JSON file per document.

Usage:  python -m crawler.extract

Output (data/processed/<doc_id>.json):
  doc_id, url, title, source_type, crawled_at, content_hash, last_modified,
  headings, text (markdown, headings/tables kept), tables, pii
Chunking reads these files, so nothing needs to be re-crawled.

Privacy filter:
  * SSN-like pattern            -> document dropped
  * > MAX_EMAILS distinct e-mails -> dropped (directory-like)
  * phone numbers are institutional office lines: kept, counted in the report
  * personal-looking e-mails    -> redacted; office/role mailboxes are kept
  * near-empty or duplicate text -> dropped
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from datetime import date
from urllib.parse import urlparse

import pandas as pd
import pymupdf
import trafilatura
from bs4 import BeautifulSoup

from . import config as C

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
ROLE_MAILBOX = re.compile(
    r"^(admission|admissions|apply|financial|finaid|fin-?aid|aid|registrar|bursar|"
    r"billing|info|information|help|helpdesk|support|service|services|enroll|"
    r"enrollment|advising|advisor|academic|student|students|studentlife|"
    r"housing|athletics|career|careers|library|it|international|transfer|"
    r"graduate|undergraduate|online|office|communications|events|veterans|"
    r"disability|accessibility|title\s?ix|compliance|counseling|health|"
    r"commencement|graduation|transcripts?|records|scholarships?|"
    r"[a-z]*(admissions|office|services|support|desk|team|dept|department))$",
    re.I,
)
MAX_EMAILS = 5
MIN_CHARS = 200


def clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return re.sub(r"\s*[|\-–—]\s*University of the Cumberlands\s*$", "", t, flags=re.I)


def md_table(df: pd.DataFrame) -> str:
    df = df.fillna("").astype(str)
    return df.to_markdown(index=False)


def heading_paths(headings: list[dict]) -> list[list[str]]:
    stack = []
    paths = []
    for heading in headings:
        while stack and stack[-1][0] >= heading['level']:
            stack.pop()
        stack.append((heading['level'], heading['text']))
        paths.append([text for _, text in stack])
    return paths


def effective_date(text: str) -> str | None:
    # Accept explicitly labelled ISO dates only; crawl/modified dates are not effective dates.
    match = re.search(r'\beffective(?:\s+date)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})\b', text, re.I)
    if match:
        try:
            return date.fromisoformat(match.group(1)).isoformat()
        except ValueError:
            pass
    return None


def page_type(url: str, source_type: str) -> str:
    path = urlparse(url).path.lower()
    for category, terms in [('calendar', ('calendar',)), ('tuition_financial_aid', ('tuition', 'financial', 'cost', 'scholarship')),
                            ('admissions', ('admission', 'apply')), ('policy', ('policy', 'policies', 'consent')),
                            ('academic_program', ('program',)), ('student_services', ('student-life', 'services', 'registrar'))]:
        if any(term in path for term in terms):
            return category
    return 'document' if source_type == 'pdf' else 'general'


# --------------------------------------------------------------------------- #
def extract_html(raw: bytes, url: str) -> dict:
    html = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    # footnote markers like "$9,875<sup>1</sup>" would otherwise become "$9,8751"
    for sup in soup.find_all("sup"):
        sup.decompose()
    html = str(soup)
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"]
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""

    content = soup.find('main') or soup.find('article') or soup
    for unwanted in content.select('nav, footer, script, style, [role="navigation"]'):
        unwanted.decompose()
    headings = [
        {"level": int(h.name[1]), "text": h.get_text(" ", strip=True)}
        for h in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        if h.get_text(strip=True)
    ]

    text = trafilatura.extract(
        html, url=url, output_format="markdown", include_tables=True,
        include_links=False, include_comments=False, favor_recall=True,
    ) or ""

    tables: list[str] = []
    try:
        for df in pd.read_html(io.StringIO(html), flavor="lxml"):
            if df.shape[0] >= 2 and df.shape[1] >= 2:
                tables.append(md_table(df))
    except ValueError:
        pass                                          # no tables on page
    # trafilatura sometimes drops tables; append them so cost data is never lost
    if tables and text.count("|") < 6:
        text += "\n\n## Tables\n\n" + "\n\n".join(tables)

    return {"title": clean_title(title), "headings": headings, "text": text.strip(),
            "tables": tables, "source_type": "html"}


def extract_pdf(raw: bytes, url: str) -> dict:
    doc = pymupdf.open(stream=raw, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, 1):
        t = page.get_text("text").strip()
        if t:
            pages.append(f"[page {i}]\n{t}")
    title = (doc.metadata or {}).get("title", "").strip()
    if not title or len(title) < 4:
        first = next((l.strip() for p in pages for l in p.splitlines()[1:] if len(l.strip()) > 3), "")
        title = first[:120] or urlparse(url).path.rsplit("/", 1)[-1]
    return {"title": clean_title(title), "headings": [], "text": "\n\n".join(pages),
            "tables": [], "source_type": "pdf", "pages": doc.page_count}


# --------------------------------------------------------------------------- #
def privacy_filter(text: str) -> tuple[str | None, dict, str]:
    """Return (clean_text or None if dropped, report, drop_reason)."""
    emails = set(m.lower() for m in EMAIL.findall(text))
    phones = set(PHONE.findall(text))
    report = {"emails_found": len(emails), "phones_found": len(phones),
              "emails_redacted": 0, "ssn_like": len(SSN.findall(text))}
    if report["ssn_like"]:
        return None, report, "SSN-like pattern"
    if len(emails) > MAX_EMAILS:
        return None, report, f">{MAX_EMAILS} e-mail addresses (directory-like)"

    def repl(m: re.Match) -> str:
        local = m.group(0).split("@")[0]
        if ROLE_MAILBOX.match(local):
            return m.group(0)
        report["emails_redacted"] += 1
        return "[REDACTED_EMAIL]"

    return EMAIL.sub(repl, text), report, ""


def main(raw_dir: Path | None = None) -> None:
    raw_dir = raw_dir or C.RAW
    metadata = sorted(raw_dir.glob('*.meta.json'))
    if not metadata:
        raise SystemExit(f'No raw metadata found in {raw_dir}; existing output was preserved.')
    for mp in metadata:
        meta = json.loads(mp.read_text())
        if not (raw_dir / meta['raw_file']).is_file():
            raise SystemExit(f'Missing raw file for {mp}; existing output was preserved.')
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    for old in C.PROCESSED.glob("*.json"):
        old.unlink()                                  # reproducible rebuild
    seen_hash: dict[str, str] = {}
    rows = []
    for mp in metadata:
        meta = json.loads(mp.read_text())
        raw = (raw_dir / meta["raw_file"]).read_bytes()
        try:
            d = (extract_pdf if meta["raw_file"].endswith(".pdf") else extract_html)(raw, meta["final_url"])
        except Exception as e:                        # keep going; log the failure
            rows.append([meta["doc_id"], meta["url"], "error", str(e), 0, 0, 0, 0])
            continue

        # Apply the same privacy checks to every extracted field, including tables.
        fields = [d['text'], d['title']] + [h['text'] for h in d['headings']] + d['tables']
        _, pii, why = privacy_filter('\n'.join(fields))
        cleaned = [privacy_filter(value)[0] for value in fields] if not why else []
        text = cleaned[0] if cleaned else None
        if cleaned:
            d['title'] = cleaned[1]
            count = len(d['headings'])
            for heading, value in zip(d['headings'], cleaned[2:2 + count]):
                heading['text'] = value
            d['tables'] = cleaned[2 + count:]
        status, reason = "kept", ""
        if text is None:
            status, reason = "dropped", why
        elif len(text) < MIN_CHARS:
            status, reason = "dropped", "too little text"
        else:
            h = hashlib.sha256(text.encode()).hexdigest()
            if h in seen_hash:
                status, reason = "dropped", f"duplicate of {seen_hash[h]}"
            else:
                seen_hash[h] = meta["doc_id"]
        if status == "kept":
            out = {
                "doc_id": meta["doc_id"], "url": meta["final_url"], "title": d["title"],
                "source_type": d["source_type"], "crawled_at": meta["crawled_at"],
                "last_modified": meta["last_modified"], "content_hash": meta["content_hash"],
                "headings": d["headings"], "tables": d["tables"], "pii": pii, "text": text,
                "source_url": meta["final_url"],
                "page_type": page_type(meta['final_url'], d['source_type']),
                "effective_date": effective_date(text),
                "heading_path": heading_paths(d['headings']),
                "normalized_content_hash": h,
            }
            if "pages" in d:
                out["pages"] = d["pages"]
            for field in ('acquisition_method', 'timestamp_basis', 'robots_verified'):
                if field in meta:
                    out[field] = meta[field]
            (C.PROCESSED / f"{meta['doc_id']}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2))
        rows.append([meta["doc_id"], meta["url"], status, reason, len(text or ""),
                     len(d["tables"]), pii["emails_redacted"], pii["phones_found"]])

    with C.EXTRACT_LOG.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "url", "status", "reason", "chars", "tables",
                    "emails_redacted", "phones_found"])
        w.writerows(rows)
    kept = sum(r[2] == "kept" for r in rows)
    print(f"documents: {len(rows)} | kept: {kept} | dropped/errors: {len(rows) - kept}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=C.RAW)
    main(parser.parse_args().raw_dir)
