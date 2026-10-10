# Generation and conversation status

Local Groq generation with openai/gpt-oss-20b is verified. OpenAI and Gemini
routing remain implemented; those providers were not live-tested with keys.
The root git-ignored .env is loaded into the environment without overriding
existing environment variables. No key is packaged or committed.

Degree, subject, format, audience, term and year are explicit conversation slots.
Comparisons replace a selector and retain intent; new facets keep the subject;
standalone topics, completion and Clear conversation reset state. Unknown fragments
ask for clarification. Undergraduate requests exclude graduate-specific sources.

Generation selects compact source-span identifiers. The application resolves exact
quotes and metadata URLs, then checks quote ownership, length, numbers and table
units. Saved tuition columns were aligned from the saved pandas table without
crawling. General category rates remain labeled as category rates.

89 automated tests pass. The final live UI smoke exercised 29 turns across three
retrievers with no UI or generation/grounding errors. Provider rate-limit fallbacks
are explicitly labeled and are not counted as generated answers. See
docs/app_verification.json for observed counts.

This is component verification, not proof of answer correctness or retrieval
quality. The score threshold remains uncalibrated. Golden answers, failure labels
and the frozen held-out evaluation remain pending human verification. No metrics
were invented.
