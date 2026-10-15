# zen — OpenCode Zen Free-Model Toolkit

**English** | [简体中文](./README.md)

## 2026-10-15 update: the old "spoof the headers" path is dead

The `*-free` models on `https://opencode.ai/zen/v1` now check for client
characteristics **beyond the request contents**. As measured (see
[`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md)), replaying the official
client's request **byte-for-byte** (headers, body, header order — even matching
the TLS ClientHello) still returns:

```
403 FreeTierError: OpenCode's free tier can only be used from within OpenCode
```

On the same machine, from the same egress IP, only the **official client process
itself** gets a 200. So this repo's old path — `zen_relay.py` injecting a few
headers — **no longer works**. Do not rely on it.

## Recommended: `oc_bridge.py` (don't imitate it — use the real client)

The gate blocks the client, not the request, so let the official client make the
call. opencode ships a headless server (`opencode serve`) that runs inside the
real client process and passes the gate. `oc_bridge.py` translates its HTTP API
into an OpenAI-compatible endpoint:

```
rikkahub / any OpenAI client
      │  POST /v1/chat/completions
      ▼
oc_bridge.py (:8790)                       ← this repo, zero dependencies
      │  POST /session , POST /session/{id}/message
      ▼
opencode serve (:4097, real client binary)
      │  POST /inference/v1/chat/completions
      ▼
opencode.ai Zen gateway  ✅
```

### Quick start (one-click scripts)

```bash
# Linux / macOS / Termux / WSL
./start.sh                    # auto-find/install opencode, run in foreground
./start.sh --bg               # run in background (log: oc_bridge.log)
./start.sh --port 9000 --mode stateful
```

On Windows, just double-click `start.bat` (same auto-find/install behaviour).

> The launchers are **idempotent**: they resolve `opencode` by absolute path
> (PATH, the npm global dir, common locations) and **install only when it is
> truly missing** (usually just the first time). Once found, the absolute path is
> passed straight to the bridge, so it never depends on PATH.

### Usage (manual)

```bash
# A real opencode binary is required where you run it:
npm i -g opencode-ai          # or brew / pacman / docker — see opencode docs
# On Android/Termux: install node, then the same npm command.

python3 oc_bridge.py --port 8790 --oc-port 4097
# Options:
#   --opencode-bin PATH   path to the opencode binary (default: found on PATH)
#   --home DIR            HOME for opencode (config/credentials dir)
#   --mode stateless|stateful   default stateless (new session per request)
#   --free-models a,b,c   override the allowed model-id list
```

Client (rikkahub) provider settings:

| Item | Value |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API Key | anything (not verified) |
| Model ID | `mimo-v2.6-flash-free` |
| Custom Headers/Body | none needed |

`oc_bridge.py` starts (or reuses) `opencode serve` itself.
rikkahub can use plain http (the app manifest declares `usesCleartextTraffic="true"`).

### Verified

Measured in-sandbox (same egress IP where every Python/Node/Bun replay got 403):

| Test | Result |
|---|---|
| `GET /v1/models` | ✅ 200 |
| `POST /v1/chat/completions` (non-stream) | ✅ 200, real completion |
| `POST /v1/chat/completions` (`stream:true`) | ✅ proper SSE chunks + `[DONE]` |
| Other free models, e.g. `step-5-preview-free` | ✅ 200 |

### Caveats

- Requires the opencode binary at runtime (heavier than a pure-Python relay).
- Requests carry opencode's own system prompt / tool definitions, so the context
  is larger than a raw call.
- Free access is now **region**-gated: from an HK egress, `cat-jam-free` and
  `muse-spark-1.2/1.3` return `403 RegionError`.
- This is "being the real client", not "impersonating it" — still a grey area.
  Heavy use may be targeted; for anything serious, use a paid key.

## Files

| File | Purpose |
|---|---|
| `oc_bridge.py` | **Recommended.** Wraps the real opencode client as an OpenAI-compatible endpoint (`:8790`) |
| `start.sh` / `start.bat` | One-click launchers (Linux/macOS/Termux/WSL, Windows): auto-find/install opencode and start the bridge |
| `zen_free.py` | Minimal direct-call example (**dead**, kept for reference) |
| `zen_relay.py` | Local reverse proxy that injected headers/body (**dead**, kept as an archive; its SSE→JSON aggregation still works for any OpenAI-compatible upstream) |
| `zen_check.py` | Self-test / ablation script (**dead**, reflects the 2026-09 conditions) |
| `FINDINGS-2026-10-15.md` | Full 2026-10-15 re-check (evidence, captures, conclusion, `oc_bridge` validation) |
| `README.md` / `README.en.md` | Chinese / English readme |
| `CHANGELOG.md` | Change log |

## History (dead)

Back in 2026-09 the free endpoints let you through with a reproducible set of
header/body conditions (`ses_` session shape, `UA: opencode/≥1.18`, `stream:true`,
`tools` containing the core tool names); `zen_relay.py` injected those and relayed.
The server tightened it from 2026-09-17 onward; by 2026-10-15 it had become a
content-level check and static headers stopped working entirely. See
[`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md) for the byte-for-byte replay evidence.

## Repository

https://github.com/Fly143/OpenCode-Zen-free-api
