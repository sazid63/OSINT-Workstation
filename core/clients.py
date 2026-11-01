"""SearXNG + SpiderFoot HTTP clients (graceful when services down)."""
import requests

def searxng_search(base_url: str, query: str, timeout=20, categories='general', count=10):
    try:
        r = requests.get(f"{base_url}/search", params={'q': query, 'format': 'json', 'categories': categories},
                         timeout=timeout, headers={'User-Agent': 'OSINT-Workstation/1.0'})
        r.raise_for_status()
        j = r.json()
        out = []
        for res in (j.get('results') or [])[:count]:
            out.append({'title': res.get('title'), 'url': res.get('url'),
                        'content': res.get('content'), 'engine': res.get('engine'),
                        'source': 'searxng', 'confidence_class': 'DIRECTLY OBSERVED'})
        return {'status': 'ok', 'query': query, 'results': out}
    except Exception as e:
        return {'status': 'unavailable', 'query': query, 'results': [], 'error': str(e)}

def spiderfoot_status(base_url: str, timeout=10):
    try:
        r = requests.get(f"{base_url}/", timeout=timeout)
        return {'status': 'ok' if r.status_code < 500 else 'error', 'http': r.status_code}
    except Exception as e:
        return {'status': 'unavailable', 'error': str(e)}
