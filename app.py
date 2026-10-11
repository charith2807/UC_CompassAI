"""Cumberlands Compass AI - Streamlit chat UI.

Run:  .venv/bin/streamlit run app.py
"""
import os

import anthropic
import pandas as pd
import streamlit as st

from compass import config  # noqa: F401  (loads .env, sets HF_HOME)
from compass.pipeline import CONFIGS, answer
from compass.s9_generate import MODEL

st.set_page_config(page_title="Cumberlands Compass AI", page_icon="🧭")
title_col, info_col = st.columns([5, 1], vertical_alignment="center")
title_col.title("🧭 Cumberlands Compass AI")
with info_col.popover("ℹ️", help="What can I ask?"):
    st.markdown(
        "**I can answer from public university pages:**\n"
        "- Programs (undergraduate, graduate, doctoral, certificates)\n"
        "- Tuition, cost of attendance, financial aid, payments\n"
        "- Admissions (international, transfer, dual credit)\n"
        "- 2026-27 academic calendar\n"
        "- Campus rules and services (Student Handbook 2026-27)\n\n"
        "**I can't see** term course schedules or your personal records "
        "(grades, aid, balance). I'll point you to the right office instead."
    )
st.caption("Answers from public University of the Cumberlands web pages, with sources. "
           "Not official advice: confirm important details with the university.")

with st.sidebar:
    # The UI offers the four course baselines; ablation steps (A1-A4, B3-no-*) are eval-only.
    UI_CONFIGS = ["B0", "B1", "B2", "B3"]
    config_name = st.radio("Configuration", UI_CONFIGS, index=UI_CONFIGS.index("B3"),
                           help="B0 closed-book · B1 BM25 · B2 dense + naive chunks · B3 final "
                                "(hybrid + rerank + section expansion + rewrite fallback)")
    st.json(CONFIGS[config_name])
    page_type = st.selectbox("Search only", ["all pages", "program", "financial", "admissions", "policy",
                                             "calendar", "student-life", "about"],
                             help="Metadata filter on page type, applied inside the vector database and BM25")
    st.caption(f"Model: `{MODEL}`")
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("No ANTHROPIC_API_KEY in .env: retrieval, refusals and referrals still work; "
                   "generated answers will fail.")


def show_trace(t: dict) -> None:
    with st.expander("Retrieval trace"):
        st.write(f"**Decision:** `{t['action']}` - {t['reason']}  ·  **latency** {t['latency_s']} s"
                 f"  ·  **cost** ${t.get('cost_usd', 0):.4f}")
        if t.get("queries"):
            st.write("**0. Search queries** (your question + rewrites in website vocabulary)")
            st.markdown("\n".join(f"- {q}" for q in t["queries"]))
        if t.get("candidates"):
            st.write(f"**1. {t['retriever']} candidates** ({t['strategy']} chunks)")
            st.dataframe(pd.DataFrame(t["candidates"])[["rank", "score", "title", "section"]],
                         hide_index=True, width="stretch")
        if t.get("reranked"):
            st.write("**2. After cross-encoder rerank** (score < 0 ≈ not relevant)")
            st.dataframe(pd.DataFrame(t["reranked"])[["rerank_score", "rank", "title", "section"]]
                         .rename(columns={"rank": "was rank"}), hide_index=True, width="stretch")
        if t.get("expanded"):
            st.write(f"**2b. Section expansion** added {len(t['expanded'])} sibling chunk(s) from the same sections")
        if t.get("prompt"):
            st.write("**3. Prompt sent to the LLM**")
            st.code(t["prompt"], language="xml")
        if t.get("invalid_citations"):
            st.error(f"Invalid citations (not among the sources sent): {t['invalid_citations']}")


def show_answer(t: dict) -> None:
    if t.get("followup_of"):
        st.caption(f"↪ Follow-up understood as: “{t['question']}”")
    if t.get("pii_removed"):
        kinds = ", ".join(f"{k.replace('_', ' ').lower()} ×{n}" if n > 1 else k.replace("_", " ").lower()
                          for k, n in t["pii_removed"].items())
        st.info(f"🔒 Removed from your question before it was searched or sent to the AI: {kinds}. "
                f"Sent as: “{t['question']}”")
    icon = {"refuse": "🚫 ", "refer": "📞 "}.get(t["action"], "")
    st.markdown(icon + t["answer"])
    pages = {}  # several chunks can come from one page: list each page once
    for c in t.get("citations", []):
        age = " · ".join(x for x in (f"effective {c['effective_date']}" if c.get("effective_date") else "",
                                      f"crawled {c['fetched_at'][:10]}" if c.get("fetched_at") else "") if x)
        pages.setdefault((c["title"], c["url"], age), []).append(c["n"])
    for (title, url, age), ns in pages.items():
        # Content age next to every source: an old page cited with a real URL looks verified.
        st.markdown(f"{''.join(f'[{n}]' for n in ns)} [{title}]({url})" + (f"  \n<small>🕒 {age}</small>" if age else ""),
                    unsafe_allow_html=True)
    show_trace(t)


if "history" not in st.session_state:
    st.session_state.history = []

for role, content in st.session_state.history:
    with st.chat_message(role):
        if role == "assistant":
            show_answer(content)
        else:
            st.markdown(content)

if question := st.chat_input("Ask about admissions, tuition, financial aid, programs..."):
    st.session_state.history.append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching university pages..."):
            try:
                turns = st.session_state.history[:-1]  # everything before this question
                past = [(q, t["answer"]) for (r1, q), (r2, t) in zip(turns[0::2], turns[1::2])
                        if r1 == "user" and r2 == "assistant"]
                trace = answer(question, **CONFIGS[config_name], history=past or None,
                               page_type=None if page_type == "all pages" else page_type)
            except anthropic.AuthenticationError:
                st.error("Claude rejected the API key. Check ANTHROPIC_API_KEY in .env.")
                st.stop()
            except anthropic.APIConnectionError:
                st.error("Could not reach the Claude API. Check your connection.")
                st.stop()
            except TypeError as e:  # anthropic.Anthropic() without any credentials
                st.error(f"No Claude credentials found. Add ANTHROPIC_API_KEY to .env. ({e})")
                st.stop()
        show_answer(trace)
    st.session_state.history.append(("assistant", trace))
