# Ethics, privacy, and user reliance

## Source and privacy policy

The collection is limited to public, unauthenticated university information. The crawler checks robots rules, observes a one-request-per-second floor, and uses a role-based descriptive contact string. Login content and directory pages are excluded. The normalization pass quarantined four pages with directory-like email density, redacted non-role email addresses and 336 contact-block name candidates, and rejects SSN-like patterns. Raw and normalized documents remain local and are not part of the public source repository.

These automated rules cannot guarantee removal of all identifying information. They may also remove organization names or other harmless lines. Human privacy review remains a release prerequisite. The manually supplied Patriot Guide PDF has a provenance caveat: robots compliance was not independently verified. No further crawl was performed during application assembly.

## Safeguards in code

The answer pipeline filters known instruction-like text from retrieved evidence, checks user queries for known injection patterns, validates that cited quotes are exact and no longer than 25 words, restricts citations to university hosts, and rejects numeric claims unsupported by cited quotes. Weak reranker evidence is intended to trigger an explicit refusal, although its threshold remains provisional and uncalibrated. Selected individualized financial-aid, immigration, and health questions receive office referrals. The UI warns that information may be stale and shows official-source links and crawl dates.

Tests cover these mechanics, including malicious-context filtering, refusals, office referrals, and citation validation. They do not prove resistance to all attacks or semantic entailment of every generated claim. The application has not had real LLM generation or adversarial evaluation in this environment.

## Staleness and user reliance

The corpus is a snapshot. Explicit effective dates are recorded only when source text provides a recognized ISO date; unknown dates remain null. Crawl timestamps show when a page was collected, not when a policy takes effect. Calendar content lacks useful deadline detail, some PDFs are old, and tuition figures require checking against current official pages. The interface tells users to verify information on the official site. Personal eligibility, aid awards, immigration status, health, and other decisions require qualified staff.

## Evidence and remaining work

No personal-data audit has been completed by a human, no threshold has been calibrated, no human golden answers have been verified, and no generated answers have been graded. Before public deployment, complete privacy review, current-source review, human evaluation, adversarial testing, and operating-owner review. No live deployment has been made.

See [../docs/ETHICS.md](../docs/ETHICS.md) for implemented controls and [../docs/REPRODUCE.md](../docs/REPRODUCE.md) for local execution and data-handling details.
