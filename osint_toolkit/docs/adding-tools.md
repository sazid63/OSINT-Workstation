# Adding tools

Drop a manifest (and optional adapter) into `plugins/` and the app will load it.

## Manifest schema (`.yaml` or `.yml`)

```yaml
id: my_tool
name: My Tool
category: Domain & DNS
description: Short, clear description.
how_to_use: |
  1. Type a target...
  2. Click Run...
  3. Read the results...
important: |                # optional; shown for active tools or important notes
  ACTIVE TOOL - only on systems you own or are authorized to test.
what_to_connect: []         # bullet list shown to user (binary, api key, etc.)
safety: passive             # passive | active
license: MIT
homepage: https://...
tags: [dns, custom]
inputs:
  - name: target
    label: Domain
    placeholder: example.com
    type: text               # text | select | bool
    required: true
    help: "What to enter"
    options: []
# Run mode (pick ONE):
adapter: mypackage.func     # pure-Python function taking **inputs
command: ["tool", "{target}"]  # external binary with {placeholders}
url: "https://example.com/search?q={target}"  # opens in browser
install:
  method: pip | binary
  package: mypackage        # if pip
  url: https://...          # if binary
```

## Pure-Python adapter

```python
# plugins/mytool.py
def run(target: str, **_):
    return {"summary": f"Did something for {target}", "data": {...}}
```

Manifest: `adapter: plugins.mytool:run`

## External binary

The app uses an argv list (never a shell). Placeholders `{target}` are substituted.
Binaries can be auto-downloaded if you set `install.url`; or put them in
`%LOCALAPPDATA%\OSINT Toolkit\bin\`.

## Validation

The app validates inputs against the schema and redacts secrets from all output.
Active tools require the one-time authorization acknowledgment.
