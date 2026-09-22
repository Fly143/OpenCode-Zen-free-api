# Changelog

> 注：本仓库于 2026-09-22 所有功能完成后才 `git init`，
> 此前的演进无 git 历史，本文件依实测记录补写。自基线提交 `73d88fb` 起以 git 为准。

## 2026-09-22（基线前，无 git 记录）

### 探测与确认
- 确认 Zen 免费端点 4 项放行条件（ses_ session / UA≥1.18 / stream:true / tools 四件套），
  消融实验共 10 组；裸请求 403 `FreeTierError` 复现。
- 读 rikkahub 源码定位根因：`Request.kt configureSessionHeaders()` 在自定义 headers
  **之后**用 `header()` 覆盖式写 `x-opencode-session`，且 `host=="opencode.ai"` 时
  硬塞 conversationId UUID（非法格式）→ 必 403；UA 自定义可生效。
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
- **`rikkahub-fix-session.patch`**：由改好的 `Request.kt` 经 `git diff` 生成——
  用户已设同名头则不覆盖，否则 UUID 格式化为 `ses_` + 26 位（已过服务端正则验证）。
- **`README.md`**：校验条件表、relay 配置、失败绕过记录、补丁 fork + Actions 出包步骤；
  relay 启动说明改为「用户在自己常驻环境启动」。

## 2026-09-22 基线后
- `73d88fb` git 仓库初始化，基线提交（6 文件，`*.log` 入 .gitignore）。
- 本 CHANGELOG 补写。
