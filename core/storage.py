"""Investigation storage layout."""
import os, re, json, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = os.path.join(BASE, 'investigations')

SUBDIRS = ['metadata', 'raw', 'normalized', 'sources', 'screenshots', 'graph', 'logs', 'reports']

def safe_name(target: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', target.strip())[:80]

def create_investigation(target: str, target_type: str, plan: list) -> dict:
    day = datetime.datetime.now().strftime('%Y-%m-%d')
    base = f"{day}_{safe_name(target)}"
    path = os.path.join(INV, base)
    # never overwrite: suffix _2, _3...
    n, final = 1, path
    while os.path.exists(final):
        n += 1
        final = f"{path}_{n}"
    for sub in SUBDIRS:
        os.makedirs(os.path.join(final, sub), exist_ok=True)
    inv_id = os.path.basename(final)
    meta = {
        'id': inv_id, 'target': target, 'target_type': target_type,
        'plan': plan, 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'path': final,
    }
    with open(os.path.join(final, 'metadata', 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    return meta

def inv_path(inv_id: str) -> str:
    return os.path.join(INV, inv_id)

def save_raw(inv_id: str, tool: str, data) -> str:
    import json as j
    p = os.path.join(inv_path(inv_id), 'raw', f'{tool}.json')
    with open(p, 'w', encoding='utf-8') as f:
        j.dump(data, f, indent=2, default=str)
    return p
