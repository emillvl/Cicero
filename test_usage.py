"""Offline accounting, balance, catalog and saved-run regressions."""
import json
from unittest.mock import Mock, patch

import pytest

import interactive_translator as app
from test_translator import DRAFT, PASS, SECRET, SOURCE


def config(provider='google', base=None):
    return app.Config(provider, 'catalog-model', base or app.PROVIDERS[provider], SECRET, 128000, 8192)


def envelope(text=DRAFT, finish='stop', usage=None):
    return {'choices': [{'message': {'content': text}, 'finish_reason': finish}], 'usage': usage}


@pytest.mark.parametrize('provider', ['google', 'openai', 'qwen', 'glm', 'nvidia'])
def test_compatible_usage_keeps_cache_and_reasoning_within_totals(provider):
    result = app.token_usage(provider, {'usage': {'prompt_tokens': 100, 'completion_tokens': 50,
        'total_tokens': 150, 'prompt_tokens_details': {'cached_tokens': 60, 'cache_write_tokens': 10},
        'completion_tokens_details': {'reasoning_tokens': 30}}})
    assert result == dict(input=100, output=50, total=150, cached_input=60, cache_write=10, reasoning_output=30)


def test_deepseek_cache_counts_do_not_add_to_prompt_twice():
    result = app.token_usage('deepseek', {'usage': {'prompt_tokens': 100, 'completion_tokens': 5,
        'prompt_cache_hit_tokens': 70, 'prompt_cache_miss_tokens': 30}})
    assert result['input'] == 100 and result['cached_input'] == 70 and result['total'] == 105


def test_anthropic_input_includes_cache_read_and_creation_once():
    result = app.token_usage('anthropic', {'usage': {'input_tokens': 30, 'output_tokens': 20,
        'cache_read_input_tokens': 70, 'cache_creation_input_tokens': 10,
        'output_tokens_details': {'thinking_tokens': 5}}})
    assert result == dict(input=110, output=20, total=130, cached_input=70, cache_write=10, reasoning_output=5)


@pytest.mark.parametrize('value', [None, [], {}, {'prompt_tokens': -1}, {'prompt_tokens': True},
                                  {'prompt_tokens': '100'}, {'completion_tokens': 10**15}])
def test_missing_or_invalid_usage_is_unknown(value):
    result = app.token_usage('google', {'usage': value})
    assert result['input'] is None and result['output'] is None and result['total'] is None


def test_partial_usage_keeps_reported_output_without_guessing_input():
    result = app.token_usage('google', {'usage': {'completion_tokens': 11, 'total_tokens': 111}})
    assert result['input'] is None and result['output'] == 11 and result['total'] == 111


def test_malformed_detail_is_ignored_without_losing_valid_counts():
    result = app.token_usage('openai', {'usage': {'prompt_tokens': 10, 'completion_tokens': 2,
                                               'prompt_tokens_details': [],
                                               'completion_tokens_details': {'reasoning_tokens': 50}}})
    assert result['total'] == 12 and result['reasoning_output'] is None


def test_paid_and_free_calls_are_recorded_identically_without_price_questions(tmp_path):
    cfg = config()
    http = Mock()
    http.request.side_effect = [envelope(usage={'prompt_tokens': 100, 'completion_tokens': 20}),
                               envelope(PASS, 'length', {'prompt_tokens': 120, 'completion_tokens': 8192}),
                               app.APIError(429, 'Rate or quota limit reported'), envelope(PASS)]
    models = app.Models(http)
    with app.UsageTracker(tmp_path, models, dict.fromkeys(app.ROLES, cfg)) as usage:
        models.call(cfg, 'translator', 'system', 'source', sample=True)
        with pytest.raises(app.IncompleteResponse):
            models.call(cfg, 'auditor', 'system', 'draft')
        with pytest.raises(app.APIError):
            models.call(cfg, 'auditor', 'system', 'draft')
        models.call(cfg, 'auditor', 'system', 'draft')
    data = json.loads((tmp_path / 'usage.json').read_text(encoding='utf-8'))
    assert len(data['requests']) == 4
    assert [r['received'] for r in data['requests']] == [True, True, False, True]
    summary = (tmp_path / 'usage-summary.txt').read_text(encoding='utf-8')
    assert 'Input tokens: 220' in summary and 'Output tokens: 8,212' in summary
    assert 'Total tokens: 8,432' in summary
    assert '1 startup samples' in summary and 'incomplete for 2 attempts' in summary
    assert 'unavailable through this connection' in summary
    assert SECRET not in json.dumps(data) + summary and SOURCE not in json.dumps(data)
    assert http.request.call_count == 4  # No balance request to an unsupported provider.


