"""Regression tests: analyst must not manufacture identity attributes.
Prompt tests run offline; live tests need Ollama (skipped if unreachable)."""
import sys, os, re, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.analyst import PROMPT, available, analyze

HANDLE_RE = re.compile(r'(?<![\w/])@[\w.]{2,40}\b')
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
URL_RE = re.compile(r'https?://[^\s)>\]]+')

def test_prompt_forbids_invented_attributes():
    low = PROMPT.lower()
    for phrase in ['never invent specific identity attributes', 'never guess a social-media handle',
                   'was established from the collected evidence', 'labeled as inference',
                   'pretrained knowledge']:
        assert phrase in low, phrase

def test_prompt_does_not_demand_per_sentence_citations():
    low = PROMPT.lower()
    assert 'every factual claim must cite' not in low
    assert 'no id = no claim' not in low

def _run_case(findings):
    model = available()
    if not model:
        print('SKIP (Ollama unreachable)')
        return None
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'reports'))
    r = analyze(d, findings, model=model, options={'temperature': 0})
    assert r['status'] == 'ok', r
    return open(os.path.join(d, 'reports', 'analyst.md'), encoding='utf-8').read()

BASE = [
    {'tool': 'searxng', 'level': 'MEDIUM CONFIDENCE',
     'value': 'Example Person — https://en.wikipedia.org/wiki/Example_Person',
     'source': 'https://en.wikipedia.org/wiki/Example_Person'},
    {'tool': 'dns', 'level': 'CONFIRMED', 'value': 'A: 93.184.216.34', 'source': 'target DNS'},
]

def test_no_twitter_handle_invented_from_name():
    """Exact bug: evidence has a name but no handle; analyst must not emit @exampleperson."""
    text = _run_case(BASE)
    if text is None:
        return
    assert not re.search(r'@example[_.]?person\b', text, re.I), 'invented handle from name'
    assert not HANDLE_RE.search(text), 'no handle of any kind is in evidence, none should appear'
    if re.search(r'twitter|/x handle|instagram', text, re.I):
        assert re.search(r'not established|not (?:in|supported by) (?:the )?evidence|no evidence', text, re.I), \
            'any social-handle discussion must state it was not established'

def _unhedged_ownership_claims(text):
    own = re.compile(r'belongs to the target|owned by the target|is the target[\'’]s|confirmed to be the target', re.I)
    hedge = re.compile(r'not (?:explicitly |directly )?(?:confirmed|established|verified)|unclear|unverified|unknown|\bmay\b|might|possibly|possible|suggest|determine (?:if|whether)|to verify|needs verification', re.I)
    bad = []
    for s in re.split(r'(?<=[.!?])\s+', text):
        if own.search(s) and not hedge.search(s):
            bad.append(s)
    return bad

def test_observed_handle_not_assigned_to_target():
    findings = BASE + [{'tool': 'username', 'level': 'MEDIUM CONFIDENCE',
                        'value': 'github: https://github.com/exampledev',
                        'source': 'https://github.com/exampledev'}]
    text = _run_case(findings)
    if text is None:
        return
    bad = _unhedged_ownership_claims(text)
    assert not bad, f'unhedged ownership claims: {bad}'

def test_observed_email_and_url_not_altered():
    findings = BASE + [
        {'tool': 'harvester', 'level': 'MEDIUM CONFIDENCE',
         'value': 'email: contact@example.com', 'source': 'theHarvester passive'},
        {'tool': 'url', 'level': 'CONFIRMED',
         'value': 'https://example.com/page -> https://example.com/page [200]', 'source': 'live HTTP'}]
    text = _run_case(findings)
    if text is None:
        return
    evidence_text = ' '.join(f['value'] + ' ' + f['source'] for f in findings).lower()
    for em in set(EMAIL_RE.findall(text)):
        assert em.lower() in evidence_text, f'email not from evidence: {em}'
    for u in set(URL_RE.findall(text)):
        assert u.lower().rstrip('.,;)') in evidence_text, f'url not from evidence: {u}'

if __name__ == '__main__':
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = skipped = 0
    for name, fn in fns:
        try:
            fn()
            print(f'PASS {name}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL {name}: {e}')
    print(f'{len(fns) - failed}/{len(fns)} passed')
    sys.exit(1 if failed else 0)
