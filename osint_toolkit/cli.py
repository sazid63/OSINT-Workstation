"""Command-line interface.

The GUI is the default. ``web``/``mcp``/``run`` are provided so the toolkit can
be scripted and connected to other agents (e.g. OpenCode via MCP).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import logging_setup, registry, runner, safety, workspace as ws_mod

log = logging_setup.get_logger("osint_toolkit.cli")


def _cmd_list(args=None):
    catalog = registry.load_catalog()
    for tool in catalog:
        state = "on" if registry.is_enabled(tool.id) else "off"
        print(f"[{state}] {tool.id:22s} {tool.category:20s} {tool.name}")
    print(f"\n{len(catalog)} tools in the catalog.")


def _cmd_run(args):
    tool = registry.get_tool(args.tool)
    if tool is None:
        print(f"Unknown tool '{args.tool}'. See 'osint-toolkit list'.", file=sys.stderr)
        return 1
    if args.accept_terms:
        safety.accept_terms()
    try:
        inputs = dict(pair.split("=", 1) for pair in args.input)
    except ValueError:
        print("Inputs must be key=value pairs.", file=sys.stderr)
        return 2
    workspace = ws_mod.load(args.workspace or "cli")
    result = runner.run_tool(tool, inputs, workspace=workspace)
    print(json.dumps(result.to_dict(), indent=2, default=str, ensure_ascii=False))
    return 0


def _cmd_doctor(args=None):
    checks: list[tuple[str, bool, str]] = []
    try:
        from .config import load as _load
        _load()
        checks.append(("config readable", True, ""))
    except Exception as exc:  # noqa: BLE001
        checks.append(("config readable", False, str(exc)))

    catalog = registry.load_catalog()
    passive = sum(1 for t in catalog if not t.is_active_tool)
    active = len(catalog) - passive
    checks.append(("catalog", True, f"{len(catalog)} tools ({passive} passive / {active} active)"))

    try:
        import requests  # noqa: F401
        checks.append(("requests", True, ""))
    except Exception:
        checks.append(("requests", False, "missing"))

    for module, label in [("dns", "dnspython"), ("whois", "python-whois"),
                          ("ipwhois", "ipwhois"), ("phonenumbers", "phonenumbers"),
                          ("yaml", "pyyaml")]:
        try:
            __import__(module)
            checks.append((label, True, ""))
        except Exception:
            checks.append((label, False, "missing"))

    for name, ok, detail in checks:
        print(f"{'OK ' if ok else 'FAIL'} {name:24s} {detail}")
    return 0 if all(ok for _, ok, _ in checks) else 1


def _cmd_terms(args):
    if args.accept:
        safety.accept_terms()
        print("Responsible-use notice accepted.")
    else:
        print("accepted" if safety.terms_accepted() else "not accepted")
    return 0


def _cmd_web(args):
    from .web.server import start
    server = start(host=args.host, port=args.port)
    print(f"OSINT Toolkit web UI: http://{args.host}:{args.port}  (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="osint-toolkit", description="OSINT Toolkit")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="launch the desktop app (default)")
    sub.add_parser("mcp", help="run the MCP stdio server (for OpenCode / MCP clients)")
    list_p = sub.add_parser("list", help="list all tools")
    list_p.set_defaults(func=_cmd_list)

    run_p = sub.add_parser("run", help="run one tool headlessly: run <tool> --input k=v")
    run_p.add_argument("tool")
    run_p.add_argument("--input", action="append", default=[], help="key=value")
    run_p.add_argument("--workspace")
    run_p.add_argument("--accept-terms", action="store_true", help="accept the responsible-use notice")
    run_p.set_defaults(func=_cmd_run)

    terms_p = sub.add_parser("terms", help="accept or query the responsible-use notice")
    terms_p.add_argument("--accept", action="store_true")
    terms_p.set_defaults(func=_cmd_terms)

    web_p = sub.add_parser("web", help="start the optional loopback web view")
    web_p.add_argument("--host", default="127.0.0.1")
    web_p.add_argument("--port", type=int, default=8765)
    web_p.set_defaults(func=_cmd_web)

    sub.add_parser("doctor", help="check the environment").set_defaults(func=_cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging_setup.setup()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command and getattr(args, "func", None):
        try:
            return args.func(args)
        except safety.NotAcceptedError as exc:
            print(f"Not allowed yet: {exc}", file=sys.stderr)
            return 3
    # default: launch the GUI
    try:
        from .ui.app import main as gui_main
        gui_main()
        return 0
    except ImportError as exc:  # pragma: no cover - PySide6 missing
        print(f"GUI unavailable ({exc}). Use: osint-toolkit web", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())