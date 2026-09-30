# Cicero

Cicero translates documents into readable plain text. It is an interactive Python
program: you pick a file, choose a target language and a model, and it produces a
UTF-8 text file. Translation does not preserve the source layout. Paragraph
counts, heading markers, and list markers may change, because Cicero formats the
text locally after translating it.

The program is resumable. Every run writes to its own folder and keeps enough
state to continue after a stop, a crash, or a provider error.

## Requirements

- Python 3.11 or later.
- An API key for one of the supported providers.
- Tesseract, installed separately and on `PATH`, if you need OCR (scanned PDFs,
  images, or image-only DOCX). The Python wrapper is in `requirements.txt`, but
  the Tesseract program itself is not bundled.

## Install and run on Windows

1. Keep the files together in a writable folder.
2. Run `Install_Cicero.cmd` once. It creates a local `.venv` and installs the
   dependencies.
3. Run `Start_Cicero.cmd`. Choose a document and a target language.

To install and run manually:

```text
python -m pip install -r requirements.txt
python interactive_translator.py
```

The program asks for your API key at run time with a hidden prompt. Keys are
never written to disk. Provider charges apply to the account you use, including
the optional startup samples.

## How a run works

1. A native file window opens. If it cannot, Cicero asks for a path.
2. You choose the target language and, in advanced mode, the passage size,
   reviewing mode, file-reading options, and token budgets.
3. You choose the models. One model can serve every role, or you can pick a model
   per role. A provider key is entered once per provider and server.
4. Cicero extracts the text, splits it into passages, and shows the passage
   count.
5. Startup checks run seven short samples across all five roles. You can skip
   them, and the reviews still run during translation.
6. Each passage is translated, reviewed, corrected when needed, and audited.
7. The finished text is saved as `translation.txt`. You can also export DOCX or
   PDF.

### Roles

| Role | Job |
| --- | --- |
| Translator | Translates each source passage. |
| Blind Critic | Reads the translation on its own for naturalness and style. |
| Alignment Inspector | Compares source and translation for missing or changed meaning. |
| Fixer | Corrects the draft using the reviewers' findings. |
| Final Auditor | Checks the corrected draft for accuracy and fluency. |

### Concurrency

Within one passage, the Blind Critic and the Alignment Inspector run at the same
time, because they do not depend on each other. Passages themselves stay in
order, so each passage still receives the previous approved translation as
continuity context. The number of simultaneous provider calls is capped at ten.

## Supported documents

- **TXT**: BOM and UTF detection, plus automatic legacy-encoding detection, with a
  source preview and a manual override.
- **DOCX**: paragraphs, headings, lists, table-cell text, footnotes, and endnotes.
  Formatting runs are joined before translation. Table geometry, repeating
  headers and footers, comments, charts, and embedded images are not
  reconstructed. An image-only DOCX uses local OCR in document image order.
- **PDF**: digital text in reading order, with best-effort headings. Sparse
  scanned pages use local OCR, which replaces the page's digital extraction so
  both copies are not appended.
- **PNG, JPEG, TIFF, WEBP**: local OCR, with multi-frame images read in order.

OCR uses Tesseract on your computer. Choose the source-language code in advanced
settings, for example `eng`, `rus`, or `eng+rus`. You can force OCR on every PDF
page. No cloud OCR account or upload is used. OCR accuracy depends on the scan.
Mixed digital and scanned pages, multi-column PDFs, and unusual heading styles
need checking.

## Output files

Each run creates a folder under `translations/`, beside the program:

- `translation.txt`: the completed UTF-8 deliverable.
- `translation.partial.txt`: saved passages with explicit incomplete or
  unreviewed labels. Missing passages are marked, never silently skipped.
- `review-notes.txt`: the reviewers' findings, kept separate from the translation.
- `passage-...received.txt`: the text received from each role, saved before
  validation and labelled unreviewed. Startup evidence uses `sample-...`. A
  response that contains a configured API key is never saved.
- `checkpoint.json`: saved progress, settings, and stage results. No keys.
- `usage.json`: API-reported token counts per request attempt, kept across
  resumes. No keys, prompts, or response text.
- `usage-summary.txt`: token totals and the latest balance result, when available.
- `translation.docx`, `translation.pdf`: optional exports after completion.

The source file is only read, never modified. A new run gets a new folder.

## Resume

Run the program again and select the same source. If a saved run exists, Cicero
offers to continue it and restores its language and model settings. You enter
keys again only if more inference is needed. Completed stages are reused.

