"""Checks for the PII policy (crawl-scope exclusions are tested in test_crawl_scope.py). The real corpus contains no sensitive PII, so these
synthetic examples prove the rules actually fire (and don't over-fire).

Run:  python -m tests.test_pii
"""
from compass.pii import CORPUS_KINDS, redact


def test_user_question_identifiers_are_removed():
    text, found = redact("My student ID is 1234567 and my SSN is 123-45-6789. What GPA do I need?")
    assert "1234567" not in text and "123-45-6789" not in text
    assert found == {"STUDENT_ID": 1, "SSN": 1}
    assert "What GPA do I need?" in text  # the question itself survives


def test_personal_contact_details_are_removed():
    text, found = redact("I'm jane.doe1999@gmail.com, call (859) 555-0142. Born on 04/12/2006. Card 4111 1111 1111 1111.")
    for secret in ("jane.doe1999", "555-0142", "04/12/2006", "4111"):
        assert secret not in text, secret
    assert found == {"EMAIL": 1, "PHONE": 1, "DOB": 1, "CARD": 1}


def test_official_contacts_and_facts_are_kept():
    for keep in ("Email registrar@ucumberlands.edu or call 606-539-4000",
                 "Classes begin Monday, August 24, 2026; tuition is $9,875 for 120 credit hours",
                 "FAFSA school code 001962"):
        assert redact(keep) == (keep, {}), keep


def test_corpus_rules_keep_public_organisation_phones():
    text = "Cumberland Inn 606-539-4100, Super 8 800-315-0286"
    assert redact(text, CORPUS_KINDS) == (text, {})


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
