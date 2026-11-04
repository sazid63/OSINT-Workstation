"""Built-in, pure-Python collectors.

These need no external binaries and query public data sources. They are the
default engine behind the catalog's ``adapter`` tools. Everything here is
read-only and passive.
"""

from __future__ import annotations

import json
import socket
from typing import Any

import requests

USER_AGENT = "OSINT-Toolkit/0.1 (+https://github.com/; educational)"
DEFAULT_TIMEOUT = 20


def _get(url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs: Any) -> requests.Response:
    headers = {"User-Agent": USER_AGENT}
    headers.update(kwargs.pop("headers", {}))
    resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp


# --------------------------------------------------------------------------
# Domain / DNS
# --------------------------------------------------------------------------

def dns_lookup(target: str, **_):
    """Resolve common DNS record types for a domain."""
    import dns.resolver

    records: dict[str, Any] = {}
    for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"):
        try:
            answers = dns.resolver.resolve(target, rtype, lifetime=10)
            records[rtype] = [str(r.to_text()) for r in answers]
        except Exception as exc:  # noqa: BLE001
            records[rtype] = []
            records.setdefault("_errors", {})[rtype] = type(exc).__name__
    return {
        "summary": f"DNS records for {target}",
        "target": target,
        "records": records,
    }


def whois_lookup(target: str, **_):
    """WHOIS registration data for a domain."""
    import whois

    data = whois.whois(target)
    if isinstance(data, dict):
        cleaned = {k: (str(v) if not isinstance(v, (list, str, int, type(None))) else v)
                   for k, v in data.items()}
    else:
        cleaned = {k: str(v) for k, v in data.__dict__.items()}
    return {"summary": f"WHOIS for {target}", "target": target, "whois": cleaned}


def rdap_lookup(target: str, **_):
    """Registration data from RDAP (modern WHOIS alternative)."""
    data = _get(f"https://rdap.org/domain/{target}").json()
    summary = f"RDAP for {target} ({data.get('ldhName', target)})"
    return {"summary": summary, "target": target, "rdap": data}


def crtsh_lookup(target: str, **_):
    """Certificate Transparency subdomains via crt.sh."""
    resp = _get(f"https://crt.sh/?q=%25.{target}&output=json", timeout=40)
    rows = resp.json()
    names = sorted({r.get("name_value", "").replace("\n", " ").strip()
                    for r in rows if r.get("name_value")})
    hosts = sorted({n.lstrip("*.") for n in names if n})
    return {
        "summary": f"{len(hosts)} hostnames seen in CT logs for {target}",
        "target": target,
        "hostnames": hosts[:2000],
    }


# --------------------------------------------------------------------------
# IP / network
# --------------------------------------------------------------------------

def ip_lookup(target: str, **_):
    """Registration and network info for an IP address."""
    from ipwhois import IPWhois

    obj = IPWhois(target)
    data = obj.lookup_rdap(depth=1)
    return {"summary": f"IP intelligence for {target}", "target": target, "ip": data}


# --------------------------------------------------------------------------
# Web / archives
# --------------------------------------------------------------------------

def wayback_lookup(target: str, **_):
    """Check whether the Wayback Machine has snapshots of a URL/domain."""
    resp = _get(
        "https://archive.org/wayback/available", params={"url": target}
    ).json()
    snap = resp.get("archived_snapshots", {}).get("closest", {})
    return {
        "summary": f"Wayback: {'snapshot found' if snap else 'no snapshot'} for {target}",
        "target": target,
        "snapshot": snap,
    }


def urlscan_search(target: str, **_):
    """Search public urlscan.io scans for a domain."""
    resp = _get(
        "https://urlscan.io/api/v1/search/", params={"q": f"domain:{target}"}
    ).json()
    results = [
        {"url": r.get("page", {}).get("url"), "scanned": r.get("task", {}).get("time")}
        for r in resp.get("results", [])[:50]
    ]
    return {
        "summary": f"{len(results)} public urlscan.io results for {target}",
        "target": target,
        "results": results,
    }


# --------------------------------------------------------------------------
# Username / identity (public only)
# --------------------------------------------------------------------------

def email_format(target: str, **_):
    """Basic, offline checks on an email address (no network)."""
    import re

    local, _, domain = target.partition("@")
    valid = bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", target))
    disposable = domain.lower() in {
        "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    }
    has_mx = False
    try:
        import dns.resolver
        has_mx = bool(dns.resolver.resolve(domain, "MX", lifetime=8))
    except Exception:  # noqa: BLE001
        has_mx = False
    return {
        "summary": f"Email format check for {target}",
        "target": target,
        "valid_syntax": valid,
        "local_part": local,
        "domain": domain,
        "domain_has_mx": has_mx,
        "likely_disposable": disposable,
    }


def phone_lookup(target: str, **_):
    """Parse a phone number offline and report country/carrier type."""
    import phonenumbers
    from phonenumbers import carrier, geocoder, number_type

    parsed = phonenumbers.parse(target, None)
    return {
        "summary": f"Phone metadata for {target}",
        "target": target,
        "valid": phonenumbers.is_valid_number(parsed),
        "possible": phonenumbers.is_possible_number(parsed),
        "country_code": parsed.country_code,
        "region": geocoder.description_for_number(parsed, "en"),
        "carrier": carrier.name_for_number(parsed, "en"),
        "line_type": str(number_type(parsed)),
        "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
    }


# --------------------------------------------------------------------------
# Network primitives (passive)
# --------------------------------------------------------------------------

def reverse_dns(target: str, **_):
    """Reverse DNS (PTR) for an IP address."""
    host = socket.gethostbyaddr(target)[0]
    return {"summary": f"PTR for {target}: {host}", "target": target, "hostname": host}


def nominatim_geocode(target: str, **_):
    """Geocode a place name or address using OpenStreetMap's Nominatim."""
    resp = _get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": target, "format": "json", "limit": 5},
        headers={"Referer": "https://example.com/"},
    )
    rows = resp.json()
    simplified = [
        {
            "display": r.get("display_name"),
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "type": r.get("type"),
        }
        for r in rows
    ]
    return {
        "summary": f"{len(simplified)} matches for '{target}'",
        "target": target,
        "results": simplified,
    }


def http_headers(target: str, **_):
    """Fetch HTTP response headers and note a few security-relevant ones."""
    url = target if target.startswith(("http://", "https://")) else f"https://{target}"
    resp = _get(url)
    headers = dict(resp.headers)
    interesting = {
        k: headers[k]
        for k in headers
        if k.lower() in {
            "server", "x-powered-by", "strict-transport-security",
            "content-security-policy", "x-frame-options",
            "x-content-type-options", "referrer-policy",
        }
    }
    return {
        "summary": f"HTTP {resp.status_code} from {url}",
        "target": target,
        "status": resp.status_code,
        "security_headers": interesting,
        "all_headers": headers,
    }
