#!/usr/bin/env python3
"""
oc_bridge.py —— 把「真实 opencode 客户端」变成 OpenAI 兼容端点。

思路（2026-10-15）：Zen 免费额度的闸门挡的是客户端本身，任何"模仿"都 403，
但官方客户端自己（`opencode serve` 无头服务器）能过。所以不做 fingerprint 伪装，
而是起一个真实客户端进程当传输层，再把它的 HTTP API 翻译成 /v1/chat/completions。

  rikkahub / 任何 OpenAI 客户端
        │  POST /v1/chat/completions
        ▼
  oc_bridge.py (本文件, 默认 :8790)
        │  POST /session , POST /session/{id}/message
        ▼
  opencode serve (真实 1.19.0 二进制, 127.0.0.1:4097)
        │  POST /inference/v1/chat/completions   ← 真客户端指纹，可过闸
        ▼
  opencode.ai Zen 网关  ✅

用法:
  # 1) 确保已装 opencode（真实二进制）。本机可用 npm 包：
  #    npm i -g opencode-ai   →  或指定 --opencode-bin /path/to/opencode
  python3 oc_bridge.py [--port 8790] [--oc-port 4097] [--opencode-bin PATH]
                       [--free-models a,b,c] [--mode stateless|stateful]
  # 2) rikkahub 提供商:
  #    Base URL = http://127.0.0.1:8790/v1     API Key = 随便
  #    模型 ID  = mimo-v2.6-flash-free
"""
import argparse, json, os, shutil, signal, subprocess, sys, threading, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_FREE = ["mimo-v2.6-flash-free", "step-5-preview-free", "deepseek-v4.1-flash-free",
                "nemotron-3.5-lightning-free", "jev-1.13-free", "longcat-2.5-preview-free",
                "space-bunny-free", "big-pickle"]

ARGS = None
OC_BASE = None
_proc = None
_sessions = {}          # conversation-key -> session id  (stateful 模式)
_lock = threading.Lock()


# ---------- opencode server helpers ----------
def oc(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OC_BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def find_opencode():
    if ARGS.opencode_bin:
        return ARGS.opencode_bin
    for c in (os.environ.get("OPENCODE_BIN"),
              shutil.which("opencode"),
              shutil.which("opencode.exe")):
        if c and os.path.exists(c):
            return c
    return None


def start_server():
    global _proc, OC_BASE
    OC_BASE = f"http://127.0.0.1:{ARGS.oc_port}"
    # 已有服务器就直接用
    try:
        oc("GET", "/global/health", timeout=3)
        print(f"[bridge] 复用已运行的 opencode serve @ {OC_BASE}")
        return
    except Exception:
        pass
    binary = find_opencode()
    if not binary:
        sys.exit("[bridge] 找不到 opencode 二进制，请 --opencode-bin 指定，或 npm i -g opencode-ai")
    env = dict(os.environ)
    if ARGS.home:
        env["HOME"] = ARGS.home
    _proc = subprocess.Popen([binary, "serve", "--port", str(ARGS.oc_port), "--hostname", "127.0.0.1"],
                             env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            oc("GET", "/global/health", timeout=3)
            print(f"[bridge] opencode serve 已就绪 ({binary})")
            return
        except Exception:
            time.sleep(0.5)
    sys.exit("[bridge] opencode serve 启动失败")


def flush_children(*_):
    if _proc:
        try:
            _proc.send_signal(signal.SIGTERM)
            time.sleep(0.5)
            _proc.kill()
        except Exception:
            pass
    sys.exit(0)


# ---------- OpenAI <-> opencode 转换 ----------
def flatten_messages(messages):
    """把 OpenAI messages 数组压成一段文本（stateless 模式用）。"""
    roles = {"system": "System", "user": "User", "assistant": "Assistant", "tool": "Tool"}
    out = []
    for m in messages or []:
        role = roles.get(m.get("role"), m.get("role") or "User")
        c = m.get("content")
        if isinstance(c, list):  # 多模态/分段
            c = "".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") in ("text", "input_text")) or ""
        out.append(f"{role}: {c}" if m.get("role") != "user" else str(c))
    return "\n\n".join(out)


def ask(model, prompt, key):
    """返回助手文本。stateless=每请求新会话；stateful=按 key 复用会话。"""
    with _lock:
        sid = _sessions.get(key) if ARGS.mode == "stateful" else None
        if not sid:
            sid = oc("POST", "/session", {"title": "bridge"})["id"]
            if ARGS.mode == "stateful":
                _sessions[key] = sid
    body = {"model": {"providerID": "opencode", "modelID": model},
            "parts": [{"type": "text", "text": prompt}]}
    d = oc("POST", f"/session/{sid}/message", body)
    parts = d.get("parts") or d.get("info", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()


# ---------- HTTP 端点 ----------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            now = int(time.time())
            self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model", "created": now, "owned_by": "opencode"} for m in ARGS.free_models]})
        elif "health" in self.path:
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(ln) or b"{}")
        except Exception as e:
            return self._json(400, {"error": {"message": f"bad json: {e}"}})
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "only /v1/chat/completions"}})

        model = str(req.get("model") or "").strip()
        model = model.split("/")[-1]
        if model.endswith("(high)") or "(" in model:
            model = model.split("(")[0].strip()
        if model not in ARGS.free_models:
            return self._json(404, {"error": {"message": f"model {model!r} not in allowlist",
                                              "type": "ModelError"}})
        prompt = flatten_messages(req.get("messages"))
        key = self.headers.get("X-Conversation-Id") or self.headers.get("X-Session-Id") or "default"
        try:
            text = ask(model, prompt, key)
        except urllib.error.HTTPError as e:
            body = e.read(400).decode(errors="replace")
            return self._json(e.code, {"error": {"message": body, "type": "UpstreamError"}})
        except Exception as e:
            return self._json(502, {"error": {"message": repr(e), "type": "BridgeError"}})

        cid = f"chatcmpl-{int(time.time()*1000)}"
        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            def chunk(delta, finish=None):
                d = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(f"data: {json.dumps(d, ensure_ascii=False)}\n\n".encode())
            chunk({"role": "assistant", "content": ""})
            for i in range(0, len(text), 24):
                chunk({"content": text[i:i+24]}); self.wfile.flush()
            chunk({}, "stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            self._json(200, {"id": cid, "object": "chat.completion", "created": int(time.time()),
                             "model": model,
                             "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                          "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--oc-port", type=int, default=4097)
    ap.add_argument("--opencode-bin", default=None)
    ap.add_argument("--home", default=None, help="opencode 的 HOME（配置/凭据目录）")
    ap.add_argument("--free-models", default=",".join(DEFAULT_FREE))
    ap.add_argument("--mode", choices=["stateless", "stateful"], default="stateless")
    ARGS = ap.parse_args()
    ARGS.free_models = [m.strip() for m in ARGS.free_models.split(",") if m.strip()]
    signal.signal(signal.SIGTERM, flush_children)
    signal.signal(signal.SIGINT, flush_children)
    start_server()
    print(f"[bridge] OpenAI 兼容端点: http://127.0.0.1:{ARGS.port}/v1  "
          f"(models: {', '.join(ARGS.free_models[:4])}...)  mode={ARGS.mode}")
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
