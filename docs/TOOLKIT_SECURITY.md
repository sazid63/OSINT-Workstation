# Security Policy

## Reporting a vulnerability

If you find a security issue in the OSINT Toolkit, please report it
responsibly. **Do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting
(**Security** tab → **Report a vulnerability**) on the repository.

Please include:

- a description of the issue and its impact;
- steps to reproduce;
- affected version / commit;
- any suggested fix.

We aim to acknowledge reports within a few days.

## Design principles that keep users safe

The Toolkit is built so that a normal user cannot accidentally harm their own
machine, leak their own secrets, or be turned into an attack tool.

1. **Local-first, zero telemetry.** No analytics, no phone-home, no accounts.
2. **No secrets in the repo.** API keys live in the OS keychain or a
   git-ignored `.env`. The repo ships only `.env.example`.
3. **No secrets in logs or AI prompts.** Values are redacted before logging and
   before any cloud AI request.
4. **No arbitrary code execution.** The AI can only call *registered tools* with
   validated, typed arguments — never a shell.
5. **Sandboxed execution.** External tools run as subprocesses using argument
   arrays (never a shell string), with timeouts and rate limits.
6. **Verified downloads.** External tools and updates are fetched from official
   releases and checked against SHA-256 hashes.
7. **No silent updates.** Updates are user-initiated.
8. **Capability line.** The software contains no authentication-bypass,
   CAPTCHA/paywall-circumvention, credential-attack, or private-data-scraping
   functionality.

## Handling of user data

- Investigations and results are stored under your local user profile
  (`%LOCALAPPDATA%\OSINT Toolkit` on Windows), never inside the repository.
- Deleting a workspace deletes its data locally.

## Dependencies

Third-party tools are installed on demand from their official sources and are
**not** vendored into this repository. Each tool keeps its own license, shown in
the app.
