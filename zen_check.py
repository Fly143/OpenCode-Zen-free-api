#!/usr/bin/env python3
"""zen_check.py — OpenCode Zen 免费模型（*-free）校验条件自检，零依赖。
合并了原先 9 个一次性探测脚本：裸请求/消融/UA大小写/session格式/子域探测/
重复头/尾点域名/relay 端到端。

用法:
  python3 zen_check.py            # 全部检查（约 25 请求）
  python3 zen_check.py basic      # 只跑最小可用性 + relay
  python3 zen_check.py ablate     # 10 组消融，确认校验条件是否变严
  python3 zen_check.py host       # 子域/尾点域名探测（找可绕过 host 硬编码的别名）
  python3 zen_check.py relay      # 本地 relay 端到端（需 relay 已启动）
"""
import json, sys, socket, uuid, ssl, http.client
import urllib.request, urllib.error

BASE = "https://opencode.ai/zen/v1"
RELAY = "http://127.0.0.1:8787/zen/v1"
MODEL = "mimo-v2.6-flash-free"
GOOD_SES = "ses_0a1b2c3d4e5faB3dE5fG7hI9jK"
UUID_SES = "6b5ab89e-2c1d-406d-837a-3d12e391be4a"

def four_tools():
    return [{"type": "function", "function": {"name": n, "description": n,
            "parameters": {"type": "object", "properties": {p: {"type": "string"}},
                           "required": [p]}}}
            for n, p in (("bash", "cmd"), ("glob", "pattern"),
                         ("grep", "pattern"), ("read", "path"))]

def new_ses():
    return "ses_" + uuid.uuid4().hex[:12] + uuid.uuid4().hex[:14]

