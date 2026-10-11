"""Checks for stage 2 extraction helpers. Each test pins down a real bug found
while building the corpus.

Run:  python -m tests.test_extract
"""
from compass.s2_extract import (WEB_PAGE_MARKERS, clean, effective_date, join_date_lines, page_type,
                                unlink_course_lists)


def test_calendar_dates_stay_paired_with_their_event():
    # Calendar PDFs print the date above its event; flattened, the LLM paired
    # "Classes Begin" with the next date (Sept 1 = last day to register).
    raw = "Monday, August 24, 2026\nClasses Begin\nTuesday, September 1, 2026\nLast Day to Register for Classes"
    assert join_date_lines(raw).splitlines() == [
        "Monday, August 24, 2026: Classes Begin",
        "Tuesday, September 1, 2026: Last Day to Register for Classes",
    ]


def test_dot_leaders_and_form_blanks_are_collapsed():
    # One handbook TOC chunk was 147 words but 4,337 tokens because of dot leaders.
    assert "...." not in clean("Bookstore........................................ 14")
    assert "____" not in clean("Name: ______________________ Relationship: ________")


def test_saved_web_pages_are_recognised():
    # Two "PDFs" (Cooperating Teacher Guide, CACREP 2017) were printouts of the homepage.
    printout = "Skip to main content Winter Break ... Main navigation Academics Admissions"
    assert all(m in printout for m in WEB_PAGE_MARKERS)
    assert not all(m in "Calendar of Academic Events Fall 2026" for m in WEB_PAGE_MARKERS)


def test_catalog_course_links_become_plain_text():
    # Trafilatura dropped link-heavy course lists as navigation.
    html = '<ul><li><a href="https://catalog.ucumberlands.edu/preview_course.php?x=1">ITS 831 - IT Strategy</a></li></ul>'
    out = unlink_course_lists(html)
    assert "ITS 831 - IT Strategy" in out and "<a " not in out


def test_page_type_and_effective_date():
    assert page_type("https://www.ucumberlands.edu/academics/graduate/phd-information-technology", "PhD in IT") == "program"
    assert page_type("https://www.ucumberlands.edu/tuition-aid/tuition", "Tuition") == "financial"
    assert page_type("https://x/sharepoint", "Academic Calendar Fall 2026") == "calendar"
    assert effective_date("Cost of Attendance", "## Cost of Attendance\n**2025-2026 Academic Year**") == "2025-2026"
    assert effective_date("Student Handbook 2026-2027", "STUDENT HANDBOOK") == "2026-2027"
    assert effective_date("Visit", "Come see us any time.") is None


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
