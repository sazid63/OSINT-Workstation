#!/usr/bin/env python3
"""OSINT Workstation — CLI.

Authorized, lawful use only. The tool is passive: it reads public sources and
never authenticates, bypasses access controls, or touches private accounts.

Usage:
  osint doctor                       Preflight: deps, data dir, services
  osint investigate <target> [...]   Run an investigation
  osint list                         List stored investigations
  osint report <id>                  Print a stored report
  osint graph <id>                   Print a stored graph
  osint audit [n]                    Show the last n audit records
  osint search <query>               Query SearXNG directly
  osint services [up|down|status]    Manage local services
  osint health                       Probe sources
  osint tools | sources | status     Inventory / status
  osint domain|ip|email|username|cert|url|dns|whois|metadata|... <target>

Run `osint <command> --help` for command options.
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from core.version import APP_VERSION  # noqa: E402

MENU = f"""
==================================================
 OSINT WORKSTATION {APP_VERSION}
 Authorized, lawful use only. Passive public sources.
==================================================
 [1] New Investigation      [7]  Email Intelligence
 [2] Resume Investigation   [8]  Username Intelligence
 [3] Search (SearXNG)       [9]  Certificate Intelligence
 [4] Service status         [10] URL Intelligence
 [5] Domain Intelligence    [11] Tool Inventory
 [6] IP Intelligence        [12] Source Inventory
 [13] Investigation Graph   [14] Reports
 [15] Configuration         [16] Services (up/down)
 [17] Doctor (preflight)    [18] Audit log
 [0]  Exit
--------------------------------------------------
 CLI: osint <command> --help for usage
