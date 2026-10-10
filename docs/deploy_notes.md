# Local run and deployment notes

## Current readiness

The application code and UI checks are in place, but a real model-backed deployment has not been demonstrated. The real MiniLM and cross-encoder downloads were blocked by sandbox DNS, the local HTTP server could not bind a socket in the sandbox, and no provider API key was available for a generation run. Thirty-six tests passed, including Streamlit AppTest and a real Chroma integration check; these do not replace a real model-backed corpus smoke run. Prepare and verify those dependencies in a normal local terminal before presenting the app as operational.

## Prepare a local environment

Use Python 3.11 for a new installation. From `UC_CompassAI/`:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export PYTHONPYCACHEPREFIX="$PWD/.cache/pycache"
export HF_HOME="$PWD/.cache/huggingface"
.venv/bin/python scripts/download_models.py
export HF_HUB_OFFLINE=1
```

Provide the private normalized corpus in `data/processed/` using the approved local transfer. Do not commit raw pages, normalized records, indexes, model caches, API credentials, or evaluation outputs containing source passages. Build and exercise the index:

```bash
.venv/bin/python -m indexing.chunking
.venv/bin/python -m indexing.rechunk --strategy structure --collection compass
.venv/bin/python scripts/smoke.py
```

The generation adapter supports Groq, OpenAI, and Gemini. Groq is preferred with model `openai/gpt-oss-20b`; OpenAI `gpt-4o-mini` and Gemini `gemini-3.8-flash` are supported alternatives. This is an authorized variation from the original OpenAI-only stack. Set only the provider key you intend to use in the terminal environment: `GROQ_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`. The application may fall back among configured accessible providers. For an evaluation run, pin provider and model and disable fallback. Never put key values in source, shell scripts, documentation, screenshots, or a commit. Without a configured provider key, the application stays in retrieval-only mode and can show source excerpts without synthesizing an answer. Confirm that the chosen index strategy matches `config/shared_config.yaml` before starting the app.

Start the local interface from the project directory:

```bash
.venv/bin/python -m streamlit run app/streamlit_app.py
```

Streamlit AppTest passing confirms interface behavior but does not prove that the HTTP server, downloaded models, index, or generation API works. Complete a real local smoke run with a source-backed answer, a refusal, and a high-stakes referral before presenting the application.

## Hosted deployment

No hosted deployment has been configured or published. Before using a hosting provider, build the private corpus index in a controlled environment with the pinned models and compatible dependencies. Package only code and reviewed non-sensitive artifacts. Keep the raw corpus, normalized documents, persistent index, model weights, query logs, and credentials private unless a separate review explicitly approves their handling.

For a Streamlit-compatible host, add the intended provider key (`GROQ_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`) through the host's encrypted secret settings. Do not add an actual secret to this repository or to a committed `.env` file. Application mode can select among configured accessible providers; evaluation mode must pin a provider and model and disable fallback. Set `HF_HOME` to a persistent cache location only if the provider supports private persistent storage; otherwise supply model artifacts through its approved secure build process. Confirm outbound access and model availability during deployment checks. Do not substitute retired Groq `llama-3.3` or legacy-restricted Gemini `gemini-2.5` model identifiers. Configure current API pricing for the pinned provider in the shared configuration before reporting cost; unset prices intentionally result in unknown cost. No provider API has been smoke-tested, so do not treat adapter configuration as verified generation behavior.

A deployment owner should verify that the published build points to the intended corpus and index, that logs do not retain sensitive prompts or passages, and that the visible stale-information notice and official-source citations work in the hosted interface. Re-check source currency and privacy review before releasing an updated corpus. Treat this as an operational checklist, not evidence that a deployment has occurred.
