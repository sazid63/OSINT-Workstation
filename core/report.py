"""Report generation: Markdown + HTML + JSON. 15-section evidence format."""
import os, json, datetime
from core.process import confidence_score

def build_graph_json(inv_path: str, target: str, findings: list, entities: list = None) -> str:
    nodes, links = [{'id': target, 'type': 'target', 'label': target}], []
    for i, f in enumerate(findings[:80]):
        nid = f"{f['tool']}:{i}"
        nodes.append({'id': nid, 'label': f['value'][:60], 'tool': f['tool'],
                      'class': f['class'], 'level': f.get('level', '')})
        links.append({'source': target, 'target': nid, 'kind': 'finding'})
    for e in (entities or [])[:40]:
        eid = f"ent:{e['type']}:{e['value']}"
        if not any(n['id'] == eid for n in nodes):
            nodes.append({'id': eid, 'label': e['value'][:60], 'type': 'entity',
                          'entity_type': e['type'], 'mentions': e['mentions']})
        links.append({'source': target, 'target': eid, 'kind': 'entity',
                      'seen_by': e.get('seen_by', [])})
    p = os.path.join(inv_path, 'graph', 'graph.json')
    with open(p, 'w') as fh:
        json.dump({'nodes': nodes, 'links': links,
                   'summary': f'{len(nodes)} nodes, {len(links)} links'}, fh, indent=2)
    return p

def write_reports(meta: dict, findings: list, tool_status: dict, entities: list = None,
                  contradictions: list = None, raw: dict = None) -> dict:
    entities, contradictions, raw = entities or [], contradictions or [], raw or {}
    inv_path, target = meta['path'], meta['target']
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for f in findings:
        f['confidence'] = round(confidence_score(f), 2)
        f.setdefault('level', 'UNVERIFIED')
    ok = sorted(t for t, s in tool_status.items() if s == 'ok')
    failed = {t: s for t, s in tool_status.items() if s != 'ok'}
    levels: dict = {}
    for f in findings:
        levels[f.get('level', 'UNVERIFIED')] = levels.get(f.get('level', 'UNVERIFIED'), 0) + 1
    jp = os.path.join(inv_path, 'reports', 'findings.json')
    with open(jp, 'w') as fh:
        json.dump({'meta': {**meta, 'path': None}, 'tool_status': tool_status,
                   'entities': entities, 'contradictions': contradictions,
                   'findings': findings}, fh, indent=2)
    L = [f"# OSINT Report — {target}",
         f"## 1. Investigation scope",
         f"- Authorized starting clue only; no authentication bypass, no private access. Passive public sources.",
         f"## 2. Starting clue", f"- `{target}` (type: {meta['target_type']}, deep={meta.get('deep', False)})",
         f"## 3. Collection timestamp", f"- {ts} (UTC). Case: `{meta['id']}`",
         f"## 4. Sources attempted", f"- {', '.join(meta['plan'])}",
         f"## 5. Sources successful", f"- {', '.join(ok) or '(none)'}",
         f"## 6. Sources failed"] + \
        ([f"- {t}: {s}" for t, s in failed.items()] or ["- (none — all attempted sources responded)"]) + [
         f"## 7. Findings ({len(findings)})"]
    for f in findings[:150]:
        L.append(f"- **[{f.get('level')}]** ({f['tool']}, conf {f['confidence']}) {f['value']}  \n  ↳ src: {f.get('source','')} | evidence: {f.get('evidence_url','')} | {f.get('observed_utc','')}")
    L.append("## 8. Correlations")
    L.append(f"- {len([f for f in findings if f.get('class')=='CORRELATED'])} multi-tool agreements; top shared entities:")
    ent_lines = [f"- {e['type']}: {e['value']} (seen by {', '.join(e['seen_by'])}, x{e['mentions']})" for e in entities[:20]]
    L.extend(ent_lines or ["- (none)"])
    L.append("## 9. Confidence levels")
    L.extend([f"- {k}: {v}" for k, v in levels.items()])
    L.append(f"## 10. Contradictions ({len(contradictions)})")
    for c in contradictions:
        L.append(f"- {c['about']}")
        L += [f"  - {cl['source']}: {cl['value']}" for cl in c['claims']]
    if not contradictions:
        L.append("- (none detected)")
    unver = [f for f in findings if f.get('level') == 'UNVERIFIED']
    L += [f"## 11. Unverified claims ({len(unver)})"]
    L += [f"- ({f['tool']}) {f['value']}" for f in unver[:20]] or ["- (none)"]
    L.append("## 12. Limitations")
    L.extend(["- WHOIS privacy redaction may hide registrant; RDAP consulted as fallback.",
          "- crt.sh lists all logged certs incl. expired — liveness verified only via handshake/resolution.",
          "- IP geolocation is approximate (city-level at best) and may disagree by source.",
          "- Username/profile hits prove handle existence, never same-human ownership.",
          "- SearXNG results reflect only engines that actually returned results (see engine health)."])
    L.append("## 13. Source URLs")
    L.extend([f"- {f.get('evidence_url','')}" for f in findings[:30] if f.get('evidence_url')] or ["- (none recorded)"])
    L += ["## 14. Collection errors"] + \
        ([f"- {t}: {(raw.get(t) or {}).get('error', s)}" for t, s in failed.items()] or ["- (none)"]) + [
          "## 15. Graph summary",
          f"- See `graph/graph.json`: findings + extracted entities linked to the target.",
          f"- Methodology: detect → plan → parallel collect → raw store → normalize → dedupe → entities → correlate → contradictions → confidence → graph → report."]
    mp = os.path.join(inv_path, 'reports', 'report.md')
    with open(mp, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))
    rows = '\n'.join(f"<tr><td>{f.get('level')}</td><td>{f['tool']}</td><td>{f['confidence']}</td><td>{f['value']}</td><td>{f.get('evidence_url','')}</td></tr>" for f in findings[:200])
    ai = ''
    aip = os.path.join(inv_path, 'reports', 'analyst.md')
    if os.path.exists(aip):
        import html as _h
        ai = f"<h2>AI analyst note (Ollama, labeled — verify against table)</h2><pre>{_h.escape(open(aip, encoding='utf-8').read())}</pre>"
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>OSINT {target}</title>
<style>body{{font-family:sans-serif;max-width:1100px;margin:auto;padding:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;font-size:13px}}pre{{background:#f4f4f4;padding:10px;white-space:pre-wrap}}</style></head>
<body><h1>OSINT Report — {target}</h1><p>{meta['id']} · {meta['target_type']} · deep={meta.get('deep', False)} · {ts}</p>
<p>Successful: {', '.join(ok) or '(none)'} | Failed: {', '.join(failed) or '(none)'} | Contradictions: {len(contradictions)}</p>
<table><tr><th>Level</th><th>Tool</th><th>Conf</th><th>Finding</th><th>Evidence</th></tr>{rows}</table>{ai}
<p>Full evidence: report.md + findings.json in this folder; raw responses in ../raw/.</p></body></html>"""
    hp = os.path.join(inv_path, 'reports', 'report.html')
    with open(hp, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return {'json': jp, 'markdown': mp, 'html': hp}
