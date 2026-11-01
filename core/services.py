"""Native (no-Docker) service manager for SearXNG + SpiderFoot.

Both run as detached processes from the project folder:
  SearXNG     tools/searxng          venv services/venv-searxng      port 8888
  SpiderFoot  tools/spiderfoot-src   venv services/venv-spiderfoot   port 5001

State (PIDs) in services/services.json; logs in services/logs/.
All paths are project-relative — the operation lives entirely under the repo.
"""
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(BASE, 'services')
STATE_FILE = os.path.join(SERVICES_DIR, 'services.json')
LOG_DIR = os.path.join(SERVICES_DIR, 'logs')

SERVICES = {
    'searxng': {
        'port': 8888,
        'url': 'http://127.0.0.1:8888',
        'cwd': os.path.join(BASE, 'tools', 'searxng'),
        'python': os.path.join(BASE, 'services', 'venv-searxng', 'Scripts', 'python.exe'),
        'args': ['-m', 'searx.webapp'],
        'env': {
            'SEARXNG_SETTINGS_PATH': os.path.join(SERVICES_DIR, 'searxng-settings.yml'),
        },
    },
    'spiderfoot': {
        'port': 5001,
        'url': 'http://127.0.0.1:5001',
        'cwd': os.path.join(BASE, 'tools', 'spiderfoot-src'),
        'python': os.path.join(BASE, 'services', 'venv-spiderfoot', 'Scripts', 'python.exe'),
        'args': ['sf.py', '-l', '127.0.0.1:5001'],
        'env': {
            'SPIDERFOOT_DATA': os.path.join(SERVICES_DIR, 'spiderfoot-data'),
            'SPIDERFOOT_CACHE': os.path.join(SERVICES_DIR, 'spiderfoot-data', 'cache'),
            'SPIDERFOOT_LOGS': os.path.join(SERVICES_DIR, 'spiderfoot-data', 'log'),
        },
    },
}


def _load_state():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {}


def _save_state(state):
    os.makedirs(SERVICES_DIR, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _alive(pid):
    """Windows-safe liveness check.

    NOTE: os.kill(pid, 0) must NOT be used here — on Windows it maps to
    TerminateProcess (killing the process with exit code 0) and also raises
    spurious WinError 87. Use OpenProcess/GetExitCodeProcess instead.
    """
    if not pid:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _listener_pid(port):
    """Return the PID listening on 127.0.0.1:<port>, or None (via netstat)."""
    try:
        out = subprocess.run(['netstat', '-ano'], capture_output=True,
                             text=True, timeout=15).stdout
    except Exception:
        return None
    suffix = f':{port}'
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == 'TCP' and parts[3] == 'LISTENING':
            local = parts[1]
            if local.endswith(suffix) and (local.startswith('127.0.0.1') or local.startswith('0.0.0.0') or local.startswith('[::]')):
                try:
                    return int(parts[4])
                except ValueError:
                    continue
    return None


def _probe(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def status():
    """Return {'searxng': 'running'|'stopped', 'spiderfoot': ...}."""
    state = _load_state()
    out = {}
    for name, cfg in SERVICES.items():
        listener = _listener_pid(cfg['port'])
        if _probe(cfg['url']):
            # refresh recorded pid to the actual listener (venv stubs re-parent)
            if listener and state.get(name, {}).get('pid') != listener:
                state[name] = {'pid': listener}
                _save_state(state)
            out[name] = 'running'
        elif listener and _alive(listener):
            out[name] = 'starting?'
        else:
            out[name] = 'stopped'
    return out


def start(name, wait=45):
    """Start one service detached; wait until its HTTP port answers."""
    cfg = SERVICES[name]
    if _probe(cfg['url']):
        return {'service': name, 'status': 'already-running'}

    if not os.path.exists(cfg['python']):
        return {'service': name, 'status': 'error',
                'error': f"venv missing: {cfg['python']} (run: uv venv + uv pip install)"}
    if not os.path.isdir(cfg['cwd']):
        return {'service': name, 'status': 'error', 'error': f"source missing: {cfg['cwd']}"}

    os.makedirs(LOG_DIR, exist_ok=True)
    log = open(os.path.join(LOG_DIR, f'{name}.log'), 'ab')
    env = {**os.environ, **cfg['env']}
    # DETACHED_PROCESS + no new console window; own process group for clean kill
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [cfg['python'], *cfg['args']],
        cwd=cfg['cwd'], env=env, stdout=log, stderr=log,
        stdin=subprocess.DEVNULL, creationflags=flags,
    )

    deadline = time.time() + wait
    while time.time() < deadline:
        if _probe(cfg['url']):
            # record the actual listening PID, not the venv launcher stub
            listener = _listener_pid(cfg['port']) or proc.pid
            state = _load_state()
            state[name] = {'pid': listener, 'launcher_pid': proc.pid}
            _save_state(state)
            return {'service': name, 'status': 'running', 'pid': listener}
        if proc.poll() is not None:
            return {'service': name, 'status': 'crashed', 'pid': proc.pid,
                    'log': os.path.join(LOG_DIR, f'{name}.log')}
        time.sleep(1.5)
    return {'service': name, 'status': 'timeout', 'pid': proc.pid,
            'log': os.path.join(LOG_DIR, f'{name}.log')}


def stop(name):
    """Stop a service we started (kills listener PID + its tree)."""
    cfg = SERVICES[name]
    state = _load_state()
    pid = state.get(name, {}).get('pid') or _listener_pid(cfg['port'])
    killed = []
    if pid and _alive(pid):
        r = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                           capture_output=True, text=True)
        if r.returncode == 0:
            killed.append(pid)
    # fallback: anything still holding the port
    time.sleep(1)
    leftover = _listener_pid(cfg['port'])
    if leftover and _alive(leftover):
        subprocess.run(['taskkill', '/PID', str(leftover), '/T', '/F'],
                       capture_output=True, text=True)
        killed.append(leftover)
    state.pop(name, None)
    _save_state(state)
    return {'service': name, 'status': 'stopped', 'pids_killed': killed or None}


def start_all():
    return [start(n) for n in SERVICES]


def stop_all():
    return [stop(n) for n in SERVICES]


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    fn = {'status': status, 'up': start_all, 'down': stop_all,
          'start': lambda: start(sys.argv[2]),
          'stop': lambda: stop(sys.argv[2])}.get(cmd)
    if not fn:
        print(__doc__); sys.exit(1)
    print(json.dumps(fn(), indent=2))
