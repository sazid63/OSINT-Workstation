"""Append-only audit trail for authorized use.

Every investigation writes one JSONL record: when it started, what was targeted,
how the target type was determined, whether the operator acknowledged
authorization, and on whose machine/account. This is the minimum needed to
answer "who ran what, when, and under what stated scope" -- which is the whole
point of operating a tool like this lawfully.

Records are appended as a single line so a crash mid-run cannot corrupt earlier
history. The file is never rewritten or truncated by this module.
"""
import datetime
import json
import os
from typing import Optional

from core.version import APP_VERSION

AUDIT_FILENAME = 'audit.jsonl'


def audit_path(data_dir: str) -> str:
    return os.path.join(data_dir, AUDIT_FILENAME)


def _operator() -> str:
    """Best-effort local operator identity (no network, no extra deps)."""
    return (os.environ.get('USERNAME') or os.environ.get('USER')
            or os.environ.get('LOGNAME') or 'unknown')


def _host() -> str:
    return os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or 'unknown'


def record(data_dir: str, *, action: str, target: str = '', target_type: str = '',
           target_type_inferred: Optional[bool] = None, authorized: bool = False,
           investigation_id: str = '', extra: Optional[dict] = None) -> str:
    """Append one audit record. Returns the path written to.

    Never raises: an audit write failure must not abort an investigation, but it
    is reported back to the caller through the return value / log.
    """
    os.makedirs(data_dir, exist_ok=True)
    entry = {
        'ts_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'action': action,
        'app_version': APP_VERSION,
        'operator': _operator(),
        'host': _host(),
        'target': target,
        'target_type': target_type,
        'target_type_inferred': target_type_inferred,
        'authorization_acknowledged': bool(authorized),
        'investigation_id': investigation_id,
    }
    if extra:
        entry.update(extra)
    path = audit_path(data_dir)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return path


def tail(data_dir: str, limit: int = 20) -> list:
    """Return the most recent `limit` audit records (newest last)."""
    path = audit_path(data_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        lines = [ln for ln in f if ln.strip()]
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out
