# zen — 把 OpenCode Zen 免费模型变成 OpenAI 兼容端点

[English](./README.en.md) | 简体中文

`oc_bridge.py` 用**官方 opencode 客户端**（`opencode serve`）当传输层，
把它包成一个 OpenAI 兼容端点——任何客户端（rikkahub、dsh、mimo code……）
填个 Base URL 就能用 Zen 的 `*-free` 模型。

> Zen 免费额度会对客户端本身做校验，第三方直连返回
> `403 FreeTierError: OpenCode's free tier can only be used from within OpenCode`。
> 本工具**不模仿**客户端，而是起一个真实的 opencode 进程去发请求，所以能过闸。
> 原理、抓包与实测见 [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md)。

```
你的客户端（rikkahub / dsh / mimo code / …）
      │  POST /v1/chat/completions
      ▼
oc_bridge.py (:8790)                       ← 本仓库，零依赖
      │  POST /session ，POST /session/{id}/message
      ▼
opencode serve (:4097，官方客户端二进制)
      │  POST /inference/v1/chat/completions
      ▼
opencode.ai Zen 网关  ✅
```

## 快速开始

```bash
# 一键启动（Linux / macOS / Termux / WSL）
./start.sh                    # 自动找/装 opencode，前台启动
./start.sh --bg               # 后台常驻（日志 oc_bridge.log）
./start.sh --port 9000        # 换端口
```

Windows 上双击 `start.bat` 即可。

> 启动脚本**幂等**：按绝对路径在 `PATH` / npm 全局目录 / 常见位置找 `opencode`，
> 只有真找不到才安装（一般只在首次装一次），找到就直接用，不依赖 `PATH`。

客户端设置：

| 项 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API Key | 随便填（不校验） |
| 模型 ID | `mimo-v2.6-flash-free` |
| 自定义 Headers/Body | 不用填 |

## 系统提示

opencode 默认会附带自己的一大段 agent 系统提示，**本工具默认已替换成精简版**：

| 想要的效果 | 启动方式 |
|---|---|
| **默认**：精简系统提示（≈1KB） | `./start.sh` |
| 自定义精简提示文本 | `./start.sh --prompt "You are a terse assistant."` |
| 恢复 opencode 默认完整提示（≈9.5KB） | `./start.sh --full-prompt` |

（实现方式：`oc_bridge.py` 用环境变量 `OPENCODE_CONFIG_CONTENT` 注入一个精简
`bridge` agent，与你自己已有的 `opencode.json` **合并**，不改动你的文件。）

**当其它 coding agent 的后端时**：下游客户端自带的 `system` 消息会**原样透传**
（走 opencode 的 `system` 字段，不会塞进 user 文本），它们自己的系统提示照常生效。
实测：下游要求"只输出 JSON"，返回即为纯 JSON。

## 手动启动 / 参数

```bash
python3 oc_bridge.py --port 8790 --oc-port 4097
#   --opencode-bin PATH   指定 opencode 二进制路径（默认从 PATH 找）
#   --home DIR            指定 opencode 的 HOME（配置/凭据目录）
#   --mode stateless|stateful   默认 stateless（每请求新会话）；stateful 按会话复用
#   --free-models a,b,c   覆盖允许的模型 id 列表
#   --prompt TEXT         精简系统提示文本（默认 "You are a helpful assistant."）
#   --full-prompt         用 opencode 默认的完整系统提示
#   --agent NAME          指定 opencode agent（默认 bridge，即自动注入的精简 agent）
```

`oc_bridge.py` 会自己拉起（或复用已在跑的）`opencode serve`。

## 已验证

| 测试 | 结果 |
|---|---|
| `GET /v1/models` | ✅ 200 |
| `POST /v1/chat/completions`（非流式） | ✅ 200，正常出字 |
| `POST /v1/chat/completions`（`stream:true`） | ✅ 标准 SSE 分片 + `[DONE]` |
| `step-5-preview-free` 等其它免费模型 | ✅ 200 |

## 注意

- 运行处需要 opencode 二进制（手机可用 Termux 装 node 后 `npm i -g opencode-ai`）。
- 请求仍会带上 opencode 的工具定义（约 23KB）——这是**固有开销**，闸门与客户端行为
  都依赖它，配置去不掉。
- 免费额度按**地区**切分：香港出口下 `cat-jam-free`、`muse-spark-1.2/1.3` 返回
  `403 RegionError`。
- 这是"用本尊"而非"伪装"，仍属灰色用法；量大可能被服务端针对，要紧场景建议走付费 key。

## 文件

| 文件 | 用途 |
|---|---|
| `oc_bridge.py` | 核心。把真实 opencode 客户端封装成 OpenAI 兼容端点（`:8790`） |
| `start.sh` / `start.bat` | 一键启动脚本（Linux/macOS/Termux/WSL、Windows） |
| `opencode.json.example` | 可选配置示例（想手动管理 `bridge` agent 时参考） |
| `FINDINGS-2026-10-15.md` | 设计原理与实测记录 |
| `CHANGELOG.md` | 改动记录 |

## 相关

- 早期"伪造请求头"方案（已失效）留档在分支 **`legacy-header-spoof`**：
  `git checkout legacy-header-spoof`。
- 仓库：https://github.com/Fly143/OpenCode-Zen-free-api
