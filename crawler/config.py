"""Shared crawler configuration. Edit the contact e-mail before running."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"                 # git-ignored
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
CRAWL_LOG = DATA / "crawl_log.csv"
SEED_DECISIONS = DATA / "seed_decisions.csv"
EXTRACT_LOG = DATA / "extract_log.csv"

import os

# Set a shared team mailbox via the CRAWLER_CONTACT env var (no personal names in code).
CONTACT = os.environ.get("CRAWLER_CONTACT", "msai633-compass-team@users.noreply.invalid")
USER_AGENT = (
    "CumberlandsCompassBot/0.1 (MSAI-633 class project, University of the "
    f"Cumberlands; research use only; contact: {CONTACT})"
)

SITE = "https://www.ucumberlands.edu"
SITEMAP_URL = f"{SITE}/sitemap.xml"
ALLOWED_HOST_SUFFIX = "ucumberlands.edu"

MIN_DELAY_SECONDS = 1.0        # hard floor: at most 1 request / second
MAX_ACCEPTED_CRAWL_DELAY = 10  # hosts demanding a longer delay are skipped
REQUEST_TIMEOUT = 20
MAX_BYTES = 25 * 1024 * 1024

MAX_HTML_PAGES = 170
MAX_PDFS = 25

# Public PDFs named in the project proposal that are not linked from crawled pages.
EXTRA_PDF_SEEDS = [
    "https://www.ucumberlands.edu/sites/default/files/downloads/VisitorsGuide.pdf",
]

# Top-level site sections that are in scope (student-facing information).
INCLUDE_SECTIONS = {
    "admissions", "admission-aid", "tuition-aid", "academics", "student-life",
    "about", "prospective-students", "parents", "current-students",
    "privacy-policy", "questions", "patriotsvip", "emergency-notification-system",
    "graduate-education-resources", "certification-and-reciprocity-education-programs",
    "option-9-education-certification-pathways", "department-institutional-research",
}

# Sections excluded on purpose (reason is written to the log).
EXCLUDE_SECTIONS = {
    "directory": "personal data: staff/faculty directory",
    "faculty-staff": "personal data: staff/faculty pages",
    "uclogin": "login page",
    "user": "login / account page",
    "node": "internal CMS path",
    "news": "out of scope: news archive (stale)",
    "blog": "out of scope: blog archive",
    "stories": "out of scope: stories archive",
    "alumni": "out of scope: alumni",
    "events": "out of scope: events listing",
    "classof2026": "out of scope",
    "connection": "out of scope",
    "communications-marketing": "out of scope",
}

# Pages containing these words are crawled first (core topics of the chatbot).
PRIORITY_WORDS = (
    "tuition", "cost", "financial", "aid", "scholarship", "admission", "apply",
    "calendar", "registrar", "catalog", "commencement", "policy", "policies",
    "student-services", "transfer", "international", "deadline", "billing",
    "bursar", "handbook", "guide", "graduation",
)