def test_usage_is_saved_before_post_and_before_envelope_validation(tmp_path):
    cfg = config()
    def response(*args, **kwargs):
        saved = json.loads((tmp_path / 'usage.json').read_text(encoding='utf-8'))
        assert not saved['requests'][-1]['received']
        return {'usage': {'prompt_tokens': 22, 'completion_tokens': 7}}  # No choices.
    models = app.Models(Mock(request=Mock(side_effect=response)))
    with app.UsageTracker(tmp_path, models, {'translator': cfg}):
        with pytest.raises(app.ResponseValidationError):
            models.call(cfg, 'translator', 'system', 'source')
    data = json.loads((tmp_path / 'usage.json').read_text(encoding='utf-8'))
    assert data['requests'][0]['tokens']['total'] == 29


def test_resume_and_reexport_preserve_totals_without_recounting(tmp_path):
    cfg = config()
    models = app.Models(Mock(request=Mock(return_value=envelope(usage={'prompt_tokens': 20, 'completion_tokens': 5}))))
    with app.UsageTracker(tmp_path, models, {'translator': cfg}):
        models.call(cfg, 'translator', 'system', 'source')
    before = (tmp_path / 'usage.json').read_bytes()
    with app.UsageTracker(tmp_path, models, {'translator': cfg}, history_incomplete=True) as resumed:
        assert 'Total tokens: 25' in resumed.summary()
        assert not resumed.data['history_incomplete']
    assert (tmp_path / 'usage.json').read_bytes() == before
    assert models.http.request.call_count == 1


def test_usage_write_failure_prevents_post(tmp_path):
    cfg, http = config(), Mock()
    tracker = app.UsageTracker(tmp_path, None, {'translator': cfg})
    models = app.Models(http, tracker)
    with patch.object(app, 'atomic_write', side_effect=OSError('disk unavailable')), pytest.raises(OSError):
        models.call(cfg, 'translator', 'system', 'source')
    http.request.assert_not_called()


def test_legacy_run_does_not_invent_past_usage(tmp_path):
    cfg = config()
    tracker = app.UsageTracker(tmp_path, Mock(), {'translator': cfg}, history_incomplete=True)
    assert 'Earlier requests made before usage tracking are not included' in tracker.summary()


@pytest.mark.parametrize('data', [[], {'version': 2}, {'version': 1, 'history_incomplete': False, 'requests': [None]}])
def test_corrupt_usage_is_not_reset(tmp_path, data):
    path = tmp_path / 'usage.json'
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(app.TranslationError, match='not overwritten'):
        app.UsageTracker(tmp_path, Mock(), {'translator': config()})
    assert path.read_bytes() == before


BALANCE = {'is_available': False, 'balance_infos': [
    {'currency': 'USD', 'total_balance': '0.00', 'granted_balance': '0.00', 'topped_up_balance': '0.00'},
    {'currency': 'CNY', 'total_balance': '1.25', 'granted_balance': '1.00', 'topped_up_balance': '0.25'}]}


def test_deepseek_balance_returns_reported_currencies_without_conversion():
    http = Mock(request=Mock(return_value=BALANCE))
    lines = app.account_balance(http, config('deepseek'))
    assert 'USD 0.00' in lines[0] and 'CNY 1.25' in lines[1] and 'insufficient balance' in lines[2]
    http.request.assert_called_once_with('GET', 'https://api.deepseek.com/user/balance',
                                         {'Authorization': 'Bearer ' + SECRET}, timeout=10)


@pytest.mark.parametrize('provider,base', [('google', None), ('openai', None), ('anthropic', None),
    ('glm', None), ('qwen', None), ('deepseek', 'https://example.invalid/v1')])
def test_unsupported_or_custom_server_never_receives_balance_query(provider, base):
    http = Mock()
    assert 'unavailable' in app.account_balance(http, config(provider, base))[0]
    http.request.assert_not_called()


def test_completed_deepseek_resume_never_asks_for_a_key_or_makes_request():
    cfg, http = config('deepseek'), Mock()
    cfg.key = ''
    assert 'no API key needed' in app.account_balance(http, cfg)[0]
    http.request.assert_not_called()


@pytest.mark.parametrize('reply', [app.APIError(500, SECRET), {}, {'is_available': True, 'balance_infos': []},
    {'is_available': True, 'balance_infos': [{'currency': 'USD', 'total_balance': SECRET}]}])
def test_balance_failure_is_nonfatal_and_does_not_expose_provider_body(reply):
    http = Mock()
    if isinstance(reply, Exception):
        http.request.side_effect = reply
    else:
        http.request.return_value = reply
    text = '\n'.join(app.account_balance(http, config('deepseek')))
    assert 'unavailable' in text and SECRET not in text


