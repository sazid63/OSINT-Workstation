"""Orchestrator: TARGET -> detect -> plan -> parallel collect -> normalize -> dedupe -> correlate -> graph -> report."""
import concurrent.futures, yaml, os
from core.detect import detect_target, plan_for
from core.storage import create_investigation, save_raw
from core.clients import searxng_search, spiderfoot_status
from core.process import to_findings, dedupe, correlate, extract_entities, detect_contradictions, level_of
from core.report import build_graph_json, write_reports
from modules.collectors import (mod_dns, mod_whois_rdap, mod_cert, mod_ip, mod_url, mod_email,
    mod_username, mod_theharvester, mod_urlscan, mod_ipinfo, mod_ripestat, mod_wikidata,
    mod_nominatim, mod_steam)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_sources():
    with open(os.path.join(BASE, 'config', 'sources.yaml')) as f:
        return yaml.safe_load(f)

def collect_one(tool: str, target: str, sources: dict):
    sx = (sources.get('searxng') or {}).get('url')
    if tool == 'dns': return mod_dns(target)
    if tool == 'whois': return mod_whois_rdap(target)
    if tool == 'cert': return mod_cert(target)
    if tool == 'ip': return mod_ip(target)
    if tool == 'url': return mod_url(target)
    if tool == 'email': return mod_email(target)
    if tool == 'username': return mod_username(target)
    if tool == 'searxng': return searxng_search(sx, target)
    if tool == 'harvester':
        dom = target.split('@')[-1].split('/')[0]
        return mod_theharvester(dom)
    if tool == 'urlscan': return mod_urlscan(target)
    if tool == 'ipinfo': return mod_ipinfo(target)
    if tool == 'ripestat': return mod_ripestat(target)
    if tool == 'wikidata': return mod_wikidata(target)
    if tool == 'nominatim': return mod_nominatim(target)
    if tool == 'steam': return mod_steam(target)
    if tool == 'spiderfoot':
        sf = (sources.get('spiderfoot') or {}).get('url')
        return {'note': 'SpiderFoot runs async via its web UI; orchestrator records its availability here.',
                **spiderfoot_status(sf)}
    return {'error': f'unknown tool {tool}'}

DEEP_EXTRA = {
    'domain':       ['ipinfo'],
    'ip':           ['urlscan'],
    'email':        ['urlscan'],
    'username':     ['steam', 'wikidata'],
    'url':          [],
    'organization': [],
}

EVIDENCE_URL = {
    'dns': 'live DNS query', 'whois': 'live WHOIS/RDAP query',
    'cert': 'https://crt.sh', 'ip': 'live IP APIs', 'url': None,
    'email': 'https://api.github.com', 'username': 'https://api.github.com + https://gitlab.com',
    'searxng': None, 'harvester': 'passive aggregation', 'urlscan': 'https://urlscan.io',
    'ipinfo': 'https://ipinfo.io', 'ripestat': 'https://stat.ripe.net',
    'wikidata': 'https://www.wikidata.org', 'nominatim': 'https://nominatim.openstreetmap.org',
    'steam': 'https://steamcommunity.com', 'spiderfoot': 'http://localhost:5001',
}