==================================================="""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _print_type_note(r: dict) -> None:
    if r.get('type_note'):
        print(f"\n! {r['type_note']}", file=sys.stderr)


def _authorized_or_explain(flags: set, interactive: bool) -> bool:
    """Collect an explicit authorization acknowledgement.

    This is a guardrail, not an access control: it forces the operator to state
    that they have a lawful basis before a run, and records that statement in
    the audit trail. Automation can pass --authorized or set OSINT_AUTHORIZED=1.
    """
    if 'authorized' in flags or os.environ.get('OSINT_AUTHORIZED') == '1':
        return True
    if not interactive:
        print(
            "refusing to run: no authorization acknowledgement.\n"
            "  This tool is for authorized, lawful investigations only.\n"
            "  Pass --authorized to confirm you have a lawful basis for this target,\n"
            "  or set OSINT_AUTHORIZED=1 in the environment for scripted runs.",
            file=sys.stderr)
        return False
    print("\nThis tool is for authorized, lawful investigations only.")
    print("Confirm you have a lawful basis to investigate this target "
          "(public-source research, own asset, signed engagement, etc.).")
    try:
        answer = input("Type 'yes' to continue: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ('yes', 'y')


def cmd_investigate(target, deep=False, ai=False, target_type=None, authorized=False):
    from core.orchestrator import investigate
    r = investigate(target, deep=deep, target_type=target_type, authorized=authorized)
    _print_type_note(r)
    if ai:
        from core.analyst import analyze
        from core.report import write_reports
        ar = analyze(r['meta']['path'], r['findings'])
        print(f"analyst: {ar}")
        write_reports(r['meta'], r['findings'], r['status'], r['entities'],
                      r['contradictions'], noise=r['noise'], diagnostics=r['diagnostics'])
    print(f"[{r['meta']['id']}] type={r['type']} deep={deep} plan={r['plan']}")
    print(f"status={r['status']}\nfindings={len(r['findings'])} "
          f"excluded_unrelated={len(r['noise'])} entities={len(r['entities'])} "
          f"contradictions={len(r['contradictions'])}")
    for f in r['findings'][:25]:
        print(f"  [{f.get('level', f['class'])}] ({f['tool']}) {f['value'][:120]}")
    if r.get('next_steps'):
        print("\nmissing sources — to fix:")
        for line in r['next_steps']:
            print(' ', line)
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
    from core import services
    with open(f'{BASE}/config/sources.yaml', encoding='utf-8') as f:
        s = yaml.safe_load(f)
    print('searxng:', searxng_search(s['searxng']['url'], 'test', count=1)['status'])
    print('spiderfoot:', spiderfoot_status(s['spiderfoot']['url']))
    print('services:', json.dumps(services.status(), default=str))


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


def cmd_services(action='status', name=None):
    from core import services
    cfg = services.SERVICES
    if action == 'status':
        print(json.dumps(services.status(), indent=2))
        return
    if action in ('up', 'down'):
        fn = services.start_all if action == 'up' else services.stop_all
        print(json.dumps(fn(), indent=2))
        return
    if action in ('start', 'stop'):
        if not name:
            print(f'usage: osint services {action} <{"|".join(cfg)}>', file=sys.stderr)
            return
        if name not in cfg:
            print(f'unknown service {name!r}; choose from {", ".join(cfg)}', file=sys.stderr)
            return
        print(json.dumps(services.start(name) if action == 'start' else services.stop(name),
                         indent=2))
        return
    print('usage: osint services [status|up|down|start <name>|stop <name>]', file=sys.stderr)


def cmd_doctor():
    from core import doctor
    checks = doctor.run_checks()
    print(doctor.format_report(checks))
    return doctor.exit_code(checks)


def cmd_audit(limit=20):
    from core import audit
    from core.storage import data_dir
    records = audit.tail(data_dir(), limit)
    if not records:
        print(f'no audit records yet ({audit.audit_path(data_dir())})')
        return 0
    for r in records:
        auth = 'authorized' if r.get('authorization_acknowledged') else 'NOT-authorized'
        print(f"{r.get('ts_utc', '?')}  {r.get('action', '?'):<12} {auth:<15} "
              f"{r.get('target_type') or '-':<13} {r.get('target', '')[:60]}")
    print(f"\n{audit.audit_path(data_dir())}")
    return 0


def cmd_list():
    from core.storage import list_investigations
    ids = list_investigations()
    print('\n'.join(ids[-40:]) or '(no investigations yet)')
    return 0


def cmd_show(what, inv_id):
    from core.storage import inv_path
    try:
        path = inv_path(inv_id)
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    target = os.path.join(path, 'graph', 'graph.json') if what == 'graph' \
        else os.path.join(path, 'reports', 'report.md')
    if not os.path.exists(target):
        print(f'not found: {target}', file=sys.stderr)
        return 1
    with open(target, encoding='utf-8') as f:
        print(f.read())
    return 0


def quick(tool, target):
    from modules.collectors import (mod_cert, mod_dns, mod_email, mod_ip, mod_ipinfo,
                                    mod_metadata, mod_nominatim, mod_ripestat,
                                    mod_steam, mod_theharvester, mod_url,
                                    mod_urlscan, mod_username, mod_wikidata,
                                    mod_whois_rdap)
    single = {'metadata': mod_metadata, 'harvester': mod_theharvester,
              'urlscan': mod_urlscan, 'ipinfo': mod_ipinfo,
              'ripestat': mod_ripestat, 'wikidata': mod_wikidata,
              'nominatim': mod_nominatim, 'steam': mod_steam}
    if tool in single:
        print(json.dumps(single[tool](target), indent=2, default=str)[:6000])
        return
    fn = {'domain': lambda t: (mod_dns(t), mod_whois_rdap(t), mod_cert(t)),
          'ip': mod_ip, 'email': mod_email, 'username': mod_username,
          'cert': mod_cert, 'url': mod_url, 'dns': mod_dns,
          'whois': mod_whois_rdap}.get(tool)
    if fn is None:
        print(f'unknown tool {tool!r}', file=sys.stderr)
        return
    print(json.dumps(fn(target), indent=2, default=str)[:6000])


def menu():
    from core.storage import inv_path, list_investigations
    print(MENU)
    while True:
        try:
            c = input('\nosint> ').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if c in ('0', 'exit', 'quit'):
            break
        if c == '1':
            target = input('target: ').strip()
            if target and _authorized_or_explain(set(), interactive=True):
                cmd_investigate(target, authorized=True)
        elif c == '2':
            print('\n'.join(list_investigations()[-10:]) or '(none)')
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
            try:
                p = os.path.join(inv_path(iid), 'graph', 'graph.json')
            except ValueError as e:
                print(e)
                continue
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    print(f.read()[:3000])
            else:
                print('(no graph yet)')
        elif c == '14':
            for d in list_investigations()[-5:]:
                print(d, '->', 'reports/report.md')
        elif c == '15':
            with open(f'{BASE}/config/settings.yaml', encoding='utf-8') as f:
                print(f.read())
        elif c == '16':
            cmd_services('status')
        elif c == '17':
            cmd_doctor()
        elif c == '18':
            cmd_audit()
        elif c.startswith('investigate '):
            target = c.split(None, 1)[1]
            if _authorized_or_explain(set(), interactive=True):
                cmd_investigate(target, authorized=True)
        elif c.startswith('search '):
            cmd_search(c.split(None, 1)[1])
        elif not c:
            print(MENU)
        else:
            print('unknown. Type a command or press Enter for the menu.')


def _split_flags(argv):
    """Separate `--type VALUE` from boolean flags and positional arguments."""
    flags, positional, ttype = set(), [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--type':
            if i + 1 >= len(argv):
                raise ValueError('--type requires a value')
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

    if cmd in ('help', '-h') or 'help' in flags:
        print(__doc__)
        return 0
    if cmd in ('version', '-V') or 'version' in flags:
        print(f'OSINT Workstation {APP_VERSION}')
        return 0

    if cmd == 'investigate':
        if len(pos) < 2:
            print('usage: osint investigate [--deep] [--ai] [--type T] [--authorized] <target> [...]',
                  file=sys.stderr)
            return 2
        if not _authorized_or_explain(flags, interactive=sys.stdin.isatty()):
            return 3
        deep, ai = 'deep' in flags, 'ai' in flags
        targets = pos[1:]
        if len(targets) > 1:
            from core.orchestrator import investigate_multi
            m = investigate_multi(targets, deep=deep, authorized=True)
            for r in m['runs']:
                print(f"[{r['meta']['id']}] {r['meta']['target']} "
                      f"findings={len(r['findings'])}")
            print(f"shared entities across clues: {len(m['shared_entities'])}")
            for s in m['shared_entities'][:20]:
                print(f"  {s['type']}: {s['value']} in {s['in_targets']}")
        else:
            cmd_investigate(targets[0], deep=deep, ai=ai, target_type=ttype,
                            authorized=True)
        return 0

    if cmd == 'doctor':
        return cmd_doctor()
    if cmd == 'audit':
        return cmd_audit(int(pos[1]) if len(pos) > 1 and pos[1].isdigit() else 20)
    if cmd == 'list':
        return cmd_list()
    if cmd in ('graph', 'report'):
        if len(pos) < 2:
            print(f'usage: osint {cmd} <investigation-id>', file=sys.stderr)
            return 2
        return cmd_show(cmd, pos[1])
    if cmd == 'search':
        if len(pos) < 2:
            print('usage: osint search <query>', file=sys.stderr)
            return 2
        cmd_search(' '.join(pos[1:]))
        return 0
    if cmd == 'status':
        cmd_status()
        return 0
    if cmd == 'health':
        cmd_health()
        return 0
    if cmd == 'tools':
        cmd_tools()
        return 0
    if cmd == 'sources':
        cmd_sources()
        return 0
    if cmd == 'services':
        cmd_services(pos[1] if len(pos) > 1 else 'status',
                     pos[2] if len(pos) > 2 else None)
        return 0
    if cmd in ('spiderfoot', 'domain', 'ip', 'email', 'username', 'cert', 'url',
               'dns', 'whois', 'metadata', 'harvester', 'urlscan', 'ipinfo',
               'ripestat', 'wikidata', 'nominatim', 'steam'):
        if cmd == 'spiderfoot':
            cmd_status()
            return 0
        if len(pos) < 2:
            print(f'usage: osint {cmd} <target>', file=sys.stderr)
            return 2
        quick(cmd, ' '.join(pos[1:]))
        return 0

    print(f'unknown command: {cmd}\n', file=sys.stderr)
    print(__doc__)
    return 2


def main(argv=None):
    """Entry point for the installed `osint` console script."""
    args = sys.argv[1:] if argv is None else list(argv)
    try:
        return run(args)
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('\ninterrupted', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
