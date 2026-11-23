"""Target-type detection and collection planning.

Target types are explicit. Multi-word input (a person's or an organisation's
name) falls back to `organization` because this pipeline has no person target
type -- name-to-person resolution is deliberately out of scope. Callers must
surface that inference via `type_note` and may override it with `--type`.
"""
import ipaddress
import re

SUPPORTED_TYPES = ('domain', 'ip', 'email', 'username', 'url', 'organization')

_URL_RE = re.compile(r'^https?://', re.I)
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_HANDLE_RE = re.compile(r'^@?[A-Za-z0-9_.-]{2,39}$')
_DOMAIN_RE = re.compile(
    r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.[A-Za-z]{2,}$')

_TYPE_ALIASES = {
    'org': 'organization',
    'organisation': 'organization',
    'host': 'domain',
    'handle': 'username',
}

PLAN = {
    'domain':       ['dns', 'whois', 'cert', 'harvester', 'urlscan', 'searxng', 'spiderfoot', 'url'],
    'ip':           ['ip', 'ripestat', 'ipinfo', 'whois', 'searxng', 'spiderfoot'],
    'email':        ['email', 'harvester', 'searxng', 'spiderfoot'],
    'username':     ['username', 'searxng', 'spiderfoot'],
    'url':          ['url', 'cert', 'urlscan', 'searxng', 'spiderfoot'],
    'organization': ['wikidata', 'nominatim', 'searxng', 'cert', 'spiderfoot'],
}


def detect_target(target: str) -> str:
    """Infer a target type from the clue's shape.

    Order matters: URL and email are checked before domain, and an IPv4 address
    must not be mistaken for a domain. Multi-word input has no unambiguous type
    and is reported as 'organization' -- always pair this with `type_note`.
    """
    t = (target or '').strip()
    if not t:
        raise ValueError('empty target')
    if _URL_RE.match(t):
        return 'url'
    if _EMAIL_RE.match(t):
        return 'email'
    try:
        ipaddress.ip_address(t)
        return 'ip'
    except ValueError:
        pass
    if _DOMAIN_RE.match(t):
        return 'domain'
    if _HANDLE_RE.match(t) and ('.' not in t or t.startswith('@')):
        return 'username'
    if ' ' in t or len(t) > 64:
        return 'organization'
    return 'domain' if '.' in t else 'username'


def normalize_type(value: str) -> str:
    """Validate a caller-supplied target type, resolving common aliases."""
    v = (value or '').strip().lower()
    v = _TYPE_ALIASES.get(v, v)
    if v not in SUPPORTED_TYPES:
        raise ValueError(
            f'unsupported target type {value!r}; choose one of: {", ".join(SUPPORTED_TYPES)}')
    return v


def type_note(target: str, target_type: str, forced: bool = False) -> "str | None":
    """Explain a non-obvious type inference so it never stays silent.

    Returns None when the type was supplied explicitly or is self-evident.
    """
    if forced:
        return None
    if target_type == 'organization':
        return (
            f"Target type 'organization' was inferred from multi-word input "
            f"{target.strip()!r}. This pipeline has no person target type: "
            f"name-to-person resolution is out of scope. Pass --type to state "
            f"the type explicitly if 'organization' is wrong."
        )
    return None


def plan_for(target_type: str):
    return PLAN.get(target_type, ['searxng'])
