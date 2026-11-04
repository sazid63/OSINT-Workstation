# OSINT Toolkit

A **local, open-source, educational OSINT desktop toolkit**. It runs entirely on
your machine, uses **free and open-source tools only**, and helps you gather
public information from public sources — with clear, plain-English instructions
for every tool.

> **Educational / lawful use only.** You are responsible for how you use this
> software. Read [DISCLAIMER.md](DISCLAIMER.md) before you start.

---

## Highlights

- 🖥️ **Native desktop app** (PySide6/Qt) with an OSINT-themed dark UI.
- 🧰 **A catalog of well-known, free & open-source OSINT tools**, each with a
  "how to use" and "what to connect" panel written for non-experts.
- ➕➖ **Add or remove tools** — enable/disable built-ins and drop in your own
  plugins.
- 📥 **Auto-install external tools** (e.g. nmap, ExifTool, Amass, subfinder)
  on demand, from official releases, **SHA-256 verified**.
- 🤖 **Optional AI assistant** — connect a **local** model (Ollama, LM Studio)
  or a **cloud** provider (OpenAI-compatible, Anthropic, Gemini) with your own
  key. The AI can *use the toolkit* through a constrained, allow-listed tool API.
- 🔌 **OpenCode integration** — expose the toolkit to OpenCode (and any MCP
  client) as an **MCP server**, and/or drive a local OpenCode server from the app.
- 🌐 **Optional loopback web view** (`127.0.0.1` only) if you prefer a browser.

## Safety first

- **Local-first, zero telemetry.** No account, no tracking, nothing phones home.
- **Your secrets stay with you.** Keys live in your OS keychain or a git-ignored
  `.env`; they are redacted from logs and from AI requests.
- **No arbitrary code execution.** The AI can only call registered tools with
  validated arguments — never a shell.
- **Sandboxed & rate-limited.** External tools run as subprocesses with timeouts
  and politeness limits.
- **Capability line.** No authentication bypass, no CAPTCHA/paywall
  circumvention, no credential attacks, no private-data scraping.
- **Active tools are gated.** Port scanners and similar tools require a one-time
  responsible-use acknowledgment.

See [SECURITY.md](SECURITY.md) and [DISCLAIMER.md](DISCLAIMER.md).

---

## Install

### Prebuilt (Windows)

1. Download `OSINT-Toolkit-Setup-x.y.z.exe` from **Releases**.
2. Verify the SHA-256 shown on the release page (optional but recommended).
3. Run the installer, then launch **OSINT Toolkit**.

### From source

```bash
git clone https://github.com/sazid63/OSINT-Toolkit
cd osint-toolkit
uv venv
uv pip install -e ".[mcp]"
python -m osint_toolkit
```

Requires Python 3.11+.

---

## Using it

1. Open the app and accept the responsible-use notice.
2. Browse **Tools**, pick one, read the **How to use** and **What to connect**
   panels, enter a target, and run it.
3. Results are saved to your local workspace and shown in **Results**.
4. (Optional) Open **Settings → AI** and connect a local or cloud model, then use
   the **AI Assistant** to plan and run tools for you.

Workspace location: `%LOCALAPPDATA%\OSINT Toolkit` (Windows), outside the repo.

---

## Connecting AI

| Mode | What you need |
|---|---|
| Local — Ollama | Ollama running (default `http://localhost:11434`) |
| Local — LM Studio / llama.cpp | An OpenAI-compatible server (default `http://localhost:1234/v1`) |
| Cloud — OpenAI-compatible | Base URL + API key (OpenAI, OpenRouter, Groq, …) |
| Cloud — Anthropic | API key |
| Cloud — Google Gemini | API key |
| OpenCode | A local OpenCode server URL |

Cloud keys are stored locally and are **never** sent anywhere except the provider
you chose. Local and offline tools send nothing.

---

## OpenCode integration

Register the toolkit as an MCP server so OpenCode agents can use your tools:

```bash
osint-toolkit-mcp            # stdio MCP server
```

Then in OpenCode, add it as an MCP server and its tools become available to
agents. You can also point the app at a running OpenCode server under
**Settings → AI → OpenCode**.

---

## Adding tools

Drop a manifest (and optional adapter) into `plugins/`, or contribute one under
`tools/`. See [docs/adding-tools.md](docs/adding-tools.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE). Third-party tools keep their own licenses, shown
in the app, and are installed on demand rather than bundled.
