"""Document-level evaluation of the full Cicero multi-agent pipeline.

Translates a coherent multi-paragraph source document through all five roles
(Translator -> Blind Critic -> Alignment Inspector -> Fixer -> Final Auditor)
with continuity context between passages, then scores against a reference.

Scoring is alignment-tolerant chrF (primary) plus sentence-aligned BLEU.
"""
import argparse
import getpass
import os
import re
import sys
import time
from pathlib import Path

import sacrebleu
from interactive_translator import (APIError, Block, Config, HTTP, Models, PROVIDERS, Settings,
                                    TranslationError, estimate_tokens, fluency_payload,
                                    system_prompt, validate_review, validate_translation)

LANGUAGE = 'Turkish'
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+')

# Free-tier quotas are per minute, so space requests instead of firing back-to-back.
REQUEST_DELAY = 0.0
_last_request = 0.0


def _throttle():
    global _last_request
    wait = REQUEST_DELAY - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def call_with_retry(models, cfg, role, payload, retries=6):
    for attempt in range(retries):
        try:
            _throttle()
            return models.call(cfg, role, system_prompt(role, LANGUAGE), payload)
        except APIError as exc:
            if exc.status not in RETRYABLE_STATUS or attempt == retries - 1:
                raise
            wait = min(2 ** attempt, 60)
            print(f'    [{role}] HTTP {exc.status}; retry in {wait}s', file=sys.stderr)
            time.sleep(wait)
    raise TranslationError('retries exhausted')


def split_sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description='Multi-agent document BLEU/chrF evaluation.')
    parser.add_argument('--provider', default='google', choices=sorted(PROVIDERS))
    parser.add_argument('--model', required=True)
    parser.add_argument('--base-url', default=None)
    parser.add_argument('--src', default='bleu_source.en.txt')
    parser.add_argument('--ref', default='bleu_reference.tr.txt')
    parser.add_argument('--start', type=int, default=0, help='First source line (0-based).')
    parser.add_argument('--count', type=int, default=37, help='Number of source lines to use.')
    parser.add_argument('--passage', type=int, default=6, help='Sentences per passage/chunk.')
    parser.add_argument('--thoroughness', default='full', choices=('balanced', 'full'))
    parser.add_argument('--out', default='doc_candidate.tr.txt')
    parser.add_argument('--delay', type=float, default=4.0,
                        help='Seconds between provider requests (free-tier rate-limit safety).')
    args = parser.parse_args(argv)

    global REQUEST_DELAY
    REQUEST_DELAY = args.delay

    key = os.environ.get('CICERO_API_KEY') or getpass.getpass('API key: ').strip()
    if not key:
        sys.exit('No API key provided.')

    src_lines = [ln.strip() for ln in Path(args.src).read_text(encoding='utf-8').splitlines() if ln.strip()]
    ref_lines = [ln.strip() for ln in Path(args.ref).read_text(encoding='utf-8').splitlines() if ln.strip()]
    src_doc = src_lines[args.start:args.start + args.count]
    ref_doc = ref_lines[args.start:args.start + args.count]

    cfg = Config(provider=args.provider, model=args.model,
                 base_url=args.base_url or PROVIDERS[args.provider], key=key)
    configs = {r: cfg for r in ('translator', 'fluency', 'accuracy', 'fixer', 'auditor')}
    settings = Settings(language=LANGUAGE, thoroughness=args.thoroughness)

    passages = [src_doc[i:i + args.passage] for i in range(0, len(src_doc), args.passage)]

    http = HTTP()
    models = Models(http)
    results = []
    activity = []
    try:
        for pi, passage in enumerate(passages):
            blocks = [Block(s, 'paragraph') for s in passage]
            source = '\n\n'.join(passage)
            context = results[-1] if results else ''
            while estimate_tokens(context) > settings.context_tokens:
                context = context[max(1, len(context) // 10):]
            prefix = 'PREVIOUS TRANSLATION (context only):\n' + context + '\n\nSOURCE:\n' + source
            print(f'Passage {pi + 1}/{len(passages)} ({len(passage)} sentences) ...')

            draft = validate_translation(
                call_with_retry(models, configs['translator'], 'translator', prefix), blocks)
            payload = prefix + '\n\nDRAFT:\n' + draft
            flu = validate_review(call_with_retry(
                models, configs['fluency'], 'fluency', fluency_payload(draft, context)))
            acc = validate_review(call_with_retry(
                models, configs['accuracy'], 'accuracy', payload))
            reviews = [flu, acc]
            verdicts = [f'fluency={"PASS" if flu["ok"] else "FIX"}',
                        f'accuracy={"PASS" if acc["ok"] else "FIX"}']
            if flu['ok'] and acc['ok'] and settings.thoroughness == 'full':
                aud = validate_review(call_with_retry(models, configs['auditor'], 'auditor', payload))
                verdicts.append(f'audit={"PASS" if aud["ok"] else "FIX"}')
                if not aud['ok']:
                    reviews = [aud]
            if not all(r['ok'] for r in reviews):
                findings = '\n'.join(r['findings'] for r in reviews if not r['ok'])
                for attempt in (1, 2):
                    draft = validate_translation(call_with_retry(
                        models, configs['fixer'], 'fixer',
                        prefix + '\n\nDRAFT:\n' + draft + '\n\nFINDINGS:\n' + findings), blocks)
                    aud = validate_review(call_with_retry(
                        models, configs['auditor'], 'auditor', prefix + '\n\nDRAFT:\n' + draft))
                    if aud['ok']:
                        verdicts.append(f'fix{attempt}+audit=PASS')
                        break
                    findings = aud['findings']
                else:
                    raise TranslationError(f'Passage {pi + 1} failed two corrections.')
            results.append(draft)
            activity.append(f'P{pi + 1}: ' + ', '.join(verdicts))
            print(f'    {activity[-1]}')
            Path(args.out).write_text('\n\n'.join(results) + '\n', encoding='utf-8')
    finally:
        http.close()

    candidate = '\n\n'.join(results)
    ref_joined = '\n'.join(ref_doc)

    chrf_doc = sacrebleu.corpus_chrf([candidate], [[ref_joined]])

    cand_seg = split_sentences(candidate)
    ref_seg = split_sentences(ref_joined)
    n = min(len(cand_seg), len(ref_seg))
    cand_seg, ref_seg = cand_seg[:n], ref_seg[:n]
    bleu = sacrebleu.corpus_bleu(cand_seg, [[r] for r in ref_seg])
    chrf_seg = sacrebleu.corpus_chrf(cand_seg, [[r] for r in ref_seg])

    print('\n' + '=' * 60)
    print(f'Multi-agent document eval — {args.model} ({settings.thoroughness})')
    print(f'Passages: {len(passages)}, source sentences: {len(src_doc)}')
    print('=' * 60)
    for line in activity:
        print('  ' + line)
    print('-' * 60)
    print(f'chrF (document)      : {chrf_doc.score:.2f}')
    print(f'chrF (segment-aligned): {chrf_seg.score:.2f}')
    print(f'BLEU (segment-aligned): {bleu.score:.2f}')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
