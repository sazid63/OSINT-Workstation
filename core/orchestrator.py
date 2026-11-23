"""Orchestrator: TARGET -> detect -> plan -> parallel collect -> normalize -> dedupe
-> correlate -> relevance -> graph -> report.
"""
import concurrent.futures
import hashlib
import json
import os
import socket
import yaml

from core.detect import detect_target, normalize_type, plan_for, type_note
from core.storage import create_investigation, save_raw
from core.clients import searxng_search, spiderfoot_status
from core.process import (to_findings, dedupe, correlate, extract_entities,
                          detect_contradictions, level_of)
from core.report import build_graph_json, write_reports
from modules.collectors import (mod_dns, mod_whois_rdap, mod_cert, mod_ip, mod_url, mod_email,
    mod_username, mod_theharvester, mod_urlscan, mod_ipinfo, mod_ripestat, mod_wikidata,
    mod_nominatim, mod_steam)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Wall-clock budget for the parallel collection phase as a whole (not per tool).
# Individual collectors also carry their own HTTP timeouts. Python cannot kill a
# running thread, so a straggler is abandoned rather than interrupted.
COLLECT_TIMEOUT = int(os.environ.get('OSINT_COLLECT_TIMEOUT', '45'))


def load_sources():
    with open(os.path.join(BASE, 'config', 'sources.yaml'), encoding='utf-8') as f:
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
        # Liveness probe only. This pipeline does not submit scans to SpiderFoot
        # or ingest its results; the probe just records whether it is running.
        sf = (sources.get('spiderfoot') or {}).get('url')
        return {'note': 'liveness probe only — no scan submitted, no results ingested',
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


def _status_of(data) -> str:
    if not isinstance(data, dict):
        return 'ok'
    if data.get('error'):
        return 'error'
    if data.get('status') == 'unavailable':
        return 'unavailable'
    return 'ok'


def _collect_phase(plan: list, target: str, sources: dict, max_workers: int,
                   timeout: int) -> tuple:
    """Run collectors in parallel under a real wall-clock budget."""
    raw, status = {}, {}
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    try:
        futs = {ex.submit(collect_one, t, target, sources): t for t in plan}
        done, not_done = concurrent.futures.wait(futs, timeout=timeout)
        for fut in done:
            tool = futs[fut]
            try:
                data = fut.result()
                raw[tool] = data
                status[tool] = 'probe-only' if tool == 'spiderfoot' else _status_of(data)
            except Exception as e:
                raw[tool] = {'error': str(e)[:300]}
                status[tool] = f'error: {e}'[:200]
        for fut in not_done:
            tool = futs[fut]
            fut.cancel()
            raw[tool] = {'error': f'collector exceeded the {timeout}s collection budget'}
            status[tool] = 'error: timeout'
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return raw, status


def investigate(target: str, max_workers: int = 8, deep: bool = False,
                _extra_queries: list = None, target_type: str = None,
                timeout: int = None) -> dict:
    target = (target or '').strip()
    if not target:
        raise ValueError('empty target')
    sources = load_sources()
    forced = target_type is not None
    ttype = normalize_type(target_type) if forced else detect_target(target)
    plan = plan_for(ttype)
    if deep:
        plan = plan + [t for t in DEEP_EXTRA.get(ttype, []) if t not in plan]
    note = type_note(target, ttype, forced=forced)
    meta = create_investigation(target, ttype, plan, deep=deep,
                                type_inferred=not forced, type_note=note)
    raw, status = _collect_phase(plan, target, sources, max_workers,
                                 timeout or COLLECT_TIMEOUT)
    for tool in plan:
        try:
            save_raw(meta['id'], tool, raw.get(tool, {'error': 'no result'}))
        except Exception as e:
            status[tool] = f'error: raw save failed: {e}'[:200]

    # --- chaining (phase 2): domain -> subdomains -> resolve
    chained = []
    if ttype in ('domain', 'url') and deep:
        subs = list({s for s in ((raw.get('cert') or {}).get('subdomains', []) +
                                 (raw.get('harvester') or {}).get('hosts', []))})[:15]
        for s in subs:
            try:
                ips = socket.gethostbyname_ex(s)[2]
                chained.append({'tool': 'chain_dns', 'value': f"{s} -> {', '.join(ips)}",
                                'source': 'chained DNS resolution', 'class': 'FACT'})
            except Exception:
                chained.append({'tool': 'chain_dns', 'value': f"{s} unresolvable",
                                'source': 'chained DNS resolution', 'class': 'UNVERIFIED'})
        save_raw(meta['id'], 'chain_dns', chained)

    # --- extra SearXNG queries in deep mode
    if deep and ttype in ('organization', 'domain'):
        sx = (sources.get('searxng') or {}).get('url')
        extra = _extra_queries or (
            [f'site:gov.bd {target}', f'{target} tender notice'] if ttype == 'organization'
            else [f'site:github.com {target}', f'"{target}"'])
        more = []
        for q in extra[:3]:
            r = searxng_search(sx, q)
            more.extend(r.get('results', []))
        raw['searxng_deep'] = {'status': 'ok', 'results': more}
        save_raw(meta['id'], 'searxng_deep', raw['searxng_deep'])
        status['searxng_deep'] = 'ok'

    findings, diagnostics = [], []
    for tool, data in raw.items():
        if tool == 'spiderfoot':
            continue  # probe payload, never a finding
        try:
            src_tool = 'searxng' if tool == 'searxng_deep' else tool
            findings.extend(to_findings(src_tool, data, target=target))
        except Exception as e:
            diagnostics.append({'tool': tool, 'stage': 'normalize', 'error': str(e)[:300]})
    findings.extend({**c, 'observed_utc': meta['created_utc'], 'relevance': 'direct'}
                    for c in chained)
    findings = correlate(dedupe(findings))

    # Unrelated search results are audit material, not findings.
    relevant = [f for f in findings if f.get('relevance', 'direct') != 'none']
    noise = [f for f in findings if f.get('relevance', 'direct') == 'none']
    for f in relevant:
        f['level'] = level_of(f)
        ev = (raw.get(f['tool']) or {})
        f['evidence_url'] = ev.get('evidence_url') or f.get('source') or EVIDENCE_URL.get(f['tool'])
        f['method'] = {'dns': 'direct DNS', 'whois': 'direct WHOIS/RDAP',
                       'cert': 'CT log + TLS handshake', 'searxng': 'metasearch',
                       'harvester': 'passive aggregation',
                       'chain_dns': 'chained resolution'}.get(f['tool'], 'public API / HTTP')

    entities = extract_entities(relevant, target)
    contradictions = detect_contradictions(raw, relevant)

    normalized = os.path.join(meta['path'], 'normalized')
    with open(os.path.join(normalized, 'findings.json'), 'w', encoding='utf-8') as f:
        json.dump(relevant, f, indent=2, default=str)
    with open(os.path.join(normalized, 'noise.json'), 'w', encoding='utf-8') as f:
        json.dump(noise, f, indent=2, default=str)
    with open(os.path.join(normalized, 'entities.json'), 'w', encoding='utf-8') as f:
        json.dump({'entities': entities, 'contradictions': contradictions},
                  f, indent=2, default=str)

    gp = build_graph_json(meta['path'], target, relevant, entities)
    reps = write_reports(meta, relevant, status, entities, contradictions, raw,
                         noise=noise, diagnostics=diagnostics)
    with open(os.path.join(meta['path'], 'logs', 'run.log'), 'w', encoding='utf-8') as f:
        f.write(f"target={target} type={ttype} inferred={not forced} deep={deep} "
                f"plan={plan} status={status} findings={len(relevant)} "
                f"excluded_unrelated={len(noise)} entities={len(entities)} "
                f"contradictions={len(contradictions)} diagnostics={len(diagnostics)}\n")

    # hash manifest for evidence integrity
    manifest = []
    for r, _, fs in os.walk(os.path.join(meta['path'], 'raw')):
        for fn in fs:
            p = os.path.join(r, fn)
            with open(p, 'rb') as f:
                manifest.append({'file': os.path.relpath(p, meta['path']),
                                 'sha256': hashlib.sha256(f.read()).hexdigest()})
    with open(os.path.join(meta['path'], 'logs', 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    return {'meta': meta, 'type': ttype, 'type_inferred': not forced, 'type_note': note,
            'plan': plan, 'status': status, 'findings': relevant, 'noise': noise,
            'diagnostics': diagnostics, 'entities': entities,
            'contradictions': contradictions, 'graph': gp, 'reports': reps}


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
