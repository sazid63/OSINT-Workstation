"""Optional loopback-only web view and JSON API (stdlib only).

Off by default. When enabled it binds to 127.0.0.1 and exposes the same guarded
runner over HTTP so you can drive the toolkit from a browser or a script.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..core import logging_setup, registry, runner, safety, workspace as ws_mod

log = logging_setup.get_logger("osint_toolkit.web")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>OSINT Toolkit (local)</title>
<style>
 body{background:#0b0f14;color:#c8d3e0;font-family:ui-monospace,Consolas,monospace;margin:2rem}
 h1{color:#00e5a0}.card{background:#11161d;border:1px solid #1f2a36;border-radius:8px;padding:1rem;margin:1rem 0}
 input,select{background:#0b0f14;color:#c8d3e0;border:1px solid #2a3a4d;padding:.4rem;margin:.2rem 0;width:100%}
 button{background:#00e5a0;color:#0b0f14;border:0;padding:.5rem 1rem;border-radius:6px;cursor:pointer;font-weight:bold}
 table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #1f2a36;padding:.4rem;text-align:left}
 .hide{display:none}pre{white-space:pre-wrap;background:#0b0f14;padding:.5rem;border-radius:6px}
</style></head><body>
<h1>OSINT Toolkit — local</h1>
<div id="status"></div>
<section class="card"><h2>Run a tool</h2>
<select id="tool"><option value="">Loading tools…</option></select>
<div id="inputs" class="hide"></div>
<button id="run" class="hide">Run</button>
</section>
<pre id="output"></pre>
<script>
let tools=[];
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(path,method,body){
 const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 return r.json();
}
async function load(){
 const res=await Promise.all([api('/api/tools'),api('/api/status')]);const tbl=res[0],st=res[1];tools=tbl.tools;
 document.getElementById('status').textContent=st.ok?'Ready':'Terms not accepted yet';
 const sel=document.getElementById('tool');sel.innerHTML='';tools.forEach(t=>{
  const o=document.createElement('option');o.value=t.id;o.textContent=`[${t.safety}] ${t.name} (${t.category})`;sel.appendChild(o);});
 document.getElementById('run').classList.remove('hide');
}
function renderInputs(){const id=document.getElementById('tool').value;const t=tools.find(x=>x.id===id);
 const wrap=document.getElementById('inputs');wrap.innerHTML=wrap.classList.remove('hide');
 (t.inputs||[]).forEach(inp=>{const lab=document.createElement('label');lab.textContent=inp.label||inp.name;
  const el=inp.type==='select'?document.createElement('select'):document.createElement('input');
  el.name=inp.name;el.placeholder=inp.placeholder||'';
  if(inp.type==='select'){inp.options.forEach(o=>{const oo=document.createElement('option');oo.value=o;oo.textContent=o;el.appendChild(oo);});}else{el.type='text';}
  wrap.appendChild(lab);wrap.appendChild(el);});
}
document.getElementById('tool').onchange=renderInputs;
document.getElementById('run').onclick=async()=>{
 const id=document.getElementById('tool').value;const t=tools.find(x=>x.id===id);const args={};
 (document.querySelectorAll('#inputs input,#inputs select')).forEach(el=>{if(el.value)args[el.name]=el.value;});
 const out=document.getElementById('output');out.textContent='Running…';
 const r=await api('/api/run','POST',{tool:id,inputs:args});
 out.textContent=JSON.stringify(r,null,2);
};
load().catch(e=>document.getElementById('status').textContent='Error: '+e);
</script></body></html>"""


def _registry_tool_payloads() -> list[dict[str, Any]]:
    return [t.to_dict() for t in registry.load_catalog()]


class Handler(BaseHTTPRequestHandler):
    server_version = "OSINT-Toolkit/0.1"

    def log_message(self, fmt, *args):  # noqa: D102
        log.info("web: %s %s", self.address_string(), fmt % args)

    def _send(self, code: int, payload: Any):
        body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/status":
            self._send(200, {"ok": safety.terms_accepted()})
        elif path == "/api/tools":
            self._send(200, {"tools": _registry_tool_payloads()})
        elif path == "/api/workspaces":
            self._send(200, {"workspaces": [{"name": w.name, "path": str(w.path)} for w in ws_mod.list_workspaces()]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            body = {}
        if path == "/api/run":
            tool = registry.get_tool(body.get("tool", ""))
            if tool is None:
                self._send(404, {"error": "unknown tool"})
                return
            try:
                result = runner.run_tool(tool, body.get("inputs") or {})
                self._send(200, result.to_dict())
            except runner.safety.NotAcceptedError as exc:
                self._send(403, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                log.exception("web run failed")
                self._send(500, {"error": str(exc)})
        elif path == "/api/terms/accept":
            try:
                safety.accept_terms()
                self._send(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": str(exc)})
        else:
            self._send(404, {"error": "not found"})


def start(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("web UI listening on http://%s:%s", host, port)
    return server