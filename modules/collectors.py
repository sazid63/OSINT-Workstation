"""Collectors: DNS, WHOIS/RDAP, certs (crt.sh), IP, URL. All free, no keys."""
import socket, ssl, datetime, re, os
import requests

UA = {'User-Agent': 'OSINT-Workstation/1.0 (authorized local research)'}
# Configurable timeouts (can be overridden via env vars)
DEFAULT_TIMEOUT = int(os.environ.get('OSINT_HTTP_TIMEOUT', '20'))
DNS_LIFETIME = int(os.environ.get('OSINT_DNS_LIFETIME', '10'))
CERT_TIMEOUT = int(os.environ.get('OSINT_CERT_TIMEOUT', '10'))
SUBDOMAIN_LIMIT = int(os.environ.get('OSINT_SUBDOMAIN_LIMIT', '200'))
HARVESTER_LIMIT = int(os.environ.get('OSINT_HARVESTER_LIMIT', '50'))

def mod_dns(target: str):
    import dns.resolver
    out = {'target': target, 'records': {}, 'errors': {}}
    # strip scheme for URLs
    host = re.sub(r'^https?://', '', target).split('/')[0].split(':')[0]
    out['host'] = host
    for rtype in ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA', 'CNAME']:
        try:
            ans = dns.resolver.resolve(host, rtype, lifetime=DNS_LIFETIME)
            out['records'][rtype] = sorted(str(r).strip('"') for r in ans)
        except Exception as e:
            out['errors'][rtype] = str(e)[:120]
    try:
        out['reverse'] = socket.gethostbyaddr(host)[0]
    except Exception as e:
        out['reverse'] = None
        out['errors']['PTR'] = str(e)[:120]
    return out