When the source content, target language, models, chunk boundaries, settings, or
prompts do not match, Cicero refuses to reuse the checkpoint and says why.
Checkpoints written by earlier shipped versions are upgraded in place, with a
backup and completed stages retained. Keep one instance open per run.

## Passage size and reviewing

The default reviewing mode is balanced: both reviewers run, and if both pass,
there is no final audit. Corrections are always audited, with at most two
correction attempts. Full mode adds an audit even when both initial reviews pass.
A failed or malformed review is never treated as approval.

The passage target is 8,000 estimated source tokens, not 8,000 characters. Cicero
labels its estimate honestly; it is a planning estimate, not the provider's exact
tokenizer. It reserves output space using a 2.5x expansion allowance plus
overhead, and checks request size in UTF-8 bytes. By default, the last 1,000
estimated tokens of the previous approved translation provide continuity
context. There is no whole-book memory or external glossary, so terminology can
drift over long documents.

Source input is capped at 200 MB, expanded DOCX at 500 MB, and extracted text at
20 million characters. Very large books should be split into volumes.

## Providers

Supported connections: Google, Anthropic, OpenAI, DeepSeek, Model Studio (Qwen),
Z.AI (GLM), OpenCode, and B.AI. The retired NVIDIA host is recognized only so
old checkpoints still resume.

Requests use a low temperature (0) for faithful, repeatable translation. Some
reasoning models ignore the temperature setting.

Cicero ships no model names, presets, or per-model token profiles. Models come
from the selected provider's catalog, or from an exact model ID you enter. A
catalog listing does not guarantee that the model supports document translation
or is available to your account. New selections use conservative operating
defaults of 32,768 context tokens and 4,096 output tokens; advanced settings let
you enter the model's documented limits. A key is never reused with a different
provider or server.

## Token usage and balance

At completion or interruption, Cicero prints input, output, and total tokens, and
totals by provider, model, and role, using the counts returned by the API. If a
request fails and reports no counts, its usage is marked unknown, not zero. The
official DeepSeek connection can return the account's monetary balance when the
session ends. Other connections report that balance is unavailable through them.
This is an implementation limit, not a claim that other companies have no billing
APIs, and it does not mean the balance is zero.

## Privacy

This section describes what the current implementation does. It is not a
guarantee.

- The text of each passage, the review prompts, and the draft are sent to the
  provider and model you select. The provider's own terms and retention policy
  apply to that data.
- OCR runs locally with Tesseract. OCR images and text are not uploaded as part
  of OCR.
- Translations, checkpoints, received model text, review notes, and usage records
  are written to the run folder on your disk. They are not encrypted and are not
  deleted automatically. Remove the run folder yourself when you no longer need
  the documents.
- The source file is read only.
- API keys are entered with `getpass` and are not saved. Responses that would
  contain a configured key are rejected and not written.
- Error messages withhold raw provider response bodies and document text.
- The only balance lookup is the documented DeepSeek endpoint, using the existing
  credential.

If you translate confidential material, that material reaches the provider you
choose, and it stays in the run folder until you delete it.

## Limitations

- Translation quality depends on the selected model. Cicero does not guarantee a
  correct translation and cannot prove that nothing was omitted.
- Local checks reject empty output, extreme whole-passage length anomalies, added
  wrappers, and truncated responses. They cannot detect every omission or
  mistranslation. The reviewers compare the full source and draft, but automated
  review is not perfect.
- Paragraph counts and layout need not match the source.
- OCR quality depends on the scan and on Tesseract's language data.
- A failed stage can be retried, and a retry may incur another charge. There is
  no automatic replay and no skipped stage.

## Development and tests

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q --cov=interactive_translator --cov-branch --cov-report=term-missing
```

Tests are in `test_translator.py`, `test_reliability.py`, and `test_usage.py`.
They run offline: `conftest.py` blocks network access, and provider responses are
simulated. Installing dependencies needs internet access; running the tests does
not.

## Evaluation

`run_document_eval.py` and `run_bleu.py` are optional evaluation scripts. They
score a translation against a reference with SacreBLEU (chrF and BLEU). They need
the `sacrebleu` package and a parallel source/reference corpus that you supply,
plus a provider key. They make real provider requests and can incur charges. They
are not part of the translator and are not run by the test suite.

## License

Cicero is licensed under the Apache License, Version 2.0. See `LICENSE` for the
full terms. `NOTICE` records the original authorship by Emil Valiyev.
