#!/usr/bin/env sh
# start.sh — oc_bridge 一键启动（Linux / macOS / Termux / WSL）
#
#   ./start.sh                              前台启动（默认端口 8790）
#   ./start.sh --port 9000 --mode stateful  透传参数给 oc_bridge.py
#   ./start.sh --bg                         后台常驻（日志 oc_bridge.log）
#   BRIDGE_PORT=9000 ./start.sh             也可用环境变量
#
# 它会自动：找 python3 → 找/装 opencode 二进制 → 启动 oc_bridge.py
set -e

DIR=$(cd "$(dirname "$0")" && pwd)

# --- 1. python ---
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[start] 找不到 python3。Termux: pkg install python ；Debian/Ubuntu: apt install python3"
  exit 1
fi

# --- 2. opencode 二进制（没有就尝试用 npm 装）---
HAVE_BIN_ARG=0
for a in "$@"; do
  case "$a" in --opencode-bin|--opencode-bin=*) HAVE_BIN_ARG=1 ;; esac
done
if [ "$HAVE_BIN_ARG" = "0" ] && ! command -v opencode >/dev/null 2>&1 && [ ! -x "${OPENCODE_BIN:-}" ]; then
  echo "[start] 未找到 opencode，尝试安装 opencode-ai ..."
  if command -v npm >/dev/null 2>&1; then
    npm i -g opencode-ai || echo "[start] npm 安装失败，请手动安装 opencode：https://opencode.ai"
    NPM_BIN="$(npm prefix -g 2>/dev/null)/bin"
    [ -d "$NPM_BIN" ] && PATH="$NPM_BIN:$PATH"
  else
    echo "[start] 也没有 npm。请先装 node/npm，或手动安装 opencode（Termux: pkg install nodejs && npm i -g opencode-ai）"
  fi
fi
export PATH

# --- 3. 启动 ---
BG=0
if [ "$1" = "--bg" ]; then BG=1; shift; fi

cd "$DIR"
if [ "$BG" = "1" ]; then
  LOG="$DIR/oc_bridge.log"
  echo "[start] 后台启动，日志 -> $LOG"
  nohup "$PY" -u "$DIR/oc_bridge.py" "$@" >>"$LOG" 2>&1 &
  echo "[start] pid $!  （停止：kill $!）"
else
  exec "$PY" -u "$DIR/oc_bridge.py" "$@"
fi
