"""Offline unit tests for the collection pipeline.

No network, no services, no Ollama: everything here runs on any machine.
Focus is on the parts that were untested in v0.2.0 -- target typing,
relevance-gated confidence, provenance merging, and UTF-8 output.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import detect, process, report, storage


# --------------------------------------------------------------------------
# target typing
# --------------------------------------------------------------------------
@pytest.mark.parametrize('target,expected', [
    ('https://example.com/path', 'url'),
    ('http://x.test', 'url'),
    ('someone@example.com', 'email'),
    ('8.8.8.8', 'ip'),
    ('2001:4860:4860::8888', 'ip'),
    ('example.com', 'domain'),
    ('sub.example.co.uk', 'domain'),
    ('@handle', 'username'),
    ('sherlock', 'username'),
    ('Bangladesh Bank', 'organization'),
    ('A Persons Name', 'organization'),
])
def test_detect_target(target, expected):
    assert detect.detect_target(target) == expected


def test_detect_target_rejects_empty():
    with pytest.raises(ValueError):
        detect.detect_target('   ')


def test_normalize_type_aliases_and_errors():
    assert detect.normalize_type('Org') == 'organization'
    assert detect.normalize_type('organisation') == 'organization'
    assert detect.normalize_type('host') == 'domain'
    with pytest.raises(ValueError):
        detect.normalize_type('person')


def test_type_note_flags_inferred_organization():
    note = detect.type_note('A Persons Name', 'organization')
    assert note and 'inferred' in note and '--type' in note
    assert detect.type_note('A Persons Name', 'organization', forced=True) is None
    assert detect.type_note('example.com', 'domain') is None


# --------------------------------------------------------------------------
# relevance and confidence
# --------------------------------------------------------------------------
def test_relevance_of_direct_partial_none():
    assert process.relevance_of('Acme — https://acme.test/p', '', 'acme') == 'direct'
    assert process.relevance_of('Public, John Q. profile', '', 'John Q Public') == 'partial'
    assert process.relevance_of('Calcutta High Court cause list', '', 'John Q Public') == 'none'
    assert process.relevance_of('anything', '', '') == 'unknown'


def test_searxng_results_are_relevance_gated():
    data = {'status': 'ok', 'results': [
        {'title': 'Acme Corp official site', 'url': 'https://acme.test',
         'content': 'Acme Corp homepage'},
        {'title': 'Calcutta High Court cause list', 'url': 'https://court.test/c.pdf',
         'content': 'unrelated matter'},
    ]}
    findings = process.to_findings('searxng', data, target='Acme')
    direct = [f for f in findings if f['relevance'] == 'direct']
    none = [f for f in findings if f['relevance'] == 'none']
    assert len(direct) == 1 and len(none) == 1
    assert direct[0]['class'] == 'DIRECTLY OBSERVED'
    assert none[0]['class'] == 'UNVERIFIED'
    # The v0.2.0 bug: unrelated hits scored 0.8 / "MEDIUM CONFIDENCE".
    assert process.confidence_score(none[0]) == 0.0
    assert process.level_of(none[0]) == 'UNVERIFIED'


def test_direct_collectors_are_relevance_direct():
    findings = process.to_findings('dns', {'records': {'A': ['1.2.3.4']}}, target='example.com')
    assert findings and all(f['relevance'] == 'direct' for f in findings)


def test_confidence_blends_class_and_relevance():
    assert process.confidence_score({'class': 'FACT', 'relevance': 'direct'}) == 0.95
    assert process.confidence_score({'class': 'DIRECTLY OBSERVED', 'relevance': 'partial'}) == 0.52
    assert process.confidence_score({'class': 'DIRECTLY OBSERVED', 'relevance': 'none'}) == 0.0


def test_level_of_promotes_only_when_correlated_and_direct():
    assert process.level_of({'class': 'DIRECTLY OBSERVED', 'relevance': 'direct',
                             'tool': 'dns', 'tools': ['dns', 'whois']}) == 'HIGH CONFIDENCE'
    assert process.level_of({'class': 'DIRECTLY OBSERVED', 'relevance': 'partial',
                             'tool': 'searxng', 'tools': ['searxng']}) == 'LOW CONFIDENCE'
    assert process.level_of({'class': 'DIRECTLY OBSERVED', 'relevance': 'none'}) == 'UNVERIFIED'


# --------------------------------------------------------------------------
# dedupe / correlate
# --------------------------------------------------------------------------
def test_dedupe_collapses_same_tool_and_value():
    a = {'tool': 'dns', 'value': 'A: 1.1.1.1', 'class': 'FACT', 'relevance': 'direct'}
    b = dict(a, value='a: 1.1.1.1 ')
    assert len(process.dedupe([a, b])) == 1


def test_correlate_records_full_provenance_and_worst_relevance():
    a = {'tool': 'dns', 'value': 'X', 'source': 's1',
         'class': 'DIRECTLY OBSERVED', 'relevance': 'direct'}
    b = {'tool': 'whois', 'value': 'x', 'source': 's2',
         'class': 'DIRECTLY OBSERVED', 'relevance': 'none'}
    out = process.correlate(process.dedupe([a, b]))
    assert len(out) == 1
    merged = out[0]
    assert merged['tools'] == ['dns', 'whois']
    assert set(merged['sources']) == {'s1', 's2'}
    assert merged['relevance'] == 'none'
    # Two unrelated hits agreeing is not corroboration.
    assert merged['class'] != 'CORRELATED'


def test_correlate_promotes_relevant_agreement():
    a = {'tool': 'dns', 'value': 'X', 'source': 's1',
         'class': 'DIRECTLY OBSERVED', 'relevance': 'direct'}
    b = {'tool': 'whois', 'value': 'x', 'source': 's2',
         'class': 'DIRECTLY OBSERVED', 'relevance': 'direct'}
    merged = process.correlate([a, b])[0]
    assert merged['class'] == 'CORRELATED'


# --------------------------------------------------------------------------
# entity extraction
# --------------------------------------------------------------------------
def test_extract_entities_skips_placeholder_domains():
    findings = [{'tool': 'searxng', 'value': 'see example.com and realcorp.co.uk', 'source': ''}]
    values = {e['value'] for e in process.extract_entities(findings, 'acme')}
    assert 'example.com' not in values
    assert 'realcorp.co.uk' in values


# --------------------------------------------------------------------------
# storage + report output encoding
# --------------------------------------------------------------------------
def _finding(value):
    return {'tool': 'searxng', 'value': value, 'source': 'https://example.test',
            'class': 'DIRECTLY OBSERVED', 'relevance': 'direct',
            'evidence_url': 'https://example.test',
            'observed_utc': '2026-01-01T00:00:00+00:00',
            'confidence': 0.8, 'level': 'MEDIUM CONFIDENCE'}


def test_report_writes_utf8_for_non_latin_content(tmp_path, monkeypatch):
    """Regression: unencoded writes crash with UnicodeEncodeError on cp1252 hosts."""
    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('Acme — test', 'organization', ['searxng'])
    findings = [_finding('টাসনিম — https://example.test')]
    reps = report.write_reports(meta, findings, {'searxng': 'ok'}, [], [], {})

    with open(reps['markdown'], encoding='utf-8') as f:
        markdown = f.read()
    assert 'টাসনিম' in markdown

    with open(reps['json'], encoding='utf-8') as f:
        payload = json.load(f)
    assert payload['findings'][0]['value'].startswith('টাসনিম')


def test_graph_json_is_utf8(tmp_path):
    for sub in ('graph', 'reports'):
        os.makedirs(os.path.join(tmp_path, sub), exist_ok=True)
    p = report.build_graph_json(str(tmp_path), 'Acme — gráfico', [_finding('x')])
    with open(p, encoding='utf-8') as f:
        assert json.load(f)['nodes'][0]['label'] == 'Acme — gráfico'


def test_report_separates_unrelated_results(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('acme', 'organization', ['searxng'])
    noise = [{'tool': 'searxng', 'value': 'Court cause list — https://court.test',
              'source': 'https://court.test', 'class': 'UNVERIFIED',
              'relevance': 'none', 'confidence': 0.0, 'level': 'UNVERIFIED'}]
    reps = report.write_reports(meta, [_finding('Acme site')], {'searxng': 'ok'},
                                [], [], {}, noise=noise)
    with open(reps['markdown'], encoding='utf-8') as f:
        markdown = f.read()
    assert 'Excluded: unrelated search results (1)' in markdown
    assert 'Court cause list' in markdown


def test_report_surfaces_inferred_type_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation(
        'A Persons Name', 'organization', ['searxng'],
        type_inferred=True,
        type_note=detect.type_note('A Persons Name', 'organization'))
    reps = report.write_reports(meta, [_finding('x')], {'searxng': 'ok'}, [], [], {})
    with open(reps['markdown'], encoding='utf-8') as f:
        markdown = f.read()
    assert 'type was inferred' in markdown
    assert '--type' in markdown


# --------------------------------------------------------------------------
# collection budget
# --------------------------------------------------------------------------
def test_collect_phase_honours_its_time_budget(monkeypatch):
    """v0.2.0's `fut.result(timeout=30)` was inert because as_completed already
    yielded finished futures; one hung collector stalled the whole run."""
    import time

    from core import orchestrator

    def hang(tool, target, sources):
        time.sleep(1.5)
        return {'ok': True}

    monkeypatch.setattr(orchestrator, 'collect_one', hang)
    started = time.monotonic()
    raw, status = orchestrator._collect_phase(['dns', 'whois'], 'example.com', {}, 2, 0.2)
    elapsed = time.monotonic() - started

    assert elapsed < 3, f'collection phase ignored its budget ({elapsed:.1f}s)'
    assert status == {'dns': 'error: timeout', 'whois': 'error: timeout'}
    assert 'budget' in raw['dns']['error']


# --------------------------------------------------------------------------
# end-to-end orchestration (no network)
# --------------------------------------------------------------------------
def test_investigate_end_to_end_offline(tmp_path, monkeypatch):
    from core import orchestrator

    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    monkeypatch.setattr(orchestrator, 'load_sources', lambda: {})

    def fake_collect(tool, target, sources):
        if tool == 'searxng':
            return {'status': 'ok', 'results': [
                {'title': 'Acme Corp', 'url': 'https://acme.test', 'content': 'Acme Corp'},
                {'title': 'Court cause list', 'url': 'https://court.test/c',
                 'content': 'no match here'}]}
        if tool == 'dns':
            return {'records': {'A': ['1.2.3.4']}}
        if tool == 'spiderfoot':
            return {'note': 'probe', 'status': 'running'}
        return {'status': 'unavailable'}

    monkeypatch.setattr(orchestrator, 'collect_one', fake_collect)

    result = orchestrator.investigate('acme.com', timeout=5)

    values = [f['value'] for f in result['findings']]
    assert result['type'] == 'domain'
    assert any('Acme Corp' in v for v in values), values
    assert not any('Court cause list' in v for v in values), 'unrelated hit leaked into findings'
    assert len(result['noise']) == 1
    assert result['status']['spiderfoot'] == 'probe-only'
    assert all(f.get('confidence') is not None for f in result['findings'])

    with open(result['reports']['markdown'], encoding='utf-8') as f:
        markdown = f.read()
    assert 'Excluded: unrelated search results (1)' in markdown
    assert 'Court cause list' in markdown

    manifest = os.path.join(result['meta']['path'], 'logs', 'manifest.json')
    with open(manifest, encoding='utf-8') as f:
        entries = json.load(f)
    assert entries and all(len(e['sha256']) == 64 for e in entries)


def test_investigate_rejects_empty_target():
    from core import orchestrator

    with pytest.raises(ValueError):
        orchestrator.investigate('   ')
