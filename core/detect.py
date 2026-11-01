"""Target-type detection."""
import re, ipaddress

def detect_target(target: str) -> str:
    t = target.strip()
    # URL
    if re.match(r'^https?://', t, re.I):
        return 'url'
    # email
    if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', t):
        return 'email'
    # IP (v4/v6)
    try:
        ipaddress.ip_address(t)
        return 'ip'
    except ValueError:
        pass
    # username handle
    if re.match(r'^@?[A-Za-z0-9_.-]{2,39}$', t) and ('.' not in t or t.startswith('@')):
        # ambiguous with domain; prefer domain if it has a TLD-like suffix
        if '.' not in t:
            return 'username'
    # domain (incl. subdomain)
    if re.match(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.[A-Za-z]{2,}$', t):
        return 'domain'
    # organization = multi-word or fallback
    if ' ' in t or len(t) > 64:
        return 'organization'
    # default: treat dotted as domain else username
    return 'domain' if '.' in t else 'username'

PLAN = {
    'domain':       ['dns', 'whois', 'cert', 'harvester', 'urlscan', 'searxng', 'spiderfoot', 'url'],
    'ip':           ['ip', 'ripestat', 'ipinfo', 'whois', 'searxng', 'spiderfoot'],
    'email':        ['email', 'harvester', 'searxng', 'spiderfoot'],
    'username':     ['username', 'searxng', 'spiderfoot'],
    'url':          ['url', 'cert', 'urlscan', 'searxng', 'spiderfoot'],
    'organization': ['wikidata', 'nominatim', 'searxng', 'cert', 'spiderfoot'],
}

def plan_for(target_type: str):
    return PLAN.get(target_type, ['searxng'])
