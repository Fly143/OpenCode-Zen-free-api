# Changelog

> 注：本仓库于 2026-09-22 所有功能完成后才 `git init`，
> 此前的演进无 git 历史，本文件依实测记录补写。自基线提交 `73d88fb` 起以 git 为准。

## 2026-09-22（基线前，无 git 记录）

### 探测与确认
- 确认 Zen 免费端点 4 项放行条件（ses_ session / UA≥1.18 / stream:true / tools 四件套），
  消融实验共 10 组；裸请求 403 `FreeTierError` 复现。
- 绕过尝试全部失败（均有实测）：`www/api/app` 等子域假 200、尾点域名证书不匹配、
  大小写重复 session 头/逗号拼接 403。
- 确认本执行环境为 rkkahub per-command proot，`--kill-on-exit` 杀后台进程
  → relay 由用户在其常驻环境启动。

### 文件演进
- **`zen_free.py`**：最小直连示例（SSE 解析 reasoning/content），一步到位。
- **`zen_relay.py`**
  1. 初版：注入 UA / ses_ session / tools 四件套 / stream:true，剥离 App 脏 UUID 头，SSE 透传。
  2. 曾加路径归一（`/v1` → `/zen/v1`）以适配少填前缀的 Base URL
     —— 用户确认是其配置笔误，**已按要求回退**。
  3. 新增非流式聚合：识别客户端 `stream` 意图；非流式时上游强制 SSE 取回，
     `aggregate()` 合并 content/reasoning_content/tool_calls/usage 为
     `chat.completion` JSON 返回（服务端只收 `stream:true`，直接透传会让 App 的
     JSON 解析器在 `data:` 冒号处报错）；同时带 `stream_options.include_usage`。
     4 场景实测全过（流式透传 / stream:false / 无 stream 字段 / 非流式工具调用）。
- **`zen_check.py`**：9 个一次性探测脚本（probe/ablation/static/ua/host/alias/
  sim_rikka/dup/relay_test）合并为单文件多子命令（basic/ablate/host/relay），
  修复 four_tools 括号不匹配的 SyntaxError。
- **`README.md`**：校验条件表、relay 配置、失败绕过记录；
  relay 启动说明改为「用户在自己常驻环境启动」。

## 2026-09-23

### 复查（无代码改动，确认服务端未收紧）
- 全套指纹直连 200、裸请求 403、relay 端到端 200；`ablate` 10 组结果与 09-22 完全一致。
- 免费模型列表仍是 10 个（`/models` 里 endswith `-free` 的 9 个 + 无后缀的 `big-pickle`）。
- 并发 12 路全 200，未见 429 或任何限流响应头（30 路压测被用户中途取消）。

### 修复
- **`zen_check.py`**：`check_ablate()` 里 `post()` 参数顺序颠倒
  （`post(url, h, b)` → `post(url, b, h)`），此前 11 组消融全部
  以 `TypeError: expected string or bytes-like object, got 'list'` 报错。
  `UA=opencode/1.17` 的预期值同时从「应 200」修正为「应 426」。commit `53dd657`。

### 新增
- **`zen_relay.py` session 模式**（用户需求：启动时随机重置 session）：
  - 默认仍是**每请求随机**（原行为，未改动）。
  - `--sticky` / `-s` / `ZEN_SESSION_MODE=sticky`：启动时随机生成一个 `ses_`，进程内复用。
  - `--rotate=N`：隐含 `--sticky`，每 N 秒自动换新，并往 stderr 打轮换日志。
  - 新增本地调试端点 `GET /__session`（**不转发上游**），返回当前模式/session/年龄/轮换次数；
    sticky 启动时也会把当次 session 打到 stdout。
  - 实测（假上游抓真实发出的 `x-opencode-session`）：默认 3 请求→3 个不同、
    sticky 3 请求→1 个相同、`--rotate=2` 中间隔 2.5s→2 个不同且 `rotations=1`，
    全部符合 `^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$`；sticky 下真实上游端到端仍 200。
- `README.md` / `README.en.md` 增加「session 模式」小节（模式表、`--rotate` 建议值、
  调试端点、sticky 的权衡说明）。

## 2026-09-22 基线后
- `73d88fb` git 仓库初始化，基线提交（6 文件，`*.log` 入 .gitignore）。
- 本 CHANGELOG 补写。

## 2026-10-15 复检：旧路线失效，改用真客户端当传输层

### 结论
- Zen 免费额度的客户端校验已升级为**内容级**：把官方客户端真实请求逐字节重放
  （头/体/头顺序，乃至 TLS ClientHello）仍全部 403；只有官方客户端进程本身 200。
  → `zen_relay.py` / `zen_free.py` / `zen_check.py` 所依赖的静态指纹方案**已失效**。

### 新增
- **`oc_bridge.py`**：不模仿客户端，而是起一个真实 `opencode serve` 当传输层，
  把其 HTTP API 翻译成 OpenAI 兼容端点（默认 `:8790`）。
  rikkahub 只需把 Base URL 指到 `http://127.0.0.1:8790/v1`。
  实测通过：`GET /v1/models`、非流式与流式的 `/v1/chat/completions` 均 200。
