"""Preflight checks: can this installation actually run an investigation?

`osint doctor` prints these so a new user learns what is broken and how to fix
it, instead of discovering it from a thin report.
"""
import importlib
import os
import shutil
import subprocess
import sys
import urllib.request

from core.storage import data_dir
from core.version import APP_VERSION

REQUIRED_MODULES = [
    ('requests', 'pip install requests'),
    ('yaml', 'pip install pyyaml'),
    ('dns.resolver', 'pip install dnspython'),
    ('whois', 'pip install python-whois'),
    ('ipwhois', 'pip install ipwhois'),
    ('PIL', 'pip install Pillow'),
]

OPTIONAL_TOOLS = [
    ('exiftool', 'winget install -e --id OliverBetz.ExifTool'),
    ('nmap', 'winget install -e --id Insecure.Nmap'),
    ('docker', 'https://docs.docker.com/get-docker/  # must have docker daemon running'),
]


def _entry(name, status, detail, fix=''):
    return {'name': name, 'status': status, 'detail': detail, 'fix': fix}


def _docker_daemon_running() -> tuple:
    if not shutil.which('docker'):
        return False, 'docker CLI not on PATH'
    try:
        r = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=20)
        return r.returncode == 0, 'daemon running' if r.returncode == 0 else r.stderr.strip()[:100]
    except Exception as e:
        return False, type(e).__name__


def _probe(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500, f'HTTP {r.status}'
    except Exception as e:
        return False, type(e).__name__


def _writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, '.write-test')
        with open(probe, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(probe)
        return True, path
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def run_checks(search_url='http://127.0.0.1:8888',
               spiderfoot_url='http://127.0.0.1:5001') -> list:
    checks = []

    if sys.version_info >= (3, 11):
        checks.append(_entry('python', 'ok', sys.version.split()[0]))
    else:
        checks.append(_entry('python', 'fail', sys.version.split()[0],
                             'Install Python 3.11 or newer'))

    missing = []
    for mod, fix in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append((mod, fix))
    if missing:
        checks.append(_entry('dependencies', 'fail',
                             'missing: ' + ', '.join(m for m, _ in missing),
                             ' ; '.join(sorted({f for _, f in missing}))))
    else:
        checks.append(_entry('dependencies', 'ok', f'{len(REQUIRED_MODULES)} imports present'))

    ok, detail = _writable(data_dir())
    checks.append(_entry('data directory', 'ok' if ok else 'fail', detail,
                         '' if ok else 'Set OSINT_DATA_DIR to a writable path'))

    ok, detail = _probe(search_url)
    checks.append(_entry(
        'searxng (search)', 'ok' if ok else 'fail',
        f'{search_url} \u2014 {detail}',
        '' if ok else ('Start it: osint services up  (uses Docker if the native '
                       'source is not vendored)')))

    ok, detail = _probe(spiderfoot_url)
    checks.append(_entry(
        'spiderfoot (optional)', 'ok' if ok else 'warn',
        f'{spiderfoot_url} \u2014 {detail}',
        '' if ok else 'Optional: the CLI does not submit scans to it'))

    ok, detail = _docker_daemon_running()
    checks.append(_entry(
        'docker daemon', 'ok' if ok else 'warn',
        f'docker CLI: {detail}', '' if ok else 'Start Docker Desktop or docker service'))

    for tool, fix in OPTIONAL_TOOLS:
        found = shutil.which(tool)
        checks.append(_entry(f'tool: {tool}', 'ok' if found else 'warn',
                             found or 'not on PATH', '' if found else fix))
    return checks


_STATUS_LABEL = {'ok': 'OK  ', 'warn': 'WARN', 'fail': 'FAIL'}


def format_report(checks) -> str:
    lines = [f'OSINT Workstation {APP_VERSION} \u2014 preflight', '']
    for c in checks:
        lines.append(f'  [{_STATUS_LABEL.get(c["status"], "?")}] {c["name"]:<24} {c["detail"]}')
        if c['fix'] and c['status'] != 'ok':
            lines.append(f'         {"":<24} fix: {c["fix"]}')
    failures = [c for c in checks if c['status'] == 'fail']
    warnings = [c for c in checks if c['status'] == 'warn']
    lines.append('')
    if failures:
        lines.append(f'{len(failures)} blocking problem(s). Investigate results will be incomplete.')
    else:
        lines.append('Ready. ' + (f'{len(warnings)} warning(s).' if warnings else 'No warnings.'))
    return '\n'.join(lines)


def exit_code(checks) -> int:
    return 1 if any(c['status'] == 'fail' for c in checks) else 0