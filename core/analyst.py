"""Local AI ANALYST (Ollama) — reasons over collected evidence only.

The model may connect evidence, spot patterns, and offer clearly-labeled
inferences, but it must never manufacture specific identity attributes
(handles, emails, phones, URLs, account ownership) the evidence doesn't
contain, and never present pretrained knowledge as collected evidence.
Output is labeled AI-GENERATED and evidence-grounded.
"""
import os, json, requests

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')

def available() -> str | None:
    try:
        tags = requests.get(f'{OLLAMA_URL}/api/tags', timeout=10).json().get('models', [])
        have = {m.get('name', '').split(':')[0] for m in tags}
        for m in ['llama3.2', 'qwen3', 'qwen2.5-coder']:
            if m in have:
                return next(t.get('name') for t in tags if t.get('name', '').startswith(m))
        return tags[0].get('name') if tags else None
    except Exception:
        return None

PROMPT = """You are an OSINT report analyst. Below is a JSON list of collected findings, each with tool, value, source, and confidence level (CONFIRMED / HIGH / MEDIUM / LOW / UNVERIFIED).

You may reason over this evidence: connect related findings, identify patterns and relationships the evidence supports, and offer inferences — but every inference MUST be labeled as inference/possibility (e.g. "possibly", "may suggest", "unverified") and must never be stated as fact.

Hard rules:
- NEVER invent specific identity attributes: usernames, Twitter/X or Instagram handles, email addresses, phone numbers, URLs, account names, or account ownership. If it is not in the evidence, do not write it.
- NEVER guess a social-media handle from a person's name or naming pattern.
- NEVER claim an account belongs to the target unless the evidence supports that relationship. A handle merely observed in evidence (e.g. "@name appears on a public page") must be reported as observed with ownership explicitly not established.
- If a specific identifier is not supported by the evidence, say so plainly, e.g. "No Twitter/X handle was established from the collected evidence."
- Do NOT use your pretrained knowledge as evidence. Only the findings below count as evidence; your training data may inform how you reason, never what you report as fact.
- NEVER fabricate sources, URLs, findings, evidence, timestamps, or search results.
- Cite supporting findings as [n] where natural. Keep the existing confidence vocabulary; do not upgrade an inference to CONFIRMED/HIGH/MEDIUM by reasoning alone.

Produce: 1) 3-5 sentence summary 2) key relationships 3) contradictions worth checking (report, don't resolve by intuition) 4) 3 suggested next legitimate public sources/queries.
Keep under 300 words. Findings:
{items}"""

def analyze(inv_path: str, findings: list, max_items=60, model: str = None, options: dict = None) -> dict:
    model = model or available()
    if not model:
        return {'status': 'unavailable', 'reason': 'Ollama not reachable at ' + OLLAMA_URL}
    items = [{'n': i, 'tool': f.get('tool'), 'level': f.get('level'),
              'value': (f.get('value') or '')[:200], 'source': (f.get('source') or '')[:120]}
             for i, f in enumerate(findings[:max_items])]
    try:
        opts = {'num_predict': 500}
        opts.update(options or {})
        text = ''
        for _ in range(2):  # one retry on empty generation
            r = requests.post(f'{OLLAMA_URL}/api/generate',
                              json={'model': model, 'prompt': PROMPT.format(items=json.dumps(items)),
                                    'stream': False, 'options': opts}, timeout=240)
            text = r.json().get('response', '').strip()
            if text:
                break
            import time as _t
            _t.sleep(5)
        if not text:
            return {'status': 'empty', 'model': model,
                    'reason': 'model returned no text; evidence unchanged in findings.json'}
        labeled = (f"AI-GENERATED ANALYSIS — grounded in collected evidence only "
                   f"(model: {model}; verify claims against findings.json)\n\n{text}")
        with open(os.path.join(inv_path, 'reports', 'analyst.md'), 'w', encoding='utf-8') as fh:
            fh.write(labeled)
        return {'status': 'ok', 'model': model}
    except Exception as e:
        return {'status': 'error', 'error': str(e)[:200]}
