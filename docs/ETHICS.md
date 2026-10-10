# Ethics and demonstrated safeguards

Safeguards implemented and tested:

1. Weak or absent reranker evidence yields explicit refusal. The threshold is
   provisional, not calibrated; verified development data must calibrate it.
2. Individualized financial-aid and immigration questions produce office referrals.
3. Known prompt-injection instructions in queries are refused and injected passages
   are dropped. Remaining retrieved text is serialized as untrusted JSON data.
4. Citation IDs and <=25-word exact quotes are checked against retrieved chunks;
   citation URLs are attached from university metadata. Off-domain and invented
   citation IDs/URLs are rejected. Claim numbers must occur in the supporting quotes.
5. Extraction/privacy normalization redacts non-role emails and contact-block name
   candidates, rejects SSN-like data, and quarantines directory-like documents.

Unit tests demonstrate refusal, referral, malicious-context filtering, and citation
validation. The real Chroma integration test demonstrates persistence, metadata
filtering, deletion, and zero stale IDs after a strategy change using synthetic
vectors. Synthetic vectors are never used for chatbot answers or evaluation.
Streamlit AppTest demonstrates history, citations, refusal styling, and referrals in
an explicitly labelled UI mock. This is not evidence of real retrieval quality.

Limits: regex injection checks are incomplete; URL/quote validation does not prove
semantic entailment. The LLM prompt is a safeguard, not a guarantee against
hallucination. Human answer/citation grading, adversarial tests, and personal-name
review remain required. The UI warns users about stale content and links to official
sources with crawl dates. No-key operation returns source excerpts, not fabricated
LLM answers. No individual decision should be made from this assistant alone.

The crawler uses public university hosts, robots checks, a one-second request floor,
and a descriptive role-based contact string. Hosts requesting excessive delay are
skipped. No additional university crawl was performed during application assembly.
The Patriot Guide was supplied manually; its acquisition caveat is preserved.

No API key was present during this build. No key is packaged or committed. GROQ_API_KEY, OPENAI_API_KEY and
GEMINI_API_KEY are read only from the environment; exception text and chat logs are not
persisted by the UI. Evaluation outputs may contain queries and passages, so they
remain local in ignored data/runtime until reviewed for safe publication.

Credential requests are refused before retrieval. Public password-reset guidance
remains eligible for source-grounded retrieval. A real smoke check also demonstrated
weak-evidence refusal for an out-of-corpus question; this is not a calibration or
a measured refusal-rate result.

Conversation state stores only user intent and pending clarification slots in
the session, not assistant assertions as facts. Resolved follow-ups pass the same
safety gate and grounding rules as standalone questions. Context is isolated
between sessions and resets on completion or an explicit new conversation.
