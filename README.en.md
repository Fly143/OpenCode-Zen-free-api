# zen — OpenCode Zen Free Models Direct-Access Toolkit

**English** | [简体中文](./README.md)

The `*-free` models on `https://opencode.ai/zen/v1` are protected by a
**client fingerprint check**. Third-party clients calling the endpoint directly get:

```
403 FreeTierError: OpenCode's free tier can only be used from within OpenCode
```

**rikkahub** additionally has a source-level bug: for any request whose
`host == "opencode.ai"` it forcibly injects a UUID-formatted `x-opencode-session`
header **after** custom headers (overwriting yours), while the server only accepts
the `ses_` format → guaranteed 403.

This toolkit provides a **local reverse proxy** that injects all required
headers/body fields, so any OpenAI-compatible client just points at it.

## Files

| File | Purpose |
|---|---|
| `zen_relay.py` | Core local reverse proxy. Injects compliant headers/body, strips dirty sessions, relays SSE; **automatically aggregates SSE into JSON for non-streaming clients** (the server only accepts `stream:true`, but some client paths expect plain JSON). `python3 zen_relay.py [port]`, default 8787 |
| `zen_free.py` | Minimal direct-call example: `python3 zen_free.py [model] [prompt]` |
| `zen_check.py` | Self-test (merges 9 one-off probe scripts): `python3 zen_check.py [basic\|ablate\|host\|relay]` |
| `README.md` | Chinese readme (switch via link at top) |
| `README.en.md` | English readme (this page) |
| `CHANGELOG.md` | Change log (pre-baseline part reconstructed from test records) |

## Setup (rikkahub via relay)

1. Start the relay **in an environment you control** (any persistent terminal on
   the same device — Termux on the same phone, PC, NAS, cloud host — as long as
   rikkahub can reach `IP:port`; do NOT run it in an ephemeral per-command sandbox):
   ```bash
   python3 /workspace/zen/zen_relay.py 8787
   ```
   Keep-alive form: `nohup python3 -u zen_relay.py 8787 >> relay.log 2>&1 &`
2. rikkahub provider settings:

| Item | Value |
|---|---|
| Base URL | `http://127.0.0.1:8787/zen/v1` |
| API Key | `public` (not verified server-side) |
| Model ID | `mimo-v2.6-flash-free` |
| Custom Headers/Body | none needed — the relay injects everything |

Why this works: rikkahub's hard-coded override only triggers for
`host == "opencode.ai"`; pointing at `127.0.0.1` bypasses it, and the app's
manifest declares `usesCleartextTraffic="true"` so plain http is allowed.

## Checksum of required conditions (measured 2026-09-22, re-verify with `zen_check.py ablate`)

| Condition | If not met |
|---|---|
| `x-opencode-session` = `ses_` + 12 hex + 14 alnum chars | 403 |
| `User-Agent` = `opencode/1.18+` (case-insensitive) | 403; 1.17 → 426 |
| body `stream: true` | 403 |
| body `tools` contains the four tools bash/glob/grep/read (missing any one) | 403 |
| `Authorization` | may be omitted |
| `x-opencode-request/client/project` | not required |

## Approaches that were tested and DO NOT work (don't retry)

- Subdomains like `www/api/app.opencode.ai` → 404/HTML fake 200
- Trailing-dot domain `opencode.ai.` → accepted by the server, but certificate
  hostname mismatch; rikkahub has no "trust all certificates" switch
- Case-variant duplicate session headers / comma-joined values → 403

## Known risks

- The vendor keeps tightening detection (multiple changes reported on linux.do
  since mid-2026-09); static headers may break at any time. With the relay you
  only need to touch `zen_relay.py`.
- Long-term fix: submit a PR to rikkahub — make `configureSessionHeaders()`
  not overwrite a user-supplied header, and/or format the value as `ses_...`.

## Repository

https://github.com/Fly143/OpenCode-Zen-free-api
