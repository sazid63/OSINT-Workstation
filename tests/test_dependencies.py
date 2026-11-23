"""Guards the packaging contract.

v0.2.x shipped `theHarvester>=4.0` and `sherlock-project` as hard install
dependencies even though the CLI invokes them as subprocess binaries and never
imports them. On an index without that version, `pip install` failed outright --
so nobody could install the tool. It also imported PIL without declaring Pillow.

These tests fail if that ever regresses: they compare the declared core
dependencies against what the code actually imports.
"""
import ast
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Distribution name -> top-level import name, for the third-party packages here.
DIST_TO_MODULE = {
    'requests': 'requests',
    'urllib3': 'urllib3',
    'dnspython': 'dns',
    'python-whois': 'whois',
    'ipwhois': 'ipwhois',
    'pyyaml': 'yaml',
    'pillow': 'PIL',
    'pyside6': 'PySide6',
    'keyring': 'keyring',
    'phonenumbers': 'phonenumbers',
    'theharvester': 'theHarvester',
    'sherlock-project': 'sherlock',
    'mcp': 'mcp',
    'jinja2': 'jinja2',
    'packaging': 'packaging',
    'pytest': 'pytest',
    'ruff': 'ruff',
}
# First-party / stdlib prefixes to ignore when scanning imports.
LOCAL = {'core', 'modules', 'osint', 'osint_toolkit', 'config', 'qa', 'services',
         'tests'}


def _pyproject():
    with open(ROOT / 'pyproject.toml', 'rb') as f:
        return tomllib.load(f)


def _dist_names(deps):
    names = set()
    for spec in deps:
        # strip extras/markers, then take the leading name up to a version operator
        base = spec.split(';')[0].split('[')[0].strip()
        for op in ('>=', '<=', '==', '~=', '>', '<', '!='):
            base = base.split(op)[0]
        base = base.strip()
        if base:
            names.add(base.lower().replace('_', '-'))
    return names


def _imported_modules(*dirs):
    """Top-level third-party module names imported (at any depth) under dirs."""
    stdlib = set(sys.stdlib_module_names)
    found = set()
    for d in dirs:
        for py in (ROOT / d).rglob('*.py'):
            try:
                tree = ast.parse(py.read_text(encoding='utf-8', errors='replace'))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for n in names:
                    top = n.split('.')[0]
                    if top and top not in stdlib and top not in LOCAL:
                        found.add(top)
    return found


def test_core_deps_are_actually_imported_by_the_cli():
    """No subprocess-only or dead package in the install-critical core deps."""
    core = _dist_names(_pyproject()['project']['dependencies'])
    cli_imports = _imported_modules('core', 'modules')
    cli_modules = {DIST_TO_MODULE.get(d, d) for d in core}
    orphans = {d for d in core if DIST_TO_MODULE.get(d, d) not in cli_imports}
    assert not orphans, (
        f'core dependencies not imported by the CLI (breaks install for no reason): '
        f'{sorted(orphans)}. CLI imports: {sorted(cli_imports)}')


def test_subprocess_binaries_are_not_hard_dependencies():
    """theHarvester/sherlock are run via subprocess; they must be optional."""
    core = _dist_names(_pyproject()['project']['dependencies'])
    for binary in ('theharvester', 'sherlock-project'):
        assert binary not in core, f'{binary} must be an optional [tools] extra, not a core dep'


def test_every_cli_import_is_declared_somewhere():
    """If code imports a third-party module, it must be installable."""
    project = _pyproject()['project']
    declared = _dist_names(project['dependencies'])
    for extra in project.get('optional-dependencies', {}).values():
        declared |= _dist_names(extra)
    declared_modules = {DIST_TO_MODULE.get(d, d) for d in declared}
    cli_imports = _imported_modules('core', 'modules')
    # pytest is a test-only import; tolerate it appearing via helpers in these dirs.
    missing = {m for m in cli_imports if m not in declared_modules and m != 'pytest'}
    assert not missing, f'imported but undeclared modules: {sorted(missing)}'


def test_toolkit_only_libs_are_not_core_deps():
    """keyring/phonenumbers are used by osint_toolkit, not the CLI core."""
    core = _dist_names(_pyproject()['project']['dependencies'])
    cli_imports = _imported_modules('core', 'modules')
    for name, mod in (('keyring', 'keyring'), ('phonenumbers', 'phonenumbers')):
        if mod not in cli_imports:
            assert DIST_TO_MODULE[name] not in cli_imports
            assert name not in core, f'{name} is toolkit-only; keep it out of core deps'


def test_scripts_entry_points_exist():
    scripts = _pyproject()['project']['scripts']
    assert scripts.get('osint') == 'osint:main'
    # The module behind osint:main must exist and define main().
    assert (ROOT / 'osint.py').exists()
    tree = ast.parse((ROOT / 'osint.py').read_text(encoding='utf-8'))
    assert any(isinstance(n, ast.FunctionDef) and n.name == 'main' for n in tree.body)


def test_requirements_txt_matches_core_dependencies():
    req_lines = [l.split('#')[0].strip() for l in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()]
    req_names = _dist_names([l for l in req_lines if l])
    core_names = _dist_names(_pyproject()['project']['dependencies'])
    assert req_names == core_names, (
        f'requirements.txt and pyproject core deps diverge: only-req={req_names - core_names}, '
        f'only-pyproject={core_names - req_names}')


def test_every_cli_module_compiles():
    """Offline tests only import a few modules; a syntax error in services.py,
    health.py or collectors.py would ship undetected and crash `osint services`
    / `osint status` at startup. Byte-compile the whole first-party surface."""
    import compileall
    ok = True
    for d in ('core', 'modules'):
        # quiet=1, rx=None; force full recompile of the tree
        if not compileall.compile_dir(ROOT / d, quiet=1, force=True):
            ok = False
    for f in ('osint.py',):
        if not compileall.compile_file(ROOT / f, quiet=1, force=True):
            ok = False
    assert ok, 'one or more first-party modules fail to compile'


def test_services_imports_and_exposes_docker_fallback():
    """core/services.py had a syntax error that no offline test caught. It must
    import cleanly and provide the fresh-clone Docker fallback."""
    import importlib
    services = importlib.import_module('core.services')
    assert hasattr(services, 'docker_available')
    assert hasattr(services, '_start_searxng_docker')
    assert services.DOCKER_SEARXNG_IMAGE == 'searxng/searxng:latest'
    # SearXNG is not vendored in a fresh clone; the fallback path must exist.
    assert 'searxng' in services.SERVICES