def investigate(target: str, max_workers=8, deep: bool = False, _extra_queries: list = None) -> dict:
    sources = load_sources()
    ttype = detect_target(target)
    plan = plan_for(ttype)
    if deep:
        plan = plan + [t for t in DEEP_EXTRA.get(ttype, []) if t not in plan]
    meta = create_investigation(target, ttype, plan)
    meta['deep'] = deep
    raw, status = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(collect_one, t, target, sources): t for t in plan}
        for fut in concurrent.futures.as_completed(futs):
            tool = futs[fut]
            try:
                data = fut.result()
                raw[tool] = data
                if not isinstance(data, dict):
                    # e.g. a bare list from a collector — treat as a value, not a status dict
                    status[tool] = 'ok'
                else:
                    err = data.get('error')
                    st = data.get('status')
                    if err:
                        status[tool] = 'error'
                    elif st == 'unavailable':
                        status[tool] = 'unavailable'
                    else:
                        status[tool] = 'ok'
            except Exception as e:
                raw[tool] = {'error': str(e)[:300]}
                status[tool] = f'error: {e}'[:200]
            save_raw(meta['id'], tool, raw[tool])
    # --- chaining (phase 2, legitimate depth): domain -> subdomains -> resolve; org -> wikidata/nominatim already in plan
    chained = []
    if ttype in ('domain', 'url') and deep:
        subs = list({s for s in ((raw.get('cert') or {}).get('subdomains', []) +
                                 (raw.get('harvester') or {}).get('hosts', []))})[:15]
        import socket
        for s in subs:
            try:
                ips = socket.gethostbyname_ex(s)[2]
                chained.append({'tool': 'chain_dns', 'value': f"{s} -> {', '.join(ips)}",
                                'source': 'chained DNS resolution', 'class': 'FACT'})
            except Exception as e:
                chained.append({'tool': 'chain_dns', 'value': f"{s} unresolvable",
                                'source': 'chained DNS resolution', 'class': 'UNVERIFIED'})
        save_raw(meta['id'], 'chain_dns', chained)
    # --- extra SearXNG queries in deep mode (site: variants for org/domain)
    if deep and ttype in ('organization', 'domain'):
        sx = (sources.get('searxng') or {}).get('url')
        extra = _extra_queries or ([f'site:gov.bd {target}', f'{target} tender notice'] if ttype == 'organization'
                                   else [f'site:github.com {target}', f'"{target}"'])
        more = []
        for q in extra[:3]:
            r = searxng_search(sx, q)
            more.extend(r.get('results', []))
        raw['searxng_deep'] = {'status': 'ok', 'results': more}
        save_raw(meta['id'], 'searxng_deep', raw['searxng_deep'])
        status['searxng_deep'] = 'ok'
    findings = []
    for tool, data in raw.items():
        try:
            if tool == 'searxng_deep':
                findings.extend(to_findings('searxng', data))
            else:
                findings.extend(to_findings(tool, data))
        except Exception:
            pass
    findings.extend({**c, 'observed_utc': meta['created_utc']} for c in chained)
    findings = correlate(dedupe(findings))
    # evidence enrichment: source URLs, method, confidence level
    for f in findings:
        f['level'] = level_of(f)
        ev = (raw.get(f['tool']) or {})
        f['evidence_url'] = ev.get('evidence_url') or f.get('source') or EVIDENCE_URL.get(f['tool'])
        f['method'] = {'dns': 'direct DNS', 'whois': 'direct WHOIS/RDAP', 'cert': 'CT log + TLS handshake',
                       'searxng': 'metasearch', 'harvester': 'passive aggregation',
                       'chain_dns': 'chained resolution'}.get(f['tool'], 'public API / HTTP')
    entities = extract_entities(findings, target)
    contradictions = detect_contradictions(raw, findings)
    with open(os.path.join(meta['path'], 'normalized', 'findings.json'), 'w') as f:
        import json; json.dump(findings, f, indent=2, default=str)
    with open(os.path.join(meta['path'], 'normalized', 'entities.json'), 'w') as f:
        import json; json.dump({'entities': entities, 'contradictions': contradictions}, f, indent=2, default=str)
    gp = build_graph_json(meta['path'], target, findings, entities)
    reps = write_reports(meta, findings, status, entities, contradictions, raw)
    with open(os.path.join(meta['path'], 'logs', 'run.log'), 'w') as f:
        f.write(f"target={target} type={ttype} deep={deep} plan={plan} status={status} findings={len(findings)} entities={len(entities)} contradictions={len(contradictions)}\n")
    # hash manifest for evidence integrity
    import hashlib
    manifest = []
    for r, _, fs in os.walk(os.path.join(meta['path'], 'raw')):
        for fn in fs:
            p = os.path.join(r, fn)
            with open(p, 'rb') as f:
                h = hashlib.sha256(f.read()).hexdigest()
            manifest.append({'file': os.path.relpath(p, meta['path']), 'sha256': h})
    with open(os.path.join(meta['path'], 'logs', 'manifest.json'), 'w') as f:
        import json; json.dump(manifest, f, indent=2)
    return {'meta': meta, 'type': ttype, 'plan': plan, 'status': status,
            'findings': findings, 'entities': entities, 'contradictions': contradictions,
            'graph': gp, 'reports': reps}

def investigate_multi(targets: list, deep: bool = False) -> dict:
    """Combine multiple clues: separate investigations + shared-entity cross-correlation."""
    runs = [investigate(t, deep=deep) for t in targets]
    from collections import defaultdict
    by_ent = defaultdict(list)
    for r in runs:
        for e in r['entities']:
            by_ent[(e['type'], e['value'])].append(r['meta']['target'])
    shared = [{'type': k[0], 'value': k[1], 'in_targets': sorted(set(v))}
              for k, v in by_ent.items() if len(set(v)) >= 2]
    return {'runs': runs, 'shared_entities': sorted(shared, key=lambda x: -len(x['in_targets']))}
