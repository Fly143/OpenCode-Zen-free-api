# zen — OpenCode Zen 免费模型直连工具包

解决的问题：`https://opencode.ai/zen/v1` 的 `*-free` 模型加了「客户端指纹」校验，
第三方客户端直连返回 403 `FreeTierError: OpenCode's free tier can only be used from within OpenCode`。
另外 **rikkahub** 有一个源码级 bug：它对 `host == "opencode.ai"` 的请求硬塞
UUID 格式的 `x-opencode-session`，覆盖用户自定义 Header，而服务端只认 `ses_` 格式 → 必 403。

## 文件

| 文件 | 用途 |
|---|---|
| `zen_free.py` | 最小可用直连示例：`python3 zen_free.py [模型] [提示词]` |
| `zen_relay.py` | 本地反代（核心）。注入合规头/体、剥离脏 session、透传 SSE；**非流式客户端自动把 SSE 聚合成 JSON**（服务端只收 `stream:true`，但 App 部分场景期望纯 JSON）。`python3 zen_relay.py [端口]` 默认 8787 |
| `zen_check.py` | 自检（合并了原 9 个一次性探测脚本）：`python3 zen_check.py [basic\|ablate\|host\|relay]` |
| `README.md` | 本说明 |
| `CHANGELOG.md` | 改动记录（基线前部分为依实测补写） |

## rikkahub 配置（推荐：走 relay）

1. 启动 relay —— **在你自己控制的环境里跑**（本软件的常驻终端/会话都行；
   对话里的执行环境每次调用结束会清空进程树，放那里必死）：
   ```bash
   python3 /workspace/zen/zen_relay.py 8787
   ```
   需常驻可用 `nohup python3 -u zen_relay.py 8787 >> relay.log 2>&1 &`。
   任何有 python3 的设备都行（同手机 Termux、电脑、NAS、云主机），只要 rikkahub 能访问到那个 `IP:端口`。
2. rikkahub 提供商设置：

| 项 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8787/zen/v1` |
| API Key | `public`（服务端不校验） |
| 模型 ID | `mimo-v2.6-flash-free` |
| 自定义 Headers/Body | 不用填，relay 统一注入 |

原理：硬编码只认 `host == "opencode.ai"`，指向 `127.0.0.1` 即绕开；
manifest `usesCleartextTraffic="true"`，App 允许 http。

## 校验条件（2026-09-22 实测，`zen_check.py ablate` 可复验）

| 条件 | 不满足时 |
|---|---|
| `x-opencode-session` = `ses_` + 12位hex + 14位字母数字 | 403 |
| `User-Agent` = `opencode/1.18+`（大小写不限） | 403；1.17 → 426 |
| body `stream: true` | 403 |
| body `tools` 含 bash/glob/grep/read 四件套（缺一即拒） | 403 |
| `Authorization` | 可省略 |
| `x-opencode-request/client/project` | 非必需 |

## 已验证走不通的路（别重复踩）

- `www/api/app.opencode.ai` 等子域 → 404/HTML 假 200
- 尾点域名 `opencode.ai.` → 服务端认，但证书不匹配；rikkahub 无「信任所有证书」开关
- 大小写变体重复 session 头 / 逗号拼接 → 服务端 403

## 已知风险

- 官方在持续收紧检测（linux.do 反馈 2026-09 中旬起多次变更），纯静态头随时可能失效；
  走 relay 的话以后只需改 `zen_relay.py` 一处。
- 长期方案：给 rikkahub 提 PR —— `configureSessionHeaders()` 里 `header()` 改为
  「用户已设同名头则不覆盖」，或 session 值格式化为 `ses_...`。
