"""Query rewriting (multi-query retrieval): bridge the gap between how students ask
and how the website words things.

"if I have billing questions, how should I escalate" shares no words with the page
that answers it ("Student Financial Center ... Phone: 606-539-4220"). Claude rewrites
the question into a few short search queries in university-website vocabulary;
stage 6 searches with all of them plus the original and fuses the results.

Reads:  the (already PII-redacted) question
Writes: nothing. Returns {"queries": [...], "cost_usd": float}
Run:    python -m compass.rewrite "How do I get in touch with admissions?"
"""
import argparse

from compass.s9_generate import call_claude

MAX_REWRITES = 3

SYSTEM = f"""You turn a student's question into search queries for the University of the \
Cumberlands website. Write up to {MAX_REWRITES} short queries (3-8 words each) that use the \
words a university website would use, for example "contact", "phone", "email", "office", \
"Student Financial Center", "payments", "student account", "policy", "requirements", \
"eligibility", "deadline". Keep the meaning of the question; don't add facts or answer it.
Output only the queries, one per line, with no numbering or extra text."""


def rewrite(question: str) -> dict:
    out = call_claude(SYSTEM, question)
    lines = [line.strip(" -*0123456789.").strip() for line in out["text"].splitlines()]
    # Keep only query-shaped lines: the model sometimes adds a sentence of commentary
    # ("I can't say that tuition is free ... :") that must not become a search query.
    queries = [q for q in lines if q and q.lower() != question.lower() and len(q.split()) <= 10
               and not q.endswith(":") and not q.lower().startswith(("i ", "i'", "here", "note"))][:MAX_REWRITES]
    return {"queries": queries, "cost_usd": out["cost_usd"]}


CONDENSE_SYSTEM = """You help a university chatbot handle follow-up questions. Given the \
recent conversation and the student's new message, rewrite the new message as one \
standalone question that makes sense without the conversation (resolve "it", "that \
program", "what about ..."). If it is already standalone, return it unchanged. Don't \
answer it and don't add facts. Output only the question."""


def condense(question: str, history: list[tuple[str, str]], turns: int = 3) -> dict:
    """Follow-ups: turn "what about graduate students?" into a standalone question
    using the last few (question, answer) turns. Retrieval can't resolve "it" by itself."""
    convo = "\n".join(f"Student: {q}\nAssistant: {a[:400]}" for q, a in history[-turns:])
    out = call_claude(CONDENSE_SYSTEM, f"<conversation>\n{convo}\n</conversation>\n\nNew message: {question}")
    standalone = out["text"].strip().splitlines()[0].strip() if out["text"].strip() else question
    return {"question": standalone, "cost_usd": out["cost_usd"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    r = rewrite(parser.parse_args().question)
    print("\n".join(r["queries"]), f"\n(${r['cost_usd']:.5f})")