def post(url, body, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return -1, repr(e)

def chat_body(stream=True, tools=True):
    b = {"model": MODEL, "messages": [{"role": "user", "content": "只回复：收到"}],
         "stream": stream}
    if tools:
        b["tools"] = four_tools()
    return b

def hdrs(ua="opencode/1.18.13", ses=GOOD_SES, auth=None, extra=False):
    h = {"User-Agent": ua}
    if auth is not None:
        h["Authorization"] = auth
    if ses is not None:
        h["x-opencode-session"] = ses
    if extra:
        h.update({"x-opencode-request": uuid.uuid4().hex,
                  "x-opencode-client": "cli",
                  "x-opencode-project": uuid.uuid4().hex[:24]})
    return h

def line(ok, tag, st, note=""):
    print(f"{'✅' if ok else '❌'} {tag:34s} HTTP {st}  {note}")

def is_ok(st, raw):
    return st == 200 and "FreeTierError" not in raw and raw.strip().startswith(("data:", "{"))

def collect_sse(raw):
    """从 SSE 文本里取出 reasoning/content 拼接结果。"""
    reason, content = [], []
    for l in raw.splitlines():
        l = l.strip()
        if not l.startswith("data:"):
            continue
        p = l[5:].strip()
        if p == "[DONE]":
            break
        try:
            d = json.loads(p)
        except Exception:
            continue
        for c in d.get("choices") or []:
            delta = c.get("delta") or {}
            if delta.get("reasoning_content"):
                reason.append(delta["reasoning_content"])
            if delta.get("content"):
                content.append(delta["content"])
    return "".join(reason), "".join(content)

def check_basic():
    print("== 基础可用性 ==")
    st, raw = post(BASE + "/chat/completions",
                   {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                   {"User-Agent": "python-urllib/3.12"})
    line(st == 403, "裸请求应被 403 拦截", st)
    st, raw = post(BASE + "/chat/completions", chat_body(), hdrs())
    ok = is_ok(st, raw)
    line(ok, "全套指纹直连", st)
    if ok:
        r, c = collect_sse(raw)
        print(f"   思考: {r[:50] or '(无)'}")
        print(f"   回答: {c[:80]}")

def check_ablate():
    print("== 消融（确认校验条件有无变化）==")
    cases = [
        ("基线: UA+ses_+stream+tools", hdrs(),                              chat_body()),
        ("无 x-opencode-session",      hdrs(ses=None),                      chat_body()),
        ("session=UUID(rikkahub格式)", hdrs(ses=UUID_SES),                  chat_body()),
        ("有 Authorization",           hdrs(auth="Bearer public"),          chat_body()),
        ("UA=python",                  hdrs(ua="python-urllib/3.12"),       chat_body()),
        ("UA=opencode/1.17",           hdrs(ua="opencode/1.17.0"),          chat_body()),
        ("UA大写 OpenCode",            hdrs(ua="OpenCode/1.18.13"),         chat_body()),
        ("stream=false",               hdrs(),                              chat_body(stream=False)),
        ("无 tools",                   hdrs(),                              chat_body(tools=False)),
        ("tools只有3个(缺grep)",       hdrs(),                              {**chat_body(), "tools": four_tools()[:3]}),
        ("带 extra 三头",              hdrs(extra=True),                    chat_body()),
    ]
    expect403 = {"无 x-opencode-session", "session=UUID(rikkahub格式)",
                 "UA=python", "stream=false", "无 tools", "tools只有3个(缺grep)"}
    for tag, h, b in cases:
        st, raw = post(BASE + "/chat/completions", b, h)
        if tag in expect403:
            line(st == 403, tag + " (应403)", st)
        elif tag == "UA=opencode/1.17":
            line(st == 426, tag + " (应426 旧版被拒)", st)
        else:
            line(is_ok(st, raw), tag + " (应200)", st,
                 "" if st == 200 else raw[:70])

def check_host():
    print("== 子域/别名探测（找 host != opencode.ai 仍能用的入口）==")
    print("   用途: rikkahub 只对 host==opencode.ai 硬塞 UUID session")
    for sub in ("", "zen.", "api.", "www.", "app.", "cdn.", "go.", "v1."):
        host = sub + "opencode.ai"
        try:
            socket.gethostbyname(host)
        except Exception:
            print(f"·  {host:24s} DNS 无记录")
            continue
        st, raw = post(f"https://{host}/zen/v1/chat/completions",
                       chat_body(), hdrs(), timeout=20)
        # 关键: 状态码 200 不够，body 必须是 SSE 才算真通
        real = is_ok(st, raw)
        note = "" if real else ("假200: " + raw[:40].replace("\n", " ") if st == 200 else raw[:40])
        line(real, host, st, note)
    # 尾点域名（服务端认但证书不匹配 → 需跳过校验，rikkahub 无此开关）
    ctx = ssl.create_default_context()
    try:
        http.client.HTTPSConnection("opencode.ai.", 443, context=ctx, timeout=15)
        line(False, "尾点 opencode.ai.", "-", "证书必不匹配，放弃")
    except Exception as e:
        line(False, "尾点 opencode.ai.", "-", repr(e)[:50])

def check_relay():
    print("== 本地 relay 端到端 ==")
    body = chat_body(tools=False)   # 故意不带 tools，验证 relay 会补
    h = {"Content-Type": "application/json", "Accept": "text/event-stream",
         "Authorization": "Bearer ", "User-Agent": "OpenCode/1.18.13",
         "X-Session-ID": UUID_SES, "x-opencode-session": UUID_SES}  # 模拟 rikkahub 脏头
    st, raw = post(RELAY + "/chat/completions", body, h, timeout=90)
    ok = is_ok(st, raw)
    line(ok, "relay 聊天(脏头+无tools)", st)
    if ok:
        r, c = collect_sse(raw)
        print(f"   回答: {c[:80]}")
    req = urllib.request.Request(RELAY + "/models", headers={"User-Agent": "opencode/1.18.13"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ids = [m["id"] for m in json.loads(resp.read())["data"]]
            free = [i for i in ids if i.endswith("-free")]
            line(True, "relay /models", resp.status,
                 f"{len(free)} 个免费模型: {', '.join(free)}")
    except Exception as e:
        line(False, "relay /models", "-", repr(e)[:70])

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "basic"):
        check_basic()
        check_relay()
    if mode == "ablate" or mode == "all":
        check_ablate()
    if mode == "host" or mode == "all":
        check_host()
    if mode == "relay":
        check_relay()

if __name__ == "__main__":
    main()
