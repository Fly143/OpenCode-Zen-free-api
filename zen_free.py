#!/usr/bin/env python3
"""OpenCode Zen 免费模型直连示例（绕过客户端校验），零依赖，python3 即可跑。
用法: python3 zen_free.py [模型名] [提示词]
"""
import json, sys, uuid, urllib.request

BASE = "https://opencode.ai/zen/v1"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "mimo-v2.6-flash-free"
PROMPT = sys.argv[2] if len(sys.argv) > 2 else "用一句话介绍你自己"

TOOLS = [{"type": "function", "function": {"name": n, "description": n,
    "parameters": {"type": "object", "properties": {"p": {"type": "string"}}, "required": ["p"]}}}
    for n in ("bash", "glob", "grep", "read")]

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "opencode/1.18.13",                       # 必须 >=1.18
    "x-opencode-session": "ses_" + uuid.uuid4().hex[:12] + uuid.uuid4().hex[:14],  # 必须 ses_+26位
    # Authorization 可省略；带上 Bearer public 也行
}

BODY = {
    "model": MODEL,
    "messages": [{"role": "user", "content": PROMPT}],
    "stream": True,          # 必须 true，false 会被 403
    "tools": TOOLS,          # 必须含 bash/glob/grep/read 四个
}

req = urllib.request.Request(BASE + "/chat/completions",
                             data=json.dumps(BODY).encode(),
                             headers=HEADERS, method="POST")

reasoning, content = [], []
with urllib.request.urlopen(req, timeout=120) as r:
    for line in r:
        line = line.decode(errors="replace").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            d = json.loads(payload)
        except Exception:
            continue
        for ch in d.get("choices") or []:
            delta = ch.get("delta") or {}
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])
            if delta.get("content"):
                content.append(delta["content"])

if reasoning:
    print("[思考]", "".join(reasoning))
print("[回答]", "".join(content))
