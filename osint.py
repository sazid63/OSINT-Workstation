#!/usr/bin/env python3
"""OSINT Terminal — menu + CLI. Usage: python osint.py [command] [args]"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

MENU = """
==================================================
OSINT TERMINAL
==============
[1] New Investigation      [7]  Email Intelligence
[2] Resume Investigation   [8]  Username Intelligence
[3] Search (SearXNG)       [9]  Certificate Intelligence
[4] SpiderFoot status      [10] URL Intelligence
[5] Domain Intelligence    [11] Tool Inventory
[6] IP Intelligence        [12] Source Inventory
[13] Investigation Graph   [14] Reports
[15] Configuration         [16] Services (up/down)
[0]  Exit
--------------------------------------------------
CLI: investigate [--deep] [--ai] [--type T] <target> [more targets] |search|spiderfoot|domain|ip|email|username|cert|url|metadata|harvester|urlscan|ipinfo|ripestat|wikidata|nominatim|steam|graph|report|tools|sources|status|health|services <args>
=================================================="""


def _print_type_note(r: dict) -> None:
    if r.get('type_note'):
        print(f"\n! {r['type_note']}", file=sys.stderr)


def cmd_investigate(target, deep=False, ai=False, target_type=None):
    from core.orchestrator import investigate
    r = investigate(target, deep=deep, target_type=target_type)
    _print_type_note(r)
    if ai:
        from core.analyst import analyze
        ar = analyze(r['meta']['path'], r['findings'])
        print(f"analyst: {ar}")
        from core.report import write_reports as _wr
        _wr(r['meta'], r['findings'], r['status'], r['entities'],
            r['contradictions'], noise=r['noise'], diagnostics=r['diagnostics'])
    print(f"[{r['meta']['id']}] type={r['type']} deep={deep} plan={r['plan']}")
    print(f"status={r['status']}\nfindings={len(r['findings'])} "
          f"excluded_unrelated={len(r['noise'])} entities={len(r['entities'])} "
          f"contradictions={len(r['contradictions'])}")
    for f in r['findings'][:25]:
        print(f"  [{f.get('level', f['class'])}] ({f['tool']}) {f['value'][:120]}")
    print(f"report: {r['reports']['markdown']}")
    return r


def cmd_search(query):
    import yaml
    from core.clients import searxng_search
    with open(f'{BASE}/config/sources.yaml', encoding='utf-8') as f:
        sx = yaml.safe_load(f)['searxng']['url']
    r = searxng_search(sx, query)
    print(f"status={r['status']} results={len(r['results'])}")
    for x in r['results'][:15]:
        print(f"  - {x['title']}\n    {x['url']}")


def cmd_status():
    import yaml
    from core.clients import searxng_search, spiderfoot_status
    with open(f'{BASE}/config/sources.yaml', encoding='utf-8') as f:
        s = yaml.safe_load(f)
    print('searxng:', searxng_search(s['searxng']['url'], 'test', count=1)['status'])
    print('spiderfoot:', spiderfoot_status(s['spiderfoot']['url']))
    print('native: dns/whois/ipwhois OK (import-tested at startup)')


def cmd_tools():
    import yaml
    with open(f'{BASE}/config/sources.yaml', encoding='utf-8') as f:
        print(yaml.safe_dump(yaml.safe_load(f)['native_tools'], default_flow_style=False))


def cmd_sources():
    import yaml
    with open(f'{BASE}/config/source_registry.yaml', encoding='utf-8') as f:
        reg = yaml.safe_load(f)['registry']
    health = {}
    try:
        with open(f'{BASE}/config/source_health.json', encoding='utf-8') as hf:
            health = {s['name']: s for s in json.load(hf)['sources']}
    except Exception:
        pass
    print(f"{'SOURCE':24} {'METHOD':13} {'EN':3} {'HEALTH':24} NOTE")
    for e in reg:
        h = health.get(e['name'], {})
        print(f"{e['name']:24} {e['method']:13} {str(e['enabled']):3} "
              f"{h.get('health', e.get('health', '?')):24} {(h.get('reason') or e.get('note', ''))[:70]}")
    print(f"\n{len(reg)} sources. Run `osint health` to live-test automated ones.")


def cmd_health():
    from core.health import run_health
    print('probing automated sources + SearXNG engines (polite pacing, ~1-2 min)...')
    r = run_health()
    counts = {}
    for s in r['sources']:
        counts[s['health']] = counts.get(s['health'], 0) + 1
    print('sources:', counts)
    for s in r['sources']:
        if s['health'] in ('FAILED', 'RATE_LIMITED', 'TEMPORARILY_UNAVAILABLE'):
            print(f"  ! {s['name']}: {s['health']} — {s['reason'][:100]}")
    print('searxng:', r['searxng']['status'],
          '| working engines:', r['searxng']['working_engines'] or '(none!)')
    for e in r['searxng']['engines']:
        if not e['working']:
            print(f"  ! engine {e['engine']}: {e['note'][:100]}")
    print('spiderfoot:', r['spiderfoot'])
    print('full JSON: config/source_health.json')


def cmd_services(action='status'):
    from core import services
    fn = {'status': services.status, 'up': services.start_all,
          'down': services.stop_all,
          'start': lambda: services.start(sys.argv[2]),
          'stop': lambda: services.stop(sys.argv[2])}.get(action)
    if not fn:
        print('usage: osint services [status|up|down|start <name>|stop <name>]'); return
    print(json.dumps(fn(), indent=2))


def quick(tool, target):
    from modules.collectors import mod_dns, mod_whois_rdap, mod_cert, mod_ip, mod_url, mod_email, mod_username, mod_metadata, mod_theharvester
    from modules.collectors import mod_urlscan, mod_ipinfo, mod_ripestat, mod_wikidata, mod_nominatim, mod_steam
    if tool == 'metadata':
        print(json.dumps(mod_metadata(target), indent=2, default=str)[:6000]); return
    if tool == 'harvester':
        print(json.dumps(mod_theharvester(target), indent=2, default=str)[:6000]); return
    if tool == 'urlscan':
        print(json.dumps(mod_urlscan(target), indent=2, default=str)[:6000]); return
    if tool == 'ipinfo':
        print(json.dumps(mod_ipinfo(target), indent=2, default=str)[:6000]); return
    if tool == 'ripestat':
        print(json.dumps(mod_ripestat(target), indent=2, default=str)[:6000]); return
    if tool == 'wikidata':
        print(json.dumps(mod_wikidata(target), indent=2, default=str)[:6000]); return
    if tool == 'nominatim':
        print(json.dumps(mod_nominatim(target), indent=2, default=str)[:6000]); return
    if tool == 'steam':
        print(json.dumps(mod_steam(target), indent=2, default=str)[:6000]); return
    fn = {'domain': lambda t: (mod_dns(t), mod_whois_rdap(t), mod_cert(t)),
          'ip': mod_ip, 'email': mod_email, 'username': mod_username,
          'cert': mod_cert, 'url': mod_url, 'dns': mod_dns, 'whois': mod_whois_rdap}[tool]
    print(json.dumps(fn(target), indent=2, default=str)[:6000])


def menu():
    print(MENU)
    while True:
        try:
            c = input('\nosint> ').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if c in ('0', 'exit', 'quit'):
            break
        elif c == '1':
            cmd_investigate(input('target: ').strip())
        elif c == '2':
            invs = sorted(os.listdir(f'{BASE}/investigations'))
            print('\n'.join(invs[-10:]) or '(none)')
        elif c == '3':
            cmd_search(input('query: '))
        elif c == '4':
            cmd_status()
        elif c in ('5', '6', '7', '8', '9', '10'):
            tool = {'5': 'domain', '6': 'ip', '7': 'email',
                    '8': 'username', '9': 'cert', '10': 'url'}[c]
            quick(tool, input(f'{tool} target: ').strip())
        elif c == '11':
            cmd_tools()
        elif c == '12':
            cmd_sources()
        elif c == '13':
            iid = input('investigation id: ').strip()
            p = f'{BASE}/investigations/{iid}/graph/graph.json'
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    print(f.read()[:3000])
            else:
                print('(no graph yet)')
        elif c == '14':
            for d in sorted(os.listdir(f'{BASE}/investigations'))[-5:]:
                print(d, '->', f'investigations/{d}/reports/report.md')
        elif c == '15':
            with open(f'{BASE}/config/settings.yaml', encoding='utf-8') as f:
                print(f.read())
        elif c == '16':
            cmd_services('status')
        elif c.startswith('investigate '):
            cmd_investigate(c.split(None, 1)[1])
        elif c.startswith('search '):
            cmd_search(c.split(None, 1)[1])
        elif not c:
            print(MENU)
        else:
            print('unknown. Type CLI cmd or empty line for menu.')


def _split_flags(argv):
    """Separate boolean flags and --type VALUE from positional arguments."""
    flags, positional, ttype = set(), [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--type':
            if i + 1 >= len(argv):
                raise SystemExit('--type requires a value')
            ttype = argv[i + 1]
            i += 2
            continue
        if a.startswith('--type='):
            ttype = a.split('=', 1)[1]
        elif a.startswith('--'):
            flags.add(a[2:])
        else:
            positional.append(a)
        i += 1
    return flags, positional, ttype


def run(argv):
    """Execute one CLI invocation. Returns a process exit code."""
    if not argv:
        menu()
        return 0
    flags, pos, ttype = _split_flags(argv)
    cmd = pos[0] if pos else ''

    if cmd == 'investigate' and len(pos) > 1:
        deep, ai = 'deep' in flags, 'ai' in flags
        targets = pos[1:]
        if len(targets) > 1:
            from core.orchestrator import investigate_multi
            m = investigate_multi(targets, deep=deep)
            for r in m['runs']:
                print(f"[{r['meta']['id']}] {r['meta']['target']} findings={len(r['findings'])}")
            print(f"shared entities across clues: {len(m['shared_entities'])}")
            for s in m['shared_entities'][:20]:
                print(f"  {s['type']}: {s['value']} in {s['in_targets']}")
        else:
            cmd_investigate(targets[0], deep=deep, ai=ai, target_type=ttype)
        return 0
    if cmd == 'search' and len(pos) > 1:
        cmd_search(' '.join(pos[1:]))
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'health':
        cmd_health()
    elif cmd == 'tools':
        cmd_tools()
    elif cmd == 'sources':
        cmd_sources()
    elif cmd == 'services':
        cmd_services(pos[1] if len(pos) > 1 else 'status')
    elif cmd in ('domain', 'ip', 'email', 'username', 'cert', 'url', 'dns', 'whois',
                 'spiderfoot', 'metadata', 'harvester', 'urlscan', 'ipinfo', 'ripestat',
                 'wikidata', 'nominatim', 'steam') and len(pos) > 1:
        if cmd == 'spiderfoot':
            cmd_status()
        else:
            quick(cmd, ' '.join(pos[1:]))
    elif cmd in ('graph', 'report') and len(pos) > 1:
        iid = pos[1]
        p = f"{BASE}/investigations/{iid}/" + \
            ("graph/graph.json" if cmd == "graph" else "reports/report.md")
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                print(f.read())
        else:
            print(f'not found: {p}')
    elif cmd in ('toolkit', 'gui', 'mcp', 'web') and len(pos) > 1:
        import subprocess
        subprocess.run([sys.executable, '-m', 'osint_toolkit'] + pos[1:], cwd=BASE)
    else:
        print(__doc__)
        return 2 if cmd else 0
    return 0


def main(argv=None):
    """Entry point for the installed `osint` console script."""
    args = sys.argv[1:] if argv is None else list(argv)
    try:
        return run(args)
    except (ValueError, SystemExit) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