def mod_whois_rdap(target: str):
    host = re.sub(r'^https?://', '', target).split('/')[0]
    domain = host.split(':')[0]
    if '@' in domain:
        domain = domain.split('@')[-1]
    out = {'target': target, 'domain': domain}
    try:
        import whois
        w = whois.whois(domain)
        out['whois'] = {k: str(v)[:500] for k, v in (dict(w) if w else {}).items()}
    except Exception as e:
        out['whois_error'] = str(e)[:300]
    for kind, url in [('domain', f'https://rdap.org/domain/{domain}'),
                      ('ip', None)]:
        try:
            r = requests.get(url, headers=UA, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                out[f'rdap_{kind}'] = r.json()
            else:
                out[f'rdap_{kind}_http'] = r.status_code
        except Exception as e:
            out[f'rdap_{kind}_error'] = str(e)[:200]
    return out

def mod_cert(target: str):
    host = re.sub(r'^https?://', '', target).split('/')[0].split(':')[0]
    if '@' in host:
        host = host.split('@')[-1]
    base = host.split('.')[-2:] if host.count('.') >= 1 else [host]
    apex = '.'.join(base)
    out = {'target': target, 'apex': apex, 'subdomains': [], 'live_cert': None}
    try:
        r = requests.get(f'https://crt.sh/?q=%25.{apex}&output=json', headers=UA, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            seen = set()
            for e in r.json():
                for n in (e.get('name_value') or '').split('\n'):
                    n = n.strip().lower()
                    if n and '*' not in n:
                        seen.add(n)
            out['subdomains'] = sorted(seen)[:SUBDOMAIN_LIMIT]
        else:
            out['crtsh_http'] = r.status_code
            raise RuntimeError(f'crt.sh http {r.status_code}')
    except Exception as e:
        out['crtsh_error'] = str(e)[:300]
        # fallback: HackerTarget hostsearch (free, no key, same data class)
        try:
            h = requests.get(f'https://api.hackertarget.com/hostsearch/?q={apex}', headers=UA, timeout=DEFAULT_TIMEOUT)
            if h.status_code == 200 and h.text.strip() and 'error' not in h.text.lower()[:60]:
                out['subdomains'] = sorted({l.split(',')[0].strip().lower() for l in h.text.splitlines() if l.strip()})[:SUBDOMAIN_LIMIT]
                out['subdomain_source'] = 'hackertarget hostsearch (fallback)'
            else:
                out['hostsearch_http'] = h.status_code
        except Exception as e2:
            out['hostsearch_error'] = str(e2)[:200]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                c = s.getpeercert()
                out['live_cert'] = {'subject': str(c.get('subject')), 'issuer': str(c.get('issuer')),
                                    'notAfter': c.get('notAfter'), 'san': [x[1] for x in c.get('subjectAltName', [])][:50]}
    except Exception as e:
        out['live_cert_error'] = str(e)[:200]
    return out

def mod_ip(target: str):
    out = {'target': target}
    try:
        out['dns_resolves'] = socket.gethostbyname_ex(target)[2]
    except Exception as e:
        out['dns_error'] = str(e)[:200]
    for name, url in [('hackertarget_geoip', f'https://api.hackertarget.com/geoip/?q={target}'),
                      ('ipapi', f'http://ip-api.com/json/{target}?fields=status,country,regionName,city,isp,org,as,query')]:
        try:
            r = requests.get(url, headers=UA, timeout=DEFAULT_TIMEOUT)
            out[name] = r.text[:2000] if 'hackertarget' in name else r.json()
        except Exception as e:
            out[name + '_error'] = str(e)[:200]
    try:
        from ipwhois import IPWhois
        ip = target if re.match(r'^\d+\.\d+\.\d+\.\d+$', target) else (out.get('dns_resolves') or [None])[0]
        if ip:
            out['rdap_whois'] = IPWhois(ip).lookup_rdap(depth=1)
    except Exception as e:
        out['ipwhois_error'] = str(e)[:300]
    return out

def mod_url(target: str):
    url = target if re.match(r'^https?://', target, re.I) else 'https://' + target
    out = {'url': url, 'checks': {}}
    try:
        r = requests.get(url, headers=UA, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        out['checks'] = {'http': r.status_code, 'final_url': r.url,
                         'server': r.headers.get('Server'), 'powered_by': r.headers.get('X-Powered-By'),
                         'title': (re.search(r'<title>(.*?)</title>', r.text, re.I | re.S).group(1).strip()[:200]
                                   if '<title>' in r.text.lower() else None),
                         'redirect_chain': [h.url for h in r.history]}
    except Exception as e:
        out['error'] = str(e)[:300]
    return out

def mod_email(target: str):
    """Free, no-key checks: domain deliverability signals + GitHub commit search (public)."""
    out = {'target': target, 'local': target.split('@')[0] if '@' in target else target,
           'domain': target.split('@')[-1] if '@' in target else None}
    if out['domain']:
        try:
            out['domain_dns'] = mod_dns(out['domain'])['records']
        except Exception as e:
            out['domain_dns_error'] = str(e)[:200]
    try:
        r = requests.get('https://api.github.com/search/commits',
                         params={'q': target}, headers={**UA, 'Accept': 'application/vnd.github.cloak-preview'},
                         timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            j = r.json()
            out['github_commits'] = [{'repo': (c.get('repository') or {}).get('full_name'),
                                      'sha': c.get('sha')} for c in j.get('items', [])[:5]]
        else:
            out['github_http'] = r.status_code
    except Exception as e:
        out['github_error'] = str(e)[:200]
    out['note'] = 'Breach lookup (HIBP) requires API key — see sources.yaml. No brute-force validation performed.'
    return out

def mod_username(target: str):
    """Fast free check: GitHub + GitLab APIs (no key). Full 400-site sweep via `osint username --full` (sherlock)."""
    u = target.lstrip('@')
    out = {'target': target, 'username': u, 'hits': []}
    import os as _os
    _headers = dict(UA, Accept='application/vnd.github.cloak-preview')
    if _os.environ.get('GITHUB_TOKEN'):
        _headers['Authorization'] = f"Bearer {_os.environ['GITHUB_TOKEN']}"
    for site, url in [('github', f'https://api.github.com/users/{u}'),
                      ('gitlab', f'https://gitlab.com/api/v4/users?username={u}')]:
        try:
            r = requests.get(url, headers=_headers if site == 'github' else UA, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                if site == 'github' and isinstance(j, dict) and j.get('login'):
                    out['hits'].append({'site': 'github', 'url': j.get('html_url'), 'id': j.get('id')})
                elif site == 'gitlab' and isinstance(j, list) and j:
                    out['hits'].append({'site': 'gitlab', 'url': j[0].get('web_url'), 'id': j[0].get('id')})
                else:
                    out.setdefault('misses', []).append(site)
            else:
                out.setdefault('misses', []).append(f'{site}:{r.status_code}')
        except Exception as e:
            out.setdefault('errors', {})[site] = str(e)[:150]
    # full 400-site sweep (best-effort, slow): sherlock binary if on PATH
    out['full_sweep_hint'] = 'Run: sherlock USER --timeout 20  (or: osint.py username USER --full)'
    return out

def mod_metadata(path: str):
    """Local file metadata: ExifTool if present, else Pillow EXIF fallback. Never uploads."""
    import os as _os, hashlib
    out = {'path': path}
    if not _os.path.exists(path):
        return {**out, 'error': 'file not found'}
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    out['sha256'] = h.hexdigest()
    out['size'] = _os.path.getsize(path)
    # try exiftool binary
    import shutil, subprocess, json as _j
    exe = shutil.which('exiftool')
    if exe:
        try:
            r = subprocess.run([exe, '-j', '-n', path], capture_output=True, text=True, timeout=60)
            out['exiftool'] = _j.loads(r.stdout)[0] if r.stdout.strip().startswith('[') else r.stdout[:3000]
            return out
        except Exception as e:
            out['exiftool_error'] = str(e)[:200]
    # Pillow fallback (JPEG/TIFF/PNG/GIF/WebP EXIF)
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        with Image.open(path) as im:
            out['format'] = im.format
            out['dimensions'] = f'{im.width}x{im.height}'
            ex = im.getexif()
            tags = {}
            for k, v in ex.items():
                name = TAGS.get(k, str(k))
                tags[name] = str(v)[:300]
            out['exif'] = tags
            out['exif_reader'] = 'pillow-fallback'
    except Exception as e:
        out['pillow_note'] = f'no image EXIF readable: {str(e)[:150]}'
    return out

def mod_urlscan(target: str):
    """urlscan.io public search (no key): archived scans of domain/URL/IP."""
    from core.http import get
    q = target.replace('https://', '').replace('http://', '').split('/')[0]
    st, body, meta = get('https://urlscan.io/api/v1/search/', params={'q': f'domain:{q}'}, timeout=25)
    out = {'target': target, 'status': st, 'evidence_url': meta.get('url'), 'http': meta.get('http')}
    if st == 'ok' and isinstance(body, dict):
        out['total'] = body.get('total')
        out['scans'] = [{'url': r.get('page', {}).get('url'), 'scan': r.get('_id'),
                         'screenshot': r.get('screenshot')} for r in (body.get('results') or [])[:10]]
    else:
        out['error'] = str(body)[:200] if body else meta.get('error')
    return out

def mod_ipinfo(target: str):
    """ipinfo.io free tier (no key): geo/ASN. Token optional via IPINFO_TOKEN."""
    import os as _os
    from core.http import get
    tok = _os.environ.get('IPINFO_TOKEN', '')
    url = f"https://ipinfo.io/{target}/json" + (f"?token={tok}" if tok else '')
    st, body, meta = get(url, timeout=20)
    return {'target': target, 'status': st, 'evidence_url': meta.get('url'), 'data': body if st == 'ok' else None,
            'error': None if st == 'ok' else str(body)[:200]}

def mod_ripestat(target: str):
    """RIPEstat (RIPE NCC, no key): ASN, announced prefixes for an IP."""
    import socket, re
    from core.http import get
    ip = target if re.match(r'^\d+\.\d+\.\d+\.\d+$', target) else None
    if not ip:
        try:
            ip = socket.gethostbyname(target.split('/')[0].replace('https://', '').replace('http://', ''))
        except Exception as e:
            return {'target': target, 'status': 'error', 'error': f'dns: {e}'[:150]}
    out = {'target': target, 'ip': ip, 'status': 'ok',
           'evidence_url': f'https://stat.ripe.net/8.8.8.8'.replace('8.8.8.8', ip)}
    st, body, _ = get('https://stat.ripe.net/data/network-info/data.json',
                      params={'resource': ip}, timeout=20)
    if st == 'ok' and isinstance(body, dict):
        d = body.get('data') or {}
        out['asns'] = d.get('asns', [])
        out['prefix'] = d.get('prefix')
    else:
        out['status'] = 'error'
        out['error'] = str(body)[:200]
        return out
    for asn in (out.get('asns') or [])[:3]:
        st2, b2, _ = get('https://stat.ripe.net/data/announced-prefixes/data.json',
                         params={'resource': f'AS{asn}'}, timeout=20)
        if st2 == 'ok' and isinstance(b2, dict):
            out.setdefault('announced', {})[f'AS{asn}'] = [
                p.get('prefix') for p in ((b2.get('data') or {}).get('prefixes') or [])[:10]]
    return out

def mod_wikidata(target: str):
    """Wikidata API (no key): structured entity facts for org/person names."""
    from core.http import get
    st, body, meta = get('https://www.wikidata.org/w/api.php',
                         params={'action': 'wbsearchentities', 'search': target, 'language': 'en',
                                 'format': 'json', 'limit': 5}, timeout=20)
    out = {'target': target, 'status': st, 'evidence_url': meta.get('url')}
    if st == 'ok' and isinstance(body, dict):
        out['entities'] = [{'id': e.get('id'), 'label': e.get('label'), 'description': e.get('description'),
                            'url': f"https://www.wikidata.org/wiki/{e.get('id')}"} for e in body.get('search', [])]
    else:
        out['error'] = str(body)[:200] if body else meta.get('error')
    return out

def mod_nominatim(target: str):
    """OSM Nominatim (no key, 1 req/s honored by http layer): geocode org/place."""
    from core.http import get
    st, body, meta = get('https://nominatim.openstreetmap.org/search',
                         params={'q': target, 'format': 'json', 'limit': 5}, timeout=20)
    out = {'target': target, 'status': st, 'evidence_url': meta.get('url')}
    if st == 'ok' and isinstance(body, list):
        out['places'] = [{'name': p.get('display_name'), 'lat': p.get('lat'), 'lon': p.get('lon'),
                          'type': p.get('type')} for p in body]
    else:
        out['error'] = str(body)[:200] if isinstance(body, str) else meta.get('error')
    return out

def mod_steam(username: str):
    """Steam public vanity-URL check only (no auth endpoints)."""
    from core.http import get
    u = username.lstrip('@')
    out = {'target': username, 'hits': []}
    for kind, url in [('vanity', f'https://steamcommunity.com/id/{u}'),
                      ('numeric', f'https://steamcommunity.com/profiles/{u}' if u.isdigit() else None)]:
        if not url:
            continue
        st, body, meta = get(url, timeout=20, use_cache=False)  # no cache: bodies truncate past the error marker
        txt = body if isinstance(body, str) else ''
        if st == 'ok' and 'Steam Community' in txt and 'could not be found' not in txt:
            out['hits'].append({'kind': kind, 'url': url})
        else:
            out.setdefault('checked', {})[kind] = meta.get('http', st)
    return out

def mod_theharvester(target: str, limit: int = HARVESTER_LIMIT):
    """Best-effort theHarvester passive run with keyless sources (crtsh, hackertarget...). Non-fatal."""
    import shutil, subprocess, json as _j, os as _os
    out = {'target': target}
    candidates = [shutil.which('theHarvester'),
                  _os.path.join(_os.environ.get('APPDATA', ''), r'Python\Python314\Scripts\theHarvester.exe')]
    exe = next((c for c in candidates if c and _os.path.exists(c)), None)
    try:
        if not exe:
            return {**out, 'status': 'unavailable', 'note': 'theHarvester binary not on PATH'}
        cmd = [exe, '-d', target, '-l', str(limit), '-b', 'crtsh,hackertarget']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        txt = (r.stdout or '') + (r.stderr or '')
        import re as _re
        out['emails'] = sorted(set(_re.findall(r'[\w.+-]+@' + _re.escape(target), txt)))[:SUBDOMAIN_LIMIT]
        hosts = sorted(set(_re.findall(r'(?:[a-z0-9-]+\.)+' + _re.escape(target), txt.lower())))[:SUBDOMAIN_LIMIT]
        out['hosts'] = hosts
        out['raw_tail'] = txt[-1500:]
    except Exception as e:
        out['error'] = str(e)[:300]
    return out
