# Implementation verification

Verified against Python 3.12. **166 tests passed, plus 50 subtests, with 90% overall statement-and-branch coverage.** No failures or skips. No authenticated provider requests were made by the test suite; all model and balance responses were simulated.

## Changes in this release

- Model selection uses the provider catalog, with filtering and exact-ID fallback. Fixed model names, preset choices, named model recommendations, per-model token profiles and model-specific reasoning overrides were removed.
- Within one passage, the Blind Critic and the Alignment Inspector run concurrently (bounded by `MAX_PARALLEL_CALLS = 10`). Passages stay ordered so each still receives the previous approved translation as continuity context. Shared state (usage records, checkpoint stages, partial output, retry prompts) is guarded by locks, and unfinished stages are tracked in `pending_all` for crash-safe resume. A regression test asserts the two reviewers overlap.
- Existing saved runs retain their chosen model IDs, configured token budgets and completed stages. Current translation/review prompts and Google inference request fields are unchanged.
- Usage is recorded before response validation and persisted across resume. Input, output and total counts include startup samples, refused/truncated replies and explicit retries when usage is returned. Cached/reasoning breakdowns are not counted twice.
- A missing usage response remains unknown. Requests from older versions are explicitly excluded. Completed-stage reuse and export-only resume do not add tokens again.
- Usage totals appear at completion or interruption and are saved in usage-summary.txt. A separate usage.json holds per-attempt counts without keys or document content.
- The official DeepSeek balance endpoint is queried once per selected account at the end of a session, including interrupted sessions. Other connections report unavailable. No manual pricing, estimated charges or inferred remaining-token balance is added.

## Offline tests

Run Test_Cicero.cmd after installation, or use:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q --cov=interactive_translator --cov-branch --cov-report=term-missing
```

The 67 original unittest tests remain in test_translator.py. Additional regressions are in test_reliability.py and test_usage.py. Pytest runs all three. conftest.py blocks socket connections during the suite; installation downloads dependencies, but the tests themselves do not use the network.

Coverage includes:

- Reported usage for compatible providers, Anthropic's additive input categories and DeepSeek's cache details; no double counting of cache or reasoning; missing, partial and malformed usage.
- Durable request intent before POST, usage saved before malformed-response rejection, truncated-response accounting, exhausted-quota accounting, and local-write failure preventing a new POST.
- Resume without resetting or duplicating counts, unknown historical usage, corrupt usage files left untouched, and complete end-to-end translation with a saved token total.
- End-to-end HTTP 402 interruption followed by a real-shaped balance response; partial translation/checkpoint preserved; no secret error-body leakage.
- Multiple balance currencies, zero balance and insufficient-funds flag; one lookup for a shared account; no requests to unsupported/custom servers or completed runs without keys; nonfatal failed balance lookups.
- Catalog selection, filter retry, exact-ID fallback, no presets, role descriptions, per-provider key reuse, Fixer reuse and advanced manual budgets.
- Existing recovery behavior, received-text archives, all seven role samples, source-aware marker validation, review verdict rules, checkpoint upgrades, numeric cancellation and settings validation.
- TXT encoding detection/overrides, Unicode and long-paragraph chunk coverage, DOCX extraction, PDF export/extraction, numbered-list behavior and OCR timeout forwarding with mocked recognition.

## Saved-run and request comparison

The actual delivered version-5 script was loaded separately for comparison:

- Prompt fingerprints matched in four target languages.
- Eight old checkpoints, including Google and legacy NVIDIA configurations, upgraded with completed text, pending stage, model IDs and budgets intact. Backup bytes matched the original checkpoint.
- Four mixed heading/list/numbered/Unicode/long-paragraph chunk fixtures retained identical boundaries under identical budgets.
- 105 provider/role/output-budget comparisons with a generic catalog model produced identical inference request addresses, headers and bodies. Official provider base addresses also matched.
- The only removed inference options are the old named-model reasoning overrides. Models now use provider defaults for those optional controls. Token tracking reads response metadata without modifying inference payloads.

The current package is syntax-checked and archive contents are verified against the reviewed deliverables. It includes three test files, the offline fixture, test runner/configuration, dependency lists and documentation.

## Earlier review findings

The previous reliability fixes remain covered: in-process explicit stage retry, preservation of malformed review evidence, source-aware literal-marker acceptance, tests of all actual role prompts, a shared findings limit, configurable OCR timeout, exposed expansion/context settings, friendly checkpoint-schema errors, numeric cancellation and numbered-list rendering.

Two qualifications to that original review still apply: tests were already present, and missing optional dataclass settings already used defaults. The double numbered prefix came from rendering/export helpers; partial TXT already used model text directly.

## Verification limits

No real API key, live inference or live balance lookup was used. Provider documentation and balance-query scope are recorded in PROVIDER_VERIFICATION.md. Tests do not establish current account access, live service reliability, billing accuracy or remaining free quota.

Native Tesseract is unavailable, so OCR recognition was mocked. DOCX structure and PDF text/export behavior were checked programmatically; Word/DOCX visual rendering remains unverified because LibreOffice is unavailable. This release did not repeat the earlier PDF visual inspection. No million-word stress run was performed.

Windows launchers were reviewed but were not used to install into the user's system Python. Test dependencies were installed only in an isolated task workspace.
