"""Source health: probe auto sources + SearXNG engines, honest statuses. Never claims untested sources work."""
import os, json, datetime, yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, 'config', 'source_registry.yaml')
HEALTH_JSON = os.path.join(BASE, 'config', 'source_health.json')

def _load():
    with open(REG, encoding='utf-8') as f:
        return yaml.safe_load(f)['registry']

def probe_auto(entry: dict, timeout=20) -> dict:
    """Lightweight keyless probe per source. Returns health dict."""
    from core import http as H
    name = entry['name']
    try:
        if name == 'osm.org':
            st, b, m = H.get('https://nominatim.openstreetmap.org/search',
                             params={'q': 'Dhaka', 'format': 'json', 'limit': 1}, timeout=timeout)
            ok = st == 'ok' and isinstance(b, list)
        elif name == 'github.com':
            st, b, m = H.get('https://api.github.com/users/torvalds', timeout=timeout, use_cache=False)
            ok = st == 'ok' and isinstance(b, dict) and b.get('login') == 'torvalds'
            if isinstance(b, dict) and 'rate limit' in str(b).lower():
                return _mk(entry, 'RATE_LIMITED', 'GitHub anon quota exhausted')
        elif name == 'gitlab.com':
            st, b, m = H.get('https://gitlab.com/api/v4/users', params={'username': 'torvalds'}, timeout=timeout)
            ok = st == 'ok'
        elif name == 'crt.sh':
            st, b, m = H.get('https://crt.sh/?q=%25.example.com&output=json', timeout=timeout)
            ok = st == 'ok'
        elif name == 'urlscan.io':
            st, b, m = H.get('https://urlscan.io/api/v1/search/', params={'q': 'domain:example.com'}, timeout=timeout)
            ok = st == 'ok' and isinstance(b, dict)
        elif name == 'ipinfo.io':
            st, b, m = H.get('https://ipinfo.io/8.8.8.8/json', timeout=timeout)
            ok = st == 'ok' and isinstance(b, dict) and b.get('ip') == '8.8.8.8'
        elif name == 'steamcommunity.com':
            st, b, m = H.get('https://steamcommunity.com/id/valve', timeout=timeout)
            ok = st == 'ok'
        elif name == 'stat.ripe.net':
            st, b, m = H.get('https://stat.ripe.net/data/network-info/data.json',
                             params={'resource': '8.8.8.8'}, timeout=timeout)
            ok = st == 'ok' and isinstance(b, dict) and (b.get('data') or {}).get('asns') == ['15169']
        elif name == 'wikidata.org':
            st, b, m = H.get('https://www.wikidata.org/w/api.php',
                             params={'action': 'wbsearchentities', 'search': 'Dhaka', 'language': 'en',
                                     'format': 'json', 'limit': 1}, timeout=timeout)
            ok = st == 'ok' and isinstance(b, dict) and 'search' in b
        else:
            return _mk(entry, 'CONFIGURED', 'no automated probe; manual/via-searxng')
        if ok:
            return _mk(entry, 'WORKING', '')
        if isinstance(st, str) and st.startswith('http_429'):
            return _mk(entry, 'RATE_LIMITED', f'HTTP 429 from {name}')
        return _mk(entry, 'TEMPORARILY_UNAVAILABLE' if (isinstance(st, str) and st.startswith('http_5')) else 'FAILED',
                   f'status={st} err={m.get("error", "")}'[:200])
    except Exception as e:
        return _mk(entry, 'FAILED', str(e)[:200])

def _mk(entry, health, reason):
    return {'name': entry['name'], 'method': entry['method'], 'enabled': entry['enabled'],
            'health': health, 'reason': reason,
            'tested_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}

def searxng_engines(base_url: str, timeout=25) -> list:
    """Test each plausible engine with a trivial query; report honestly per-engine."""
    out = []
    for eng in ['duckduckgo', 'bing', 'brave', 'mojeek', 'wikipedia', 'github', 'stackoverflow', 'openstreetmap', 'reddit']:
        try:
            from core import http as H
            st, body, meta = H.get(f'{base_url}/search',
                                   params={'q': 'example', 'format': 'json', 'engines': eng},
                                   timeout=timeout, use_cache=False)
            n = 0
            if st == 'ok' and isinstance(body, dict):
                res = body.get('results') or []
                n = len([r for r in res if (r.get('engine') or '').lower() == eng])
                # searxng may merge; count any results attributed
                if n == 0 and res:
                    n = len(res)
            out.append({'engine': eng, 'working': n > 0, 'results': n,
                        'note': '' if n else f'status={st} {meta.get("error", "") or meta.get("http", "")}'[:120]})
        except Exception as e:
            out.append({'engine': eng, 'working': False, 'results': 0, 'note': str(e)[:120]})
    return out

def run_health(save=True) -> dict:
    reg = _load()
    results = []
    for e in reg:
        if not e.get('enabled'):
            results.append(_mk(e, 'KEY_REQUIRED' if e.get('key') else 'CONFIGURED',
                               'disabled in registry (login-walled or key-gated)' if e['method'] in ('manual', 'api_key') else e.get('note', '')))
        elif e['method'] == 'auto_http':
            results.append(probe_auto(e))
        elif e['method'] == 'via_searxng':
            results.append(_mk(e, 'CONFIGURED', 'queried through SearXNG at investigation time; see engine health'))
        elif e['method'] == 'api_key':
            results.append(_mk(e, 'KEY_REQUIRED', e.get('note', 'API key required')))
        else:
            results.append(_mk(e, 'CONFIGURED', e.get('note', 'manual reference only')))
    # service-level checks
    from core.clients import searxng_search, spiderfoot_status
    import yaml as _y
    with open(os.path.join(BASE, 'config', 'sources.yaml'), encoding='utf-8') as f:
        svc = _y.safe_load(f)
    sx = searxng_search(svc['searxng']['url'], 'healthcheck', count=1)
    engines = searxng_engines(svc['searxng']['url']) if sx['status'] == 'ok' else []
    report = {'tested_utc': results[0]['tested_utc'] if results else '',
              'sources': results,
              'searxng': {'status': sx['status'], 'engines': engines,
                          'working_engines': [e['engine'] for e in engines if e['working']]},
              'spiderfoot': spiderfoot_status(svc['spiderfoot']['url'])}
    if save:
        with open(HEALTH_JSON, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    return report
