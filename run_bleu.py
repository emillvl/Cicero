"""Run a BLEU evaluation of the Cicero translator on a real test set.

Source + reference come from the WMT18 English->Turkish newstest set
(downloaded via sacrebleu). Each source sentence is translated with the
Cicero translator role, and BLEU is computed against the reference.

Usage:
    python run_bleu.py --provider google --model <model-id> --limit 100

The API key is read from the CICERO_API_KEY environment variable, or typed
interactively (never saved). Provider charges apply.
"""
import argparse
import getpass
import os
import sys
import time
from pathlib import Path

import sacrebleu
from interactive_translator import (APIError, Config, HTTP, Models, PROVIDERS, TranslationError, system_prompt)

LANGUAGE = 'Turkish'
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def translate_one(models, cfg, sentence, retries=5):
    payload = 'SOURCE:\n' + sentence
    for attempt in range(retries):
        try:
            return models.call(cfg, 'translator', system_prompt('translator', LANGUAGE), payload).strip()
        except APIError as exc:
            if exc.status not in RETRYABLE_STATUS or attempt == retries - 1:
                raise
            wait = min(2 ** attempt, 60)
            print(f'  rate-limited (HTTP {exc.status}); retrying in {wait}s', file=sys.stderr)
            time.sleep(wait)
    raise TranslationError('Retries exhausted.')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description='BLEU evaluation of the Cicero translator (WMT18 en-tr).')
    parser.add_argument('--provider', default='google', choices=sorted(PROVIDERS),
                        help='Provider for the translator role.')
    parser.add_argument('--model', required=True, help='Model ID for the translator role.')
    parser.add_argument('--base-url', default=None, help='Override the provider base URL.')
    parser.add_argument('--limit', type=int, default=100, help='Number of sentences to translate (1-3000).')
    parser.add_argument('--offset', type=int, default=0, help='Starting sentence index.')
    parser.add_argument('--src', default='bleu_source.en.txt')
    parser.add_argument('--ref', default='bleu_reference.tr.txt')
    parser.add_argument('--out', default='bleu_candidate.tr.txt')
    parser.add_argument('--delay', type=float, default=5.0, help='Seconds to wait between requests.')
    args = parser.parse_args(argv)

    key = os.environ.get('CICERO_API_KEY') or getpass.getpass('API key: ').strip()
    if not key:
        sys.exit('No API key provided.')

    src_lines = [ln.strip() for ln in Path(args.src).read_text(encoding='utf-8').splitlines() if ln.strip()]
    ref_lines = [ln.strip() for ln in Path(args.ref).read_text(encoding='utf-8').splitlines() if ln.strip()]
    if len(src_lines) != len(ref_lines):
        sys.exit(f'Source ({len(src_lines)}) and reference ({len(ref_lines)}) line counts differ.')

    end = min(args.offset + args.limit, len(src_lines))
    src_lines = src_lines[args.offset:end]
    ref_lines = ref_lines[args.offset:end]

    cfg = Config(provider=args.provider, model=args.model,
                 base_url=args.base_url or PROVIDERS[args.provider], key=key)

    http = HTTP()
    models = Models(http)
    candidates = []
    try:
        for i, sentence in enumerate(src_lines):
            try:
                text = translate_one(models, cfg, sentence)
            except TranslationError as exc:
                print(f'[{i + 1}/{len(src_lines)}] FAILED: {exc}', file=sys.stderr)
                text = ''
            candidates.append(text)
            Path(args.out).write_text('\n'.join(candidates) + '\n', encoding='utf-8')
            print(f'[{i + 1}/{len(src_lines)}] {text[:60]!r}')
            if i + 1 < len(src_lines):
                time.sleep(args.delay)
    finally:
        http.close()

    nonempty = [(c, r) for c, r in zip(candidates, ref_lines) if c]
    if not nonempty:
        sys.exit('No successful translations to score.')
    cands = [c for c, _ in nonempty]
    refs = [r for _, r in nonempty]

    refs_nested = [[r] for r in refs]
    corpus = sacrebleu.corpus_bleu(cands, refs_nested)
    corpus_lc = sacrebleu.corpus_bleu(cands, refs_nested, lowercase=True)
    per = [sacrebleu.sentence_bleu(c, [r]).score for c, r in zip(cands, refs)]
    avg = sum(per) / len(per)

    print('\n' + '=' * 56)
    print(f'Scored {len(cands)}/{len(src_lines)} sentences (provider={args.provider}, model={args.model})')
    print('=' * 56)
    print(f'Corpus BLEU           : {corpus.score:.2f}')
    print(f'Corpus BLEU (case-ins.): {corpus_lc.score:.2f}')
    print(f'Avg sentence BLEU     : {avg:.2f}')
    print(f'  {corpus}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
