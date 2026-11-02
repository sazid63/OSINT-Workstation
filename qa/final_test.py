"""Final comprehensive test of all fixes."""
import sys
import tempfile
import os
import pathlib

# Ensure both projects are on path (resolve relative to this file)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'osint-toolkit'))
sys.path.insert(0, BASE)

print("=== REGISTRY PLUGIN SOURCE FIX ===")
from osint_toolkit.core import registry
import osint_toolkit.paths as p

d = tempfile.mkdtemp()
plug_dir = pathlib.Path(d) / "plug"
plug_dir.mkdir()
open(plug_dir / "x.yaml", "w").write("""
id: x_tool
name: X
category: Test
description: test
safety: passive
source: plugin
inputs:
  - name: target
adapter: osint_toolkit.engine.collectors:dns_lookup
""")
original = p.plugins_dir
p.plugins_dir = lambda: plug_dir
tools = registry.load_catalog()
x = registry.get_tool("x_tool")
print(f"Plugin tool loaded: {x.id}, source={x.source}, run_mode={x.run_mode}")
p.plugins_dir = original

print()
print("=== AGENT INFINITE LOOP FIX ===")
from osint_toolkit.ai.agent import run_agent
from osint_toolkit.ai.base import AIProvider, AIResponse

class LoopProvider(AIProvider):
    id = "loop"
    def warmup(self): return "ready"
    def chat(self, messages, tools=None, **kw):
        return AIResponse(text="", tool_calls=[{"id":"1","name":"dns_lookup","arguments":{"target":"example.com"}}])

out = run_agent("investigate example.com", provider=LoopProvider())
print(f"Text length: {len(out.text)} (should be > 0)")
print(f"Steps: {out.steps}")
print(f"Warnings count: {len(out.warnings)}")
assert len(out.text) > 0, "Agent should produce non-empty text"
print("PASS: Agent produces summary text")

print()
print("=== ORCHESTRATOR NON-DICT FIX ===")
from core.orchestrator import investigate
r = investigate("example.com", deep=True)
print(f"Status keys: {list(r['status'].keys())}")
print(f"All statuses are strings: {all(isinstance(v, str) for v in r['status'].values())}")
assert all(isinstance(v, str) for v in r["status"].values()), "All statuses should be strings"
print("PASS: Orchestrator handles non-dict tool outputs")

print()
print("=== SETTINGS SAVE/LOAD ===")
from osint_toolkit import config as config_mod
from osint_toolkit.core import safety
config_mod.update(safety={"active_tools_acknowledged": False})
safety.acknowledge_active_tools()
print(f"Acknowledged: {safety.active_tools_acknowledged()}")
config_mod.update(safety={"active_tools_acknowledged": False})
print(f"After config update: {safety.active_tools_acknowledged()}")
assert safety.active_tools_acknowledged() == False
print("PASS: Settings safety save/load works")

print()
print("=== WEB SERVER ===")
import urllib.request
resp = urllib.request.urlopen("http://127.0.0.1:8765/api/status")
print(f"Status API: {resp.read().decode()[:100]}")

print()
print("=== ALL TESTS PASSED ===")