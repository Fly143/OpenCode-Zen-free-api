#!/usr/bin/env sh
# start.sh — oc_bridge 一键启动（Linux / macOS / Termux / WSL）
#
#   ./start.sh                              前台启动（默认端口 8790）
#   ./start.sh --port 9000 --mode stateful  透传参数给 oc_bridge.py
#   ./start.sh --bg                         后台常驻（日志 oc_bridge.log）
#   OPENCODE_BIN=/path/to/opencode ./start.sh
#
# 幂等：先用「绝对路径」找 opencode（PATH、npm 全局、常见目录），
#       找不到才安装；找到就用绝对路径传给桥上，不再依赖 PATH。
#       所以正常情况下——只在第一次装，之后每次直接启动。
set -e

DIR=$(cd "$(dirname "$0")" && pwd)

# --- 0. 解析 --bg，并记录用户是否自己指定了 --opencode-bin ---
BG=0
USER_SPECIFIED_BIN=0
for a in "$@"; do
  case "$a" in
    --bg) BG=1 ;;
    --opencode-bin|--opencode-bin=*) USER_SPECIFIED_BIN=1 ;;
  esac
done
if [ "$BG" = "1" ]; then
  # 从参数里去掉 --bg
  n=$#
  i=0
  while [ $i -lt $n ]; do
    if [ "$1" = "--bg" ]; then shift; else set -- "$@" "$1"; shift; fi
    i=$((i + 1))
  done
fi

# --- 1. python ---
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[start] 找不到 python3。Termux: pkg install python ；Debian/Ubuntu: apt install python3"
  exit 1
fi

# --- 2. 找 opencode（绝对路径，幂等）---
find_opencode() {
  # 2.1 环境变量显式指定
  if [ -n "${OPENCODE_BIN:-}" ] && [ -x "$OPENCODE_BIN" ]; then printf '%s\n' "$OPENCODE_BIN"; return 0; fi
  # 2.2 PATH
  p=$(command -v opencode 2>/dev/null || true)
  if [ -n "$p" ] && [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
  # 2.3 npm 全局目录（npm -g 装完通常不进 PATH，这里是关键）
  if command -v npm >/dev/null 2>&1; then
    np=$(npm prefix -g 2>/dev/null || true)
    [ -n "$np" ] || np=$(npm root -g 2>/dev/null | sed 's#/lib/node_modules$##' || true)
    for c in "$np/bin/opencode" "$np/opencode" "$np/opencode.exe" \
             "$np/lib/node_modules/opencode-ai/bin/opencode" \
             "$np/node_modules/opencode-ai/bin/opencode"; do
      [ -n "$np" ] && [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
    done
  fi
  # 2.4 常见安装位置
  for c in "$HOME/.local/bin/opencode" "$HOME/.opencode/bin/opencode" \
           "/usr/local/bin/opencode" "${PREFIX:-/nonexistent}/bin/opencode"; do
    [ -n "$c" ] && [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

OC_BIN=""
if [ "$USER_SPECIFIED_BIN" = "0" ]; then
  OC_BIN=$(find_opencode || true)
fi

# --- 3. 真找不到才安装 ---
if [ "$USER_SPECIFIED_BIN" = "0" ] && [ -z "$OC_BIN" ]; then
  echo "[start] 未找到 opencode，尝试安装 opencode-ai ..."
  if command -v npm >/dev/null 2>&1; then
    npm i -g opencode-ai || echo "[start] npm 安装失败，请手动安装 opencode：https://opencode.ai"
    OC_BIN=$(find_opencode || true)
    [ -n "$OC_BIN" ] && echo "[start] 已安装：$OC_BIN"
  else
    echo "[start] 也没有 npm。请先装 node/npm，或手动安装 opencode（Termux: pkg install nodejs && npm i -g opencode-ai）"
  fi
fi

# --- 4. 把绝对路径前置传给桥上（用户自己指定则不代劳）---
if [ "$USER_SPECIFIED_BIN" = "0" ] && [ -n "$OC_BIN" ]; then
  set -- --opencode-bin "$OC_BIN" "$@"
fi

# --- 5. 启动 ---
cd "$DIR"
if [ "$BG" = "1" ]; then
  LOG="$DIR/oc_bridge.log"
  echo "[start] 后台启动，日志 -> $LOG"
  nohup "$PY" -u "$DIR/oc_bridge.py" "$@" >>"$LOG" 2>&1 &
  echo "[start] pid $!  （停止：kill $!）"
else
  exec "$PY" -u "$DIR/oc_bridge.py" "$@"
fi
