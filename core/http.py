"""Shared HTTP: retries + exponential backoff + pacing + file cache. Never hammers sites."""
import time, hashlib, json, os, threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = {'User-Agent': 'OSINT-Workstation/1.0 (authorized local research; rate-limited polite client)'}
_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'http_cache')
_last_hit: dict = {}
_lock = threading.Lock()
MIN_INTERVAL = 1.1  # seconds between hits to the same host (polite; Nominatim policy compliant)

_session = None
def session():
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(UA)
        retry = Retry(total=2, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=['GET'], raise_on_status=False)
        s.mount('http://', HTTPAdapter(max_retries=retry))
        s.mount('https://', HTTPAdapter(max_retries=retry))
        _session = s
    return _session

def _pace(host: str):
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()

def get(url: str, params=None, timeout=20, use_cache=True, cache_ttl=3600):
    """GET with pacing + retry + optional disk cache. Returns (status, payload_dict_or_text, meta)."""
    from urllib.parse import urlparse
    key = hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    cp = os.path.join(_CACHE, key + '.json')
    if use_cache and os.path.exists(cp):
        try:
            c = json.load(open(cp))
            if time.time() - c['ts'] < cache_ttl:
                return c['status'], c['body'], {'cached': True, 'url': url}
        except Exception:
            pass
    _pace(urlparse(url).netloc)
    try:
        r = session().get(url, params=params, timeout=timeout)
        ctype = r.headers.get('Content-Type', '')
        body = r.json() if 'json' in ctype else r.text
        meta = {'cached': False, 'url': r.url, 'http': r.status_code}
        if use_cache and r.status_code == 200:
            try:
                os.makedirs(_CACHE, exist_ok=True)
                json.dump({'ts': time.time(), 'status': 'ok', 'body': body if isinstance(body, (dict, list)) else body[:8000]},
                          open(cp, 'w'), default=str)
            except Exception:
                pass
        return ('ok' if r.status_code < 400 else f'http_{r.status_code}'), body, meta
    except Exception as e:
        return 'error', None, {'cached': False, 'url': url, 'error': str(e)[:200]}
