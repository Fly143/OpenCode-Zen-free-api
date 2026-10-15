# zen — OpenCode Zen 免费模型工具包

[English](./README.en.md) | 简体中文

## 2026-10-15 重要更新：旧的「伪造头」路线已失效

`https://opencode.ai/zen/v1` 的 `*-free` 模型现在会对**请求内容之外的客户端特征**做校验。
经实测（详见 [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md)），
把官方客户端的真实请求**逐字节重放**（头、体、头顺序，甚至 TLS ClientHello 都对齐）**依然 403**：

```
403 FreeTierError: OpenCode's free tier can only be used from within OpenCode
```

同一台机器、同一个出口 IP 上，只有**官方客户端进程本身**能拿到 200。
所以本仓库的旧路线 —— `zen_relay.py` 注入几个请求头 —— **已不再有效**，请勿再依赖。

## 推荐方案：`oc_bridge.py`（不模仿，直接用真客户端）

思路：既然拦的是客户端本身，就**让官方客户端自己去发请求**。
opencode 自带无头服务器 `opencode serve`，它跑在真实客户端进程里，能过闸。
`oc_bridge.py` 就是把它的 HTTP API 翻译成 OpenAI 兼容端点的桥：

```
rikkahub / 任意 OpenAI 客户端
      │  POST /v1/chat/completions
      ▼
oc_bridge.py (:8790)                       ← 本仓库，零依赖
      │  POST /session ，POST /session/{id}/message
      ▼
opencode serve (:4097，真实客户端二进制)
      │  POST /inference/v1/chat/completions
      ▼
opencode.ai Zen 网关  ✅
```

### 用法（一键启动）

```bash
# Linux / macOS / Termux / WSL
./start.sh                    # 自动找/装 opencode，前台启动
./start.sh --bg               # 后台常驻（日志 oc_bridge.log）
./start.sh --port 9000 --mode stateful
```

双击 `start.bat` 即可在 Windows 上启动（同样自动找/装 opencode）。

### 用法（手动）

```bash
# 运行处需有真实的 opencode 二进制：
npm i -g opencode-ai          # 或 brew / pacman / docker，见 opencode 官方文档
# 手机可用 Termux 装 node 后同样 npm i -g opencode-ai

python3 oc_bridge.py --port 8790 --oc-port 4097
# 常用参数：
#   --opencode-bin PATH   指定 opencode 二进制路径（默认从 PATH 找）
#   --home DIR            指定 opencode 的 HOME（配置/凭据目录）
#   --mode stateless|stateful   默认 stateless（每请求新会话）；stateful 按会话复用
#   --free-models a,b,c   覆盖允许的模型 id 列表
```

客户端（rikkahub）提供商设置：

| 项 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API Key | 随便填（不校验） |
| 模型 ID | `mimo-v2.6-flash-free` |
| 自定义 Headers/Body | 不用填 |

`oc_bridge.py` 会自己拉起（或复用已在跑的）`opencode serve`。
rikkahub 走本地 http 即可（App manifest `usesCleartextTraffic="true"`）。

### 已验证

沙箱实测（同一出口 IP，所有 Python/Node/Bun 重放都 403 的地方）：

| 测试 | 结果 |
|---|---|
| `GET /v1/models` | ✅ 200 |
| `POST /v1/chat/completions`（非流式） | ✅ 200，正常出字 |
| `POST /v1/chat/completions`（`stream:true`） | ✅ 标准 SSE 分片 + `[DONE]` |
| `step-5-preview-free` 等其它免费模型 | ✅ 200 |

### 注意

- 需要在运行处装 opencode 二进制（比纯 Python relay 重）。
- 请求会带上 opencode 自己的 system prompt / 工具定义，上下文比裸调用大。
- 免费额度现按**地区**切分：香港出口下 `cat-jam-free`、`muse-spark-1.2/1.3` 返回
  `403 RegionError`。
- 这是"用本尊"而非"伪装"，仍属灰色用法；量大可能被服务端针对，要紧场景建议走付费 key。

## 文件

| 文件 | 用途 |
|---|---|
| `oc_bridge.py` | **推荐**。把真实 opencode 客户端封装成 OpenAI 兼容端点（`:8790`） |
| `start.sh` / `start.bat` | 一键启动脚本（Linux/macOS/Termux/WSL、Windows）：自动找/装 opencode 并启动桥上 |
| `zen_free.py` | 最小直连示例（**已失效**，留作参考）：`python3 zen_free.py [模型] [提示词]` |
| `zen_relay.py` | 本地反代，注入合规头/体（**已失效**，留档；换任意 OpenAI 兼容上游仍可复用其 SSE→JSON 聚合骨架） |
| `zen_check.py` | 自检/消融脚本（**已失效**，反映 2026-09 的旧校验条件） |
| `FINDINGS-2026-10-15.md` | 2026-10-15 复检全记录（证据、抓包、结论、`oc_bridge` 方案验证） |
| `README.md` / `README.en.md` | 中文 / 英文说明 |
| `CHANGELOG.md` | 改动记录 |

## 历史（已失效）

2026-09 时，Zen 免费端点靠一组可复现的请求头/体条件放行
（`ses_` 会话格式、`UA: opencode/≥1.18`、`stream:true`、`tools` 含核心工具名），
`zen_relay.py` 即据此注入头并透传，一度可用。
2026-09-17 起服务端逐步收紧，至 2026-10-15 已升级为内容级校验，静态头彻底失效。
细节与逐字节重放的证据见 [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md)。

## 仓库

https://github.com/Fly143/OpenCode-Zen-free-api