- **`start.sh` / `start.bat`**：一键启动脚本（Linux/macOS/Termux/WSL、Windows）。
  自动查找/安装 opencode 二进制并启动桥上；`--bg` 可后台常驻。
  幂等：按绝对路径在 PATH / npm 全局目录 / 常见位置查找，找不到才安装，
  找到则把绝对路径传给桥上（避免"npm 装在 PATH 之外 → 每次启动又重装"的坑）。
- **`FINDINGS-2026-10-15.md`**：本次复检的完整记录（分层判定、逐字节重放、
  TLS ClientHello 比对、官方客户端抓包、可行方案验证）。
- `_probe/` 入 `.gitignore`（复检脚本与 opencode 二进制，不入库）。

### 文档
- `README.md` / `README.en.md` 重写：以 `oc_bridge.py` 为推荐方案，
  `zen_relay.py` 等旧工具标注为已失效并保留留档。

## 2026-10-15（后续）

### 文档
- `FINDINGS-2026-10-15.md` 改为中性的《原理与实测记录》：说明为什么这么设计
  以及支撑证据，去掉"核心路线已失效/仓库还剩什么价值"等事后复盘语气。
  （文件名保留，以免破坏既有链接。）

### 仓库整理
- 主分支移除失效的旧方法（`zen_relay.py` / `zen_free.py` / `zen_check.py`），
  移至分支 **`legacy-header-spoof`** 留档；`main` 只保留当前可用方案。

### 新增
- **`opencode.json.example`** + `oc_bridge.py --agent`：用配置里的自定义 agent
  的 `prompt` 字段**替换**（非追加）opencode 默认注入的系统提示。
  实测系统提示 9565 → 1065 字符，且仍能正常出字。空 prompt 会回退默认。
- `oc_bridge.py` 新增 `--agent NAME` 选项。
- **下游 system 提示原样透传**：`split_messages()` 把下游客户端的 `system` 消息
  经 opencode `system` 字段转发（不再压进 user 文本），其余消息仍拼成一段。
  便于把本桥当 dsh / mimo code 等自带系统提示的 coding agent 的后端。
  实测：下游要求"只输出 JSON"→ 返回纯 JSON。
- 精简系统提示改为默认（见下）。
- **精简系统提示改为默认**：`oc_bridge.py` 通过 `OPENCODE_CONFIG_CONTENT` 环境变量
  注入 `bridge` agent（与用户已有 `opencode.json` 合并，不改其文件），默认
  `agent=bridge`，把注入的系统提示从 9565 → ~1080 字符。新增 `--prompt TEXT`
  自定义提示文本、`--full-prompt` 恢复完整提示。实测默认打真实上游正常出字。

## 2026-10-20 复检：方案仍有效；opencode 二进制缺失已修复，免费清单更新

### 现状核实（同一出口，无任何伪装）
- `GET https://opencode.ai/zen/v1/models`（带 opencode UA）→ **200，85 个模型**，
  免费档 9 个。**Zen 仍然只认真客户端**，旧结论（静态模仿一律 403）未变。
- `oc_bridge.py` 全链路复测通过：
  `POST /v1/chat/completions` → 200，`mimo-v2.6-flash-free` 8.9s 正常出字。
- 首次冷启动首字较慢（14–20s，含实例 bootstrap），之后 1–9s。

### 修复：opencode 二进制丢失（本机 rootfs 侧，非方案问题）
- 现象：`/opt/.../opencode-ai/bin/opencode.exe` 与
  `.../node_modules/opencode-linux-arm64/bin/opencode` 都是**悬空软链**
  （指向不存在的 `.l2s.opencode0001`），`npm i -g opencode-ai@1.19.0` 重装后
  postinstall 仍只生成软链 → `FileNotFoundError`。
- 处理：直接下平台包 tarball 手工解包（60MB tgz → 185MB 二进制）
  ```sh
  npm pack opencode-linux-arm64@1.19.0
  D=/opt/node-v22.14.0-linux-arm64/lib/node_modules/opencode-ai/node_modules/opencode-linux-arm64
  rm -rf "$D/bin" && tar xzf opencode-linux-arm64-1.19.0.tgz --strip-components=1 -C "$D"
  chmod 755 "$D/bin/opencode"
  rm -f .../opencode-ai/bin/opencode.exe && ln -s ../node_modules/opencode-linux-arm64/bin/opencode .../opencode-ai/bin/opencode.exe
  ln -sf .../opencode-ai/bin/opencode.exe /usr/local/bin/opencode
  ```
  → `opencode --version` = 1.19.0，`start.sh` 可用。

### 免费模型清单（2026-10-20 实测，逐个发消息验证）
- 可用：`deepseek-v4.1-flash-free`(2.4s)、`minimax-m3.1-flash-free`(1.6s)、
  `nemotron-3.5-lightning-free`(3.8s)、`mimo-v2.6-flash-free`、
  `glm-5.3-flash-free`(9.5s)、`longcat-2.5-preview-free`(6.1s)、
  `nemotron-3.5-super-vl-free`(4.2s)。
- 半残：`beam-free` 能连、HTTP 200，但 content 为空（疑似只出推理/空响应）。
- 已失效：`step-5-preview-free`、`space-bunny-free`、`jev-1.13-free` → HTTP 500；
  `big-pickle` 已不在 `/v1/models`。
- `DEFAULT_FREE` 已按上面顺序更新（`/v1/models` 输出随之更新）。
