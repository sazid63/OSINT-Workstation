"""Report generation: Markdown + HTML + JSON. 16-section evidence format.

All writers pin encoding='utf-8'. On Windows the default is the ANSI codepage
(cp1252), so an unencoded write raises UnicodeEncodeError on the first Bengali,
CJK or Arabic character in a finding -- i.e. exactly when a search returns a
non-Latin page.
"""
import datetime
import html as _h
import json
import os

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
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump({'nodes': nodes, 'links': links,
                   'summary': f'{len(nodes)} nodes, {len(links)} links'}, fh, indent=2)
    return p


def write_reports(meta: dict, findings: list, tool_status: dict, entities: list = None,
                  contradictions: list = None, raw: dict = None,
                  noise: list = None, diagnostics: list = None) -> dict:
    entities = entities or []
    contradictions = contradictions or []
    raw = raw or {}
    noise = noise or []
    diagnostics = diagnostics or []
    inv_path, target = meta['path'], meta['target']
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for f in findings:
        f['confidence'] = round(confidence_score(f), 2)
        f.setdefault('level', 'UNVERIFIED')
    ok = sorted(t for t, s in tool_status.items() if s == 'ok')
    probes = sorted(t for t, s in tool_status.items() if s == 'probe-only')
    failed = {t: s for t, s in tool_status.items() if s not in ('ok', 'probe-only')}
    levels: dict = {}
    for f in findings:
        levels[f.get('level', 'UNVERIFIED')] = levels.get(f.get('level', 'UNVERIFIED'), 0) + 1
    jp = os.path.join(inv_path, 'reports', 'findings.json')
    with open(jp, 'w', encoding='utf-8') as fh:
        json.dump({'meta': {**meta, 'path': None}, 'tool_status': tool_status,
                   'entities': entities, 'contradictions': contradictions,
                   'findings': findings, 'excluded_unrelated': noise,
                   'diagnostics': diagnostics}, fh, indent=2)

    type_line = f"- `{target}` (type: {meta['target_type']}, deep={meta.get('deep', False)})"
    if meta.get('type_inferred'):
        type_line += "  \n  ↳ **type was inferred, not supplied**"
    L = [f"# OSINT Report — {target}",
         "## 1. Investigation scope",
         "- Authorized starting clue only; no authentication bypass, no private access. Passive public sources.",
         "## 2. Starting clue", type_line]
    if meta.get('type_note'):
        L.append(f"- ⚠ {meta['type_note']}")
    L += ["## 3. Collection timestamp", f"- {ts} (UTC). Case: `{meta['id']}`",
          "## 4. Sources attempted", f"- {', '.join(meta['plan'])}",
          "## 5. Sources successful", f"- {', '.join(ok) or '(none)'}"]
    if probes:
        L.append(f"- liveness probes only (no data collected): {', '.join(probes)}")
    L += ["## 6. Sources failed"]
    L += ([f"- {t}: {s}" for t, s in failed.items()]
          or ["- (none — all attempted sources responded)"])
    L += [f"## 7. Findings ({len(findings)})"]
    for f in findings[:150]:
        extra_rel = '' if f.get('relevance', 'direct') == 'direct' else f", relevance {f.get('relevance')}"
        L.append(f"- **[{f.get('level')}]** ({f['tool']}, conf {f['confidence']}{extra_rel}) "
                 f"{f['value']}  \n  ↳ src: {f.get('source','')} | evidence: "
                 f"{f.get('evidence_url','')} | {f.get('observed_utc','')}")
    L.append("## 8. Correlations")
    L.append(f"- {len([f for f in findings if f.get('class')=='CORRELATED'])} multi-tool agreements; "
             f"top shared entities:")
    ent_lines = [f"- {e['type']}: {e['value']} (seen by {', '.join(e['seen_by'])}, x{e['mentions']})"
                 for e in entities[:20]]
    L.extend(ent_lines or ["- (none)"])
    L.append("## 9. Confidence levels")
    L.extend([f"- {k}: {v}" for k, v in levels.items()] or ["- (none)"])
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
              "- SearXNG results reflect only engines that actually returned results (see engine health).",
              "- Search hits are relevance-gated: a page mentioning no target token is excluded as unrelated.",
              "- There is no person target type; name-to-person resolution is out of scope."])
    L.append("## 13. Source URLs")
    L.extend([f"- {f.get('evidence_url','')}" for f in findings[:30] if f.get('evidence_url')]
             or ["- (none recorded)"])
    L += ["## 14. Collection errors"]
    err_lines = [f"- {t}: {(raw.get(t) or {}).get('error', s)}" for t, s in failed.items()]
    err_lines += [f"- {d['tool']} ({d.get('stage','?')}): {d['error']}" for d in diagnostics]
    L += (err_lines or ["- (none)"])
    L += ["## 15. Graph summary",
          "- See `graph/graph.json`: findings + extracted entities linked to the target.",
          ("- Methodology: detect → plan → parallel collect → raw store → normalize → dedupe → "
           "entities → correlate → contradictions → relevance/confidence → graph → report.")]
    L.append(f"## 16. Excluded: unrelated search results ({len(noise)})")
    L.append("- Returned by the metasearch engine but mentioning no target token. "
             "Not findings; retained for audit only (`normalized/noise.json`).")
    L += [f"- ({f['tool']}) {f['value']}" for f in noise[:25]] or ["- (none)"]
    mp = os.path.join(inv_path, 'reports', 'report.md')
    with open(mp, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))
    rows = '\n'.join(
        f"<tr><td>{_h.escape(str(f.get('level')))}</td><td>{_h.escape(f['tool'])}</td>"
        f"<td>{_h.escape(str(f['confidence']))}</td><td>{_h.escape(str(f['value']))}</td>"
        f"<td>{_h.escape(str(f.get('evidence_url','')))}</td></tr>"
        for f in findings[:200])
    ai = ''
    aip = os.path.join(inv_path, 'reports', 'analyst.md')
    if os.path.exists(aip):
        with open(aip, encoding='utf-8') as f:
            ai_content = f.read()
        ai = (f"<h2>AI analyst note (Ollama, labeled — verify against table)</h2>"
              f"<pre>{_h.escape(ai_content)}</pre>")
    note = f"<p><strong>⚠ {_h.escape(str(meta.get('type_note')))}</strong></p>" if meta.get('type_note') else ''
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>OSINT {_h.escape(str(target))}</title>
<style>body{{font-family:sans-serif;max-width:1100px;margin:auto;padding:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;font-size:13px}}pre{{background:#f4f4f4;padding:10px;white-space:pre-wrap}}</style></head>
<body><h1>OSINT Report — {_h.escape(str(target))}</h1>{note}<p>{_h.escape(str(meta['id']))} · {_h.escape(str(meta['target_type']))} · deep={_h.escape(str(meta.get('deep', False)))} · {ts}</p>
<p>Successful: {_h.escape(str(', '.join(ok) or '(none)'))} | Failed: {_h.escape(str(', '.join(failed) or '(none)'))} | Contradictions: {len(contradictions)} | Excluded unrelated: {len(noise)}</p>
<table><tr><th>Level</th><th>Tool</th><th>Conf</th><th>Finding</th><th>Evidence</th></tr>{rows}</table>{ai}
<p>Full evidence: report.md + findings.json in this folder; raw responses in ../raw/.</p></body></html>"""
    hp = os.path.join(inv_path, 'reports', 'report.html')
    with open(hp, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return {'json': jp, 'markdown': mp, 'html': hp}
