"""Crawl-scope checks for stage 1: personal-data and login pages must never be
fetched, and student-facing pages must be.

Run:  python -m tests.test_crawl_scope
"""
from compass.s1_crawl import doc_id_for, is_in_scope, normalize_url


def test_scope_excludes_personal_and_login_pages():
    for url in ("https://www.ucumberlands.edu/directory/jane-smith",
                "https://www.ucumberlands.edu/uclogin",
                "https://www.ucumberlands.edu/faculty-staff/teaching-resources",
                "https://www.ucumberlands.edu/news/some-story",
                "http://www.ucumberlands.edu/tuition-aid/tuition",          # not https
                "https://www.example.com/tuition-aid/tuition"):             # other site
        assert not is_in_scope(url), url


def test_scope_includes_student_facing_pages_and_pdfs():
    for url in ("https://www.ucumberlands.edu/tuition-aid/tuition",
                "https://www.ucumberlands.edu/admissions/apply",
                "https://www.ucumberlands.edu/sites/default/files/downloads/VisitorsGuide.pdf"):
        assert is_in_scope(url), url


def test_ids_are_deterministic_and_urls_normalized():
    url = "https://www.ucumberlands.edu/tuition-aid/tuition"
    assert doc_id_for(url) == doc_id_for(url) and len(doc_id_for(url)) == 12
    assert normalize_url(url + "/#rates") == url


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
