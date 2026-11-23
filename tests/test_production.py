"""Production-surface tests: authorization gate, audit trail, id validation,
preflight doctor, and CLI dispatch.

Offline only. These cover the parts a real operator touches before any
collector runs.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import osint  # noqa: E402
from core import audit, doctor, storage  # noqa: E402


# --------------------------------------------------------------------------
# storage: ids reach the filesystem, so they must be validated
# --------------------------------------------------------------------------
@pytest.mark.parametrize('bad', [
    '', '   ', '..', '../etc', 'a/b', 'a\\b', '.hidden', '-flag', 'x' * 200,
])
def test_validate_inv_id_rejects_traversal_and_junk(bad):
    with pytest.raises(ValueError):
        storage.validate_inv_id(bad)


@pytest.mark.parametrize('good', [
    '2026-11-24_example.com', 'case_1', 'A1', 'x' * 120,
])
def test_validate_inv_id_accepts_plain_ids(good):
    assert storage.validate_inv_id(good) == good


def test_inv_path_rejects_traversal():
    with pytest.raises(ValueError):
        storage.inv_path('../../secrets')


def test_data_dir_is_outside_the_source_tree(monkeypatch):
    monkeypatch.setenv('OSINT_DATA_DIR', r'C:\tmp\osint-data')
    assert storage.data_dir() == os.path.abspath(r'C:\tmp\osint-data')


# --------------------------------------------------------------------------
# audit trail
# --------------------------------------------------------------------------
def test_audit_appends_jsonl_with_authorization_state(tmp_path):
    audit.record(str(tmp_path), action='investigate', target='acme.test',
                 target_type='domain', target_type_inferred=False,
                 authorized=True, investigation_id='case-1')
    audit.record(str(tmp_path), action='investigate', target='other.test',
                 target_type='domain', target_type_inferred=True,
                 authorized=False, investigation_id='case-2')

    path = audit.audit_path(str(tmp_path))
    with open(path, encoding='utf-8') as f:
        lines = [ln for ln in f if ln.strip()]
    assert len(lines) == 2, 'each run must append exactly one record'

    records = audit.tail(str(tmp_path), 10)
    assert records[0]['target'] == 'acme.test'
    assert records[0]['authorization_acknowledged'] is True
    assert records[1]['authorization_acknowledged'] is False
    assert records[0]['target_type_inferred'] is False
    assert records[0]['app_version'] == '0.2.1'


def test_audit_tail_tolerates_a_corrupt_line(tmp_path):
    path = audit.audit_path(str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('{"action": "ok"}\nnot json\n')
    assert [r['action'] for r in audit.tail(str(tmp_path))] == ['ok']


def test_audit_never_truncates_history(tmp_path):
    for i in range(3):
        audit.record(str(tmp_path), action='investigate', target=f't{i}.test')
    assert len(audit.tail(str(tmp_path), 50)) == 3


# --------------------------------------------------------------------------
# CLI: authorization gate and dispatch
# --------------------------------------------------------------------------
def test_cli_refuses_unacknowledged_investigation(monkeypatch):
    monkeypatch.delenv('OSINT_AUTHORIZED', raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    code = osint.main(['investigate', 'example.com'])
    assert code == 3


def test_cli_flag_and_env_satisfy_the_gate(monkeypatch):
    monkeypatch.delenv('OSINT_AUTHORIZED', raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    assert osint._authorized_or_explain({'authorized'}, interactive=False) is True
    monkeypatch.setenv('OSINT_AUTHORIZED', '1')
    assert osint._authorized_or_explain(set(), interactive=False) is True


def test_cli_interactive_gate_requires_yes(monkeypatch):
    monkeypatch.delenv('OSINT_AUTHORIZED', raising=False)
    monkeypatch.setattr('builtins.input', lambda *_: 'no')
    assert osint._authorized_or_explain(set(), interactive=True) is False
    monkeypatch.setattr('builtins.input', lambda *_: 'yes')
    assert osint._authorized_or_explain(set(), interactive=True) is True


def test_cli_exit_codes_for_usage_errors(capsys):
    assert osint.main(['nonsense']) == 2
    assert osint.main(['dns']) == 2
    assert osint.main(['report']) == 2
    assert 'unknown command' in capsys.readouterr().err


def test_cli_help_and_version(capsys):
    assert osint.main(['--help']) == 0
    assert 'osint doctor' in capsys.readouterr().out
    assert osint.main(['version']) == 0
    assert '0.2.1' in capsys.readouterr().out


def test_cli_report_rejects_traversal(capsys):
    assert osint.main(['report', '../../etc/passwd']) == 2
    assert 'invalid investigation id' in capsys.readouterr().err


def test_split_flags_handles_type_forms():
    assert osint._split_flags(['investigate', '--deep', '--type', 'org', 'Acme']) == \
        ({'deep'}, ['investigate', 'Acme'], 'org')
    assert osint._split_flags(['investigate', 'Acme', '--type=domain']) == \
        (set(), ['investigate', 'Acme'], 'domain')


# --------------------------------------------------------------------------
# doctor / preflight
# --------------------------------------------------------------------------
def test_doctor_report_shape_and_exit_code(monkeypatch):
    monkeypatch.setattr(doctor, '_probe', lambda url, timeout=3: (True, 'HTTP 200'))
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr(doctor, '_writable', lambda path: (True, path))
    checks = doctor.run_checks()
    assert checks and all({'name', 'status', 'detail', 'fix'} <= set(c) for c in checks)
    text = doctor.format_report(checks)
    assert 'preflight' in text
    assert doctor.exit_code(checks) in (0, 1)


def test_doctor_marks_missing_search_as_blocking(monkeypatch):
    monkeypatch.setattr(doctor, '_probe', lambda url, timeout=3: (False, 'URLError'))
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: None)
    monkeypatch.setattr(doctor, '_writable', lambda path: (True, path))
    checks = doctor.run_checks()
    search = next(c for c in checks if c['name'].startswith('searxng'))
    assert search['status'] == 'fail' and 'services up' in search['fix']
    assert doctor.exit_code(checks) == 1


# --------------------------------------------------------------------------
# report: authorization must be visible in the artifact
# --------------------------------------------------------------------------
def test_report_states_authorization(tmp_path, monkeypatch):
    from core import report

    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('acme.test', 'domain', ['dns'],
                                        authorized=True)
    reps = report.write_reports(meta, [], {'dns': 'ok'}, [], [], {})
    with open(reps['markdown'], encoding='utf-8') as f:
        text = f.read()
    assert 'Authorization: acknowledged' in text
    assert 'case:' in text and meta['id'] in text


def test_report_flags_unrecorded_authorization(tmp_path, monkeypatch):
    from core import report

    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('acme.test', 'domain', ['dns'])
    reps = report.write_reports(meta, [], {'dns': 'ok'}, [], [], {})
    with open(reps['markdown'], encoding='utf-8') as f:
        text = f.read()
    assert 'not recorded' in text and '--authorized' in text


def test_findings_json_roundtrips_non_latin(tmp_path, monkeypatch):
    from core import report

    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('acme.test', 'domain', ['dns'], authorized=True)
    finding = {'tool': 'dns', 'value': 'ঢাকা — 1.2.3.4', 'source': '',
               'class': 'FACT', 'relevance': 'direct', 'level': 'CONFIRMED'}
    reps = report.write_reports(meta, [finding], {'dns': 'ok'}, [], [], {})
    with open(reps['json'], encoding='utf-8') as f:
        payload = json.load(f)
    assert payload['findings'][0]['value'] == 'ঢাকা — 1.2.3.4'
    assert payload['meta']['authorized'] is True


def test_next_steps_names_service_fix_for_down_search():
    from core import orchestrator
    steps = orchestrator.next_steps({'searxng': 'unreachable', 'dns': 'ok',
                                     'whois': "error: No module named 'dns'"})
    joined = '\n'.join(steps)
    assert 'searxng not running' in joined and 'osint services up' in joined
    assert 'whois failed' in joined and 'python-whois' in joined


def test_next_steps_empty_when_all_sources_ok():
    from core import orchestrator
    assert orchestrator.next_steps({'dns': 'ok', 'whois': 'ok'}) == []


def test_report_includes_next_steps(tmp_path, monkeypatch):
    from core import report

    monkeypatch.setattr(storage, 'INV', str(tmp_path))
    meta = storage.create_investigation('acme.test', 'domain', ['searxng'], authorized=True)
    reps = report.write_reports(meta, [], {'searxng': 'unreachable'}, [], [], {},
                                next_steps=['- searxng not running → start it: osint services up'])
    with open(reps['markdown'], encoding='utf-8') as f:
        text = f.read()
    assert 'Next steps to restore missing sources' in text
    assert 'osint services up' in text