def test_balance_report_runs_on_interruption_once_for_shared_account(tmp_path):
    cfg = config('deepseek')
    models = app.Models(Mock(request=Mock(return_value=BALANCE)))
    with pytest.raises(KeyboardInterrupt):
        with app.UsageTracker(tmp_path, models, dict.fromkeys(app.ROLES, cfg)):
            raise KeyboardInterrupt()
    models.http.request.assert_called_once()
    assert 'Available balance: USD 0.00' in (tmp_path / 'usage-summary.txt').read_text(encoding='utf-8')
    assert models.usage is None


def test_catalog_selection_reprompts_after_no_match_and_has_no_preset(capsys):
    models = Mock(catalog=Mock(return_value=['future-a', 'future-b']))
    with patch('builtins.input', side_effect=['yes', 'google', 'missing', 'future', '2']), \
            patch.object(app, 'key_for', return_value=SECRET):
        configs = app.configure(models, False)
    assert configs['translator'].model == 'future-b'
    assert configs['translator'].output_limit == app.Config('google', '', '').output_limit
    text = capsys.readouterr().out
    assert 'No models matched' in text and 'Preset' not in text


def test_failed_catalog_allows_exact_id_without_restart():
    models = Mock(catalog=Mock(side_effect=app.APIError(503, 'Unavailable')))
    with patch('builtins.input', side_effect=['yes', 'google', 'future-model']), \
            patch.object(app, 'key_for', return_value=SECRET):
        assert app.configure(models, False)['translator'].model == 'future-model'


def test_v5_checkpoint_migrates_without_changing_model_or_budget(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text(SOURCE, encoding='utf-8')
    cfg, settings = config(), app.Settings(language='Spanish')
    chunks, configs = [app.text_blocks(SOURCE)], dict.fromkeys(app.ROLES, cfg)
    current = app.identity_for(source, chunks, configs, settings)
    previous = dict(current, version='cicero-reliable-5')
    checkpoint = app.Checkpoint(tmp_path, previous)
    checkpoint.data['stages'] = {'0:translation': {'text': DRAFT, 'seconds': 1}}
    checkpoint.data['pending'] = '0:fluency'
    checkpoint.save()
    original = checkpoint.path.read_bytes()
    migrated = app.Checkpoint(tmp_path, current)
    assert migrated.data['pending'] == '0:fluency'
    assert migrated.data['stages'] == checkpoint.data['stages']
    assert migrated.data['identity']['roles'] == previous['roles']
    assert (tmp_path / 'checkpoint.before-usage-update.json').read_bytes() == original


def test_main_prints_usage_and_real_balance_when_exhausted(tmp_path, capsys):
    import httpx
    source = tmp_path / 'source.txt'
    source.write_text(SOURCE, encoding='utf-8')
    cfg, calls = config('deepseek'), []
    def handler(request):
        calls.append(request)
        if request.method == 'POST':
            return httpx.Response(402, json={'error': {'message': SECRET}})
        assert str(request.url) == 'https://api.deepseek.com/user/balance'
        return httpx.Response(200, json=BALANCE)
    http = app.HTTP(transport=httpx.MockTransport(handler))
    with patch.object(app, '__file__', str(tmp_path / 'interactive_translator.py')), \
            patch.object(app, 'select_document', return_value=source), patch.object(app, 'HTTP', return_value=http), \
            patch.object(app, 'configure', return_value=dict.fromkeys(app.ROLES, cfg)), \
            patch('builtins.input', side_effect=['no', 'Spanish', 'yes', 'skip', 'no']), \
            pytest.raises(app.APIError):
        app.main()
    text = capsys.readouterr().out
    assert 'Request attempts: 1' in text and 'Total tokens: unavailable' in text
    assert 'Available balance: USD 0.00' in text and 'insufficient balance' in text
    assert SECRET not in text
    assert [r.method for r in calls] == ['POST', 'GET']
    run = next((tmp_path / 'translations').iterdir())
    assert (run / 'usage-summary.txt').exists() and (run / 'translation.partial.txt').exists()
    assert json.loads((run / 'checkpoint.json').read_text(encoding='utf-8'))['pending'] == '0:translation'


def test_balance_failure_does_not_replace_original_translation_failure(tmp_path):
    cfg, http = config('deepseek'), Mock(request=Mock(side_effect=app.APIError(500, SECRET)))
    with pytest.raises(app.ResponseValidationError, match='original'):
        with app.UsageTracker(tmp_path, app.Models(http), {'translator': cfg}):
            raise app.ResponseValidationError('original error')
    assert 'Balance: unavailable' in (tmp_path / 'usage-summary.txt').read_text(encoding='utf-8')
