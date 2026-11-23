"""Normalize -> dedupe -> correlate -> relevance -> confidence.

Two independent properties decide how much a finding is worth:

  class       what kind of statement it is (FACT .. UNVERIFIED)
  relevance   how tightly it is tied to the target (direct/partial/none)

Search results are the reason these are separate. A metasearch hit means
"this page exists and matched a query" -- it says nothing about whether the
page is *about the target*. Scoring it as DIRECTLY OBSERVED at confidence 0.8
was the largest source of false confidence in v0.2.0; relevance now gates it.
"""
import datetime
import re

CLASS_RANK = {'FACT': 4, 'DIRECTLY OBSERVED': 3, 'CORRELATED': 2, 'INFERRED': 1, 'UNVERIFIED': 0}
RELEVANCE_RANK = {'direct': 3, 'partial': 2, 'unknown': 1, 'none': 0}
RELEVANCE_MULT = {'direct': 1.0, 'partial': 0.65, 'unknown': 0.8, 'none': 0.0}

LEVEL_OF = {'FACT': 'CONFIRMED', 'CORRELATED': 'HIGH CONFIDENCE',
            'DIRECTLY OBSERVED': 'MEDIUM CONFIDENCE', 'INFERRED': 'LOW CONFIDENCE',
            'UNVERIFIED': 'UNVERIFIED'}

_WORD_SPLIT = re.compile(r'[\s@._\-/]+')


def _tokens(value: str) -> list:
    return [w for w in _WORD_SPLIT.split((value or '').lower()) if len(w) > 2]


def relevance_of(value: str, source: str, target: str) -> str:
    """How tightly a record is tied to the target.

    'direct'  -- the target string appears verbatim
    'partial' -- most/all meaningful target tokens appear (e.g. name parts
                 reordered, or a page mentioning both city and surname)
    'unknown' -- no target supplied, so relevance cannot be assessed
    'none'    -- the record does not mention the target at all
    """
    t = (target or '').strip().lower()
    if not t:
        return 'unknown'
    hay = f"{value or ''} {source or ''}".lower()
    if t in hay:
        return 'direct'
    toks = _tokens(t)
    if not toks:
        return 'none'
    hits = sum(1 for tok in toks if tok in hay)
    if hits == len(toks):
        return 'partial'
    if hits / len(toks) >= 0.5:
        return 'partial'
    return 'none'


