#!/usr/bin/env python3
"""zen_relay.py — 本地反代，给 OpenCode Zen 免费模型注入通过校验所需的头/体。
用法: python3 zen_relay.py [端口]        默认 8787
rikkahub 里 Base URL 填: http://127.0.0.1:8787/zen/v1
原理: rikkahub 只对 host==opencode.ai 硬塞 UUID session；指向 127.0.0.1 即绕开，
      本中转统一补上 UA / ses_ session / tools / stream=true，并透传 SSE。
"""
import json, sys, uuid, threading, http.server, socketserver, urllib.request, urllib.error

UPSTREAM = "https://opencode.ai"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787

def new_session():
    return "ses_" + uuid.uuid4().hex[:12] + uuid.uuid4().hex[:14]

def new_request_id():
    return "msg_" + uuid.uuid4().hex[:12] + uuid.uuid4().hex[:14].upper()

FOUR = [{"type": "function", "function": {"name": n, "description": n,
        "parameters": {"type": "object", "properties": {p: {"type": "string"}},
                       "required": [p]}}}
        for n, p in (("bash", "cmd"), ("glob", "pattern"),
                     ("grep", "pattern"), ("read", "path"))]

def aggregate(raw: bytes) -> bytes:
    """把上游 SSE 聚合成一个 chat.completion JSON（给非流式客户端）。"""
    text = raw.decode("utf-8", errors="replace")
    out = {"id": None, "object": "chat.completion", "created": None,
           "model": None, "choices": [{"index": 0, "finish_reason": None,
                                       "message": {"role": "assistant", "content": ""}}]}
    content, reasoning, tools = [], [], {}
    finish = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if p == "[DONE]":
            break
        try:
            d = json.loads(p)
        except Exception:
            continue
        for k in ("id", "created", "model"):
            if d.get(k) is not None:
                out[k] = d[k]
        if d.get("usage"):
            out["usage"] = d["usage"]
        for c in d.get("choices") or []:
            if c.get("finish_reason"):
                finish = c["finish_reason"]
            delta = c.get("delta") or {}
            if delta.get("content"):
                content.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])
            for tc in delta.get("tool_calls") or []:
                i = tc.get("index") or 0
                t = tools.setdefault(i, {"id": "", "type": "function",
                                         "function": {"name": "", "arguments": ""}})
                if tc.get("id"):
                    t["id"] = tc["id"]
                f = tc.get("function") or {}
                if f.get("name"):
                    t["function"]["name"] += f["name"]
                if f.get("arguments"):
                    t["function"]["arguments"] += f["arguments"]
    msg = out["choices"][0]["message"]
    msg["content"] = "".join(content)
    if reasoning:
        msg["reasoning_content"] = "".join(reasoning)
    if tools:
        msg["tool_calls"] = [tools[i] for i in sorted(tools)]
        msg["content"] = msg["content"] or None
    out["choices"][0]["finish_reason"] = finish or ("tool_calls" if tools else "stop")
    if out["id"] is None:
        out.pop("id"); out.pop("created"); out.pop("model")
    return json.dumps(out, ensure_ascii=False).encode()

class Relay(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "zen-relay"

    def log_message(self, fmt, *args):
        sys.stderr.write("[relay] " + fmt % args + "\n")

    def do_GET(self):
        self._forward(None)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._forward(self.rfile.read(n) if n else b"")

    def _forward(self, raw):
        # 服务端只收 stream:true（false 直接 403），但客户端可能期望非流式 JSON。
        # 记录客户端意图：非流式时上游仍走 SSE，取回后聚合成 chat.completion JSON 再回给客户端。
        want_stream = True
        body = raw
        if raw:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    want_stream = bool(obj.get("stream", False))
                    obj["stream"] = True          # 服务端强制要求
                    if not want_stream:
                        obj["stream_options"] = {"include_usage": True}
                    tools = obj.get("tools")
                    if not isinstance(tools, list):
                        tools = []
                    names = {t.get("function", {}).get("name")
                             for t in tools if isinstance(t, dict)}
                    for t in FOUR:                # 四件套必须存在，缺一即 403
                        if t["function"]["name"] not in names:
                            tools.append(t)
                    obj["tools"] = tools
                    body = json.dumps(obj, ensure_ascii=False).encode()
            except Exception:
                pass

        headers = {
            "User-Agent": "opencode/1.18.13",
            "Authorization": "Bearer public",
            "Accept": self.headers.get("Accept", "*/*"),
            "Content-Type": "application/json",
            "x-opencode-session": new_session(),
            "x-opencode-request": new_request_id(),
            "x-opencode-client": "cli",
            "x-opencode-project": "global",
        }
        req = urllib.request.Request(UPSTREAM + self.path, data=body,
                                     headers=headers, method=self.command)
        try:
            up = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            up = e
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            self.close_connection = True
            return

        ctype = up.headers.get("Content-Type", "application/octet-stream")
        # 非流式客户端 + 上游 SSE 200 → 聚合成 JSON 再返回
        if not want_stream and up.status == 200 and "event-stream" in ctype:
            try:
                payload = aggregate(up.read())
            except Exception:
                payload = None
            if payload is not None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)
                self.close_connection = True
                return

        self.send_response(up.status)
        self.send_header("Content-Type", ctype)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                chunk = up.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception:
            pass

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    print(f"zen-relay 监听 http://127.0.0.1:{PORT}/zen/v1  ->  {UPSTREAM}/zen/v1")
    Server(("127.0.0.1", PORT), Relay).serve_forever()
