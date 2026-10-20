# zen — OpenCode Zen free models as an OpenAI-compatible endpoint

**English** | [简体中文](./README.md)

`oc_bridge.py` uses the **official opencode client** (`opencode serve`) as its
transport and exposes it as an OpenAI-compatible endpoint — any client
(rikkahub, dsh, mimo code, …) just points at a Base URL and can use Zen's
`*-free` models.

> Zen's free tier gates on the client itself; third-party calls get
> `403 FreeTierError: OpenCode's free tier can only be used from within OpenCode`.
> This tool does **not** impersonate the client — it runs a real opencode process
> to make the call, so it passes the gate. See
> [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md) for the evidence.

```
your client (rikkahub / dsh / mimo code / …)
      │  POST /v1/chat/completions
      ▼
oc_bridge.py (:8790)                       ← this repo, zero dependencies
      │  POST /session , POST /session/{id}/message
      ▼
opencode serve (:4097, official client binary)
      │  POST /inference/v1/chat/completions
      ▼
opencode.ai Zen gateway  ✅
```

## Quick start

```bash
# one-click (Linux / macOS / Termux / WSL)
./start.sh                    # auto-find/install opencode, run in foreground
./start.sh --bg               # run in background (log: oc_bridge.log)
./start.sh --port 9000        # change port
```

On Windows, double-click `start.bat`.

> The launcher is **idempotent**: it resolves `opencode` by absolute path
> (PATH / npm global dir / common locations) and installs only when it is truly
> missing (usually just the first time), then uses it directly — no PATH needed.

Client settings:

| Item | Value |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API Key | anything (not verified) |
| Model ID | `mimo-v2.6-flash-free` |
| Custom Headers/Body | none needed |

## System prompt

By default opencode attaches a large agent system prompt; **this tool already
replaces it with a minimal one**:

| Goal | How to start |
|---|---|
| **Default**: minimal prompt (≈1 KB) | `./start.sh` |
| Custom minimal prompt text | `./start.sh --prompt "You are a terse assistant."` |
| Restore opencode's default (≈9.5 KB) | `./start.sh --full-prompt` |

(How: `oc_bridge.py` injects a minimal `bridge` agent via the
`OPENCODE_CONFIG_CONTENT` env var, **merged** with your own `opencode.json` —
your file is not modified.)

**Used as a backend for other coding agents**: their `system` messages are
**forwarded verbatim** (via opencode's `system` field, not squashed into the
user text), so their own system prompts still apply. Verified: a downstream
"output JSON only" instruction produced pure JSON.

## Manual start / options

```bash
python3 oc_bridge.py --port 8790 --oc-port 4097
#   --opencode-bin PATH   path to the opencode binary (default: found on PATH)
#   --home DIR            HOME for opencode (config/credentials dir)
#   --mode stateless|stateful   default stateless (new session per request)
#   --free-models a,b,c   override the allowed model-id list
#   --prompt TEXT         minimal system prompt text (default "You are a helpful assistant.")
#   --full-prompt         use opencode's default full system prompt
#   --agent NAME          opencode agent to use (default bridge, the injected minimal one)
```

`oc_bridge.py` starts (or reuses) `opencode serve` itself.

## Verified

| Test | Result |
|---|---|
| `GET /v1/models` | ✅ 200 |
| `POST /v1/chat/completions` (non-stream) | ✅ 200, real completion |
| `POST /v1/chat/completions` (`stream:true`) | ✅ proper SSE chunks + `[DONE]` |
| Other free models (see list below) | ✅ 200 |

### Free model availability (probed individually, 2026-10-20)

| Model | Status | First token |
|---|---|---|
| `minimax-m3.1-flash-free` | ✅ | 1.6s |
| `deepseek-v4.1-flash-free` | ✅ | 2.4s |
| `nemotron-3.5-lightning-free` | ✅ | 3.8s |
| `nemotron-3.5-super-vl-free` | ✅ | 4.2s |
| `longcat-2.5-preview-free` | ✅ | 6.1s |
| `mimo-v2.6-flash-free` | ✅ | ~9s |
| `glm-5.3-flash-free` | ✅ | 9.5s |
| `beam-free` | ⚠️ HTTP 200 but usually empty text | — |
| `step-5-preview-free` / `space-bunny-free` / `jev-1.13-free` | ❌ HTTP 500 | — |
| `big-pickle` | ❌ gone from `/v1/models` | — |

## Caveats

- Requires the opencode binary at runtime (on Android/Termux: install node, then
  `npm i -g opencode-ai`).
- opencode's tool definitions (~23 KB) are still sent — an **inherent cost**
  that config cannot remove (both the gate and the client rely on them).
- Free access is **region**-gated: from an HK egress, `cat-jam-free` and
  `muse-spark-1.2/1.3` return `403 RegionError`.
- This is "being the real client", not "impersonating it" — still a grey area.
  Heavy use may be targeted; for anything serious, use a paid key.

## Files

| File | Purpose |
|---|---|
| `oc_bridge.py` | Core. Wraps the real opencode client as an OpenAI-compatible endpoint (`:8790`) |
| `start.sh` / `start.bat` | One-click launchers (Linux/macOS/Termux/WSL, Windows) |
| `opencode.json.example` | Optional config sample (for managing the `bridge` agent by hand) |
| `FINDINGS-2026-10-15.md` | Design rationale + measurements (Chinese) |
| `CHANGELOG.md` | Change log |

## Related

- The early "spoofed headers" approach (dead) is archived on branch
  **`legacy-header-spoof`**: `git checkout legacy-header-spoof`.
- Repository: https://github.com/Fly143/OpenCode-Zen-free-api