def to_findings(tool: str, data, target: str = '') -> list:
    """Flatten one module's raw output into finding dicts.

    `target` is only used to assess relevance for tools that return *about*
    arbitrary topics (searxng). Direct-query collectors are, by construction,
    about the target and are recorded as relevance='direct'.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    F = []

    def add(value, source='', conf='DIRECTLY OBSERVED', raw=None, relevance='direct'):
        if value:
            F.append({'tool': tool, 'value': str(value)[:500], 'source': source,
                      'observed_utc': ts, 'class': conf, 'relevance': relevance,
                      'raw': str(raw)[:300] if raw else None})

    if tool == 'dns':
        for rt, vals in (data.get('records') or {}).items():
            for v in vals:
                add(f"{rt}: {v}", source='target DNS', conf='FACT')
    elif tool == 'cert':
        for s in data.get('subdomains', [])[:200]:
            add(f"subdomain: {s}", source='crt.sh', conf='DIRECTLY OBSERVED')
        lc = data.get('live_cert') or {}
        if lc.get('notAfter'):
            add(f"tls expires {lc['notAfter']}", source='live TLS handshake', conf='FACT')
    elif tool == 'ip':
        for k in ('hackertarget_geoip',):
            if data.get(k):
                add(data[k], source='hackertarget geoip', conf='DIRECTLY OBSERVED')
        d = data.get('ipapi')
        if isinstance(d, dict) and d.get('status') == 'success':
            add(f"{d.get('city')}, {d.get('country')} via {d.get('isp')}",
                source='ip-api.com', conf='DIRECTLY OBSERVED')
    elif tool == 'searxng':
        # Relevance-gated: a hit is evidence that a page exists, not that it is
        # about the target. Unrelated hits drop to UNVERIFIED and are excluded
        # from the findings list downstream.
        for r in data.get('results', []):
            value = f"{r.get('title')} — {r.get('url')}"
            src = r.get('url', '') or ''
            rel = relevance_of(f"{value} {r.get('content') or ''}", src, target)
            conf = 'UNVERIFIED' if rel == 'none' else 'DIRECTLY OBSERVED'
            add(value, source=src, conf=conf, raw=r.get('content'), relevance=rel)
    elif tool == 'whois':
        w = data.get('whois') or {}
        for k in ('registrar', 'creation_date', 'org', 'country'):
            if w.get(k) and w[k] != 'None':
                add(f"whois {k}: {w[k]}", source='WHOIS/RDAP', conf='DIRECTLY OBSERVED')
    elif tool == 'url':
        c = data.get('checks', {})
        if c.get('http'):
            add(f"{data['url']} -> {c.get('final_url')} [{c.get('http')}]",
                source='live HTTP', conf='FACT')
    elif tool == 'email':
        for g in data.get('github_commits', []):
            add(f"github commit {g['sha']} in {g['repo']}", source='GitHub API', conf='CORRELATED')
    elif tool == 'username':
        for h in data.get('hits', []):
            add(f"{h['site']}: {h['url']}", source=h['url'], conf='FACT')
    elif tool == 'harvester':
        for e in data.get('emails', [])[:100]:
            add(f"email: {e}", source='theHarvester passive', conf='CORRELATED')
        for h in data.get('hosts', [])[:200]:
            add(f"host: {h}", source='theHarvester passive', conf='DIRECTLY OBSERVED')
    elif tool == 'urlscan':
        for s in data.get('scans', [])[:10]:
            add(f"archived scan: {s.get('url')}",
                source=s.get('scan') and f"https://urlscan.io/result/{s['scan']}/" or 'urlscan.io',
                conf='DIRECTLY OBSERVED')
    elif tool == 'ipinfo':
        d = data.get('data') or {}
        if d.get('city') or d.get('country'):
            add(f"geo: {d.get('city')}, {d.get('region')} {d.get('country')} ({d.get('org')})",
                source=data.get('evidence_url', 'ipinfo.io'), conf='DIRECTLY OBSERVED')
        if d.get('asn'):
            add(f"ASN: {d['asn'].get('asn')} {d['asn'].get('name')}",
                source='ipinfo.io', conf='DIRECTLY OBSERVED')
    elif tool == 'ripestat':
        for asn in data.get('asns', [])[:5]:
            add(f"origin ASN AS{asn} (prefix {data.get('prefix')})",
                source=data.get('evidence_url', 'stat.ripe.net'), conf='DIRECTLY OBSERVED')
        for asn, prefs in (data.get('announced') or {}).items():
            for p in prefs[:10]:
                add(f"announced {p} by {asn}", source='stat.ripe.net', conf='DIRECTLY OBSERVED')
    elif tool == 'wikidata':
        for e in data.get('entities', [])[:5]:
            add(f"{e.get('label')} — {e.get('description')}", source=e.get('url'),
                conf='DIRECTLY OBSERVED')
    elif tool == 'nominatim':
        for p in data.get('places', [])[:5]:
            add(f"place: {p.get('name')} [{p.get('lat')},{p.get('lon')}]",
                source='nominatim.openstreetmap.org', conf='DIRECTLY OBSERVED')
    elif tool == 'steam':
        for h in data.get('hits', []):
            add(f"steam {h['kind']}: {h['url']}", source=h['url'], conf='DIRECTLY OBSERVED')
    else:
        add(str(data)[:500], source=tool, conf='UNVERIFIED')
    return F


def dedupe(findings: list) -> list:
    seen, out = set(), []
    for f in findings:
        key = (f['tool'], f['value'].lower().strip())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def correlate(findings: list) -> list:
    """Merge identical values and record full provenance.

    Cross-tool agreement promotes to CORRELATED only when the merged finding is
    also relevant -- two unrelated search hits agreeing with each other is not
    corroboration. Relevance is carried as the weakest of the merged group.
    """
    from collections import defaultdict
    by_val = defaultdict(list)
    for f in findings:
        by_val[f['value'].lower().strip()].append(f)
    out = []
    for _val, group in by_val.items():
        tools = {g['tool'] for g in group}
        best = max(group, key=lambda g: CLASS_RANK.get(g['class'], 0))
        worst_rel = min((g.get('relevance', 'direct') for g in group),
                        key=lambda r: RELEVANCE_RANK.get(r, 1))
        merged = dict(best)
        merged['relevance'] = worst_rel
        merged['tools'] = sorted(tools)
        merged['sources'] = sorted({g.get('source', '') for g in group if g.get('source')})
        if (len(tools) >= 2 and CLASS_RANK.get(best['class'], 0) >= 2
                and worst_rel in ('direct', 'partial')):
            merged['class'] = 'CORRELATED'
        out.append(merged)
    return sorted(out, key=lambda f: (CLASS_RANK.get(f['class'], 0),
                                      RELEVANCE_RANK.get(f.get('relevance'), 1)), reverse=True)


def confidence_score(f: dict) -> float:
    """Confidence is class strength scaled by relevance to the target."""
    base = {'FACT': 0.95, 'DIRECTLY OBSERVED': 0.8, 'CORRELATED': 0.7,
            'INFERRED': 0.35, 'UNVERIFIED': 0.15}.get(f.get('class'), 0.2)
    return round(base * RELEVANCE_MULT.get(f.get('relevance', 'direct'), 1.0), 2)


def level_of(f: dict) -> str:
    rel = f.get('relevance', 'direct')
    if rel == 'none':
        return 'UNVERIFIED'
    cls = f.get('class')
    if cls == 'DIRECTLY OBSERVED':
        if len(f.get('tools', [f.get('tool')])) >= 2 and rel == 'direct':
            return 'HIGH CONFIDENCE'
        return 'MEDIUM CONFIDENCE' if rel == 'direct' else 'LOW CONFIDENCE'
    return LEVEL_OF.get(cls, 'UNVERIFIED')


_PATTERNS = {
    'domain': re.compile(r'\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b', re.I),
    'ip': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    'email': re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'),
    'url': re.compile(r'https?://[^\s)>\]]+'),
    'handle': re.compile(
        r'(?:github\.com/|gitlab\.com/|steamcommunity\.com/(?:id|profiles)/)([A-Za-z0-9_-]+)', re.I),
}


def extract_entities(findings: list, target: str) -> list:
    """Entity extraction: typed public identifiers mined from finding text."""
    ents: dict = {}
    for f in findings:
        for etype, pat in _PATTERNS.items():
            for m in pat.findall(f['value'] + ' ' + (f.get('source') or '')):
                v = m if isinstance(m, str) else m[0]
                v = v.lower().strip('.,;)')
                if etype == 'domain' and (v.startswith('example.') or len(v) < 5):
                    continue
                key = (etype, v)
                ents.setdefault(key, {'type': etype, 'value': v, 'tools': set(), 'count': 0})
                ents[key]['tools'].add(f['tool'])
                ents[key]['count'] += 1
    out = []
    for (etype, v), e in ents.items():
        if e['count'] >= 1 and not (etype == 'domain' and v == target.lower()):
            out.append({'type': etype, 'value': v, 'seen_by': sorted(e['tools']),
                        'mentions': e['count']})
    return sorted(out, key=lambda x: -x['mentions'])[:80]


def detect_contradictions(raw: dict, findings: list) -> list:
    """Evidence-based contradiction detection. Returns {about, claims[]} -- never merges blindly."""
    contra = []
    geos = []
    try:
        d = (raw.get('ip') or {}).get('ipapi') or {}
        if isinstance(d, dict) and d.get('city'):
            geos.append(('ip-api.com', f"{d.get('city')}, {d.get('country')}"))
        d2 = ((raw.get('ipinfo') or {}).get('data') or {})
        if d2.get('city'):
            geos.append(('ipinfo.io', f"{d2.get('city')}, {d2.get('country')}"))
        ht = (raw.get('ip') or {}).get('hackertarget_geoip') or ''
        if ht and 'US' in ht:
            geos.append(('hackertarget', ht.splitlines()[1] if len(ht.splitlines()) > 1 else ht[:80]))
    except Exception:
        pass
    places = {g[1].lower() for g in geos}
    if len(places) >= 2:
        contra.append({'about': 'IP geolocation differs by source (geolocation is approximate)',
                       'claims': [{'source': s, 'value': v} for s, v in geos]})
    try:
        w = ((raw.get('whois') or {}).get('whois') or {})
        reg = str(w.get('registrar', ''))[:80]
        rd = (raw.get('whois') or {}).get('rdap_domain') or {}
        if reg and reg.lower() not in ('none',) and rd and 'entities' in rd:
            contra.append({'about': 'WHOIS vs RDAP registrar records preserved separately — compare manually',
                           'claims': [{'source': 'WHOIS', 'value': reg},
                                      {'source': 'RDAP', 'value': 'see raw/whois.json rdap_domain'}]})
    except Exception:
        pass
    u = raw.get('username') or {}
    if u.get('hits') and u.get('misses'):
        contra.append({'about': 'Username exists on some services, absent on others — same handle ≠ same person',
                       'claims': [{'source': 'api-checks',
                                   'value': f"hits={[h['site'] for h in u['hits']]} misses={u['misses']}"}]})
    return contra
