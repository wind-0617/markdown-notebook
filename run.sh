#!/usr/bin/env bash
# run.sh —— Linux/macOS 一键启动（v0.3：前后端分离 + Vite 构建）
# 自动完成：定位 Python → 建虚拟环境（失败回退 backend/.deps）→ 装依赖
#           → 构建前端（npm run build → frontend/dist）
#           → 启动 Flask → 轮询就绪 → 打开浏览器 → Ctrl+C 终止
#
# 用法：chmod +x run.sh && ./run.sh
#       REINSTALL=1 ./run.sh    强制重装依赖
#       NO_BROWSER=1 ./run.sh   不自动开浏览器
#       ./run.sh --stop         停止服务
set -u
cd "$(dirname "$0")"
echo "📁 当前目录: $(pwd)"

PORT="${PORT:-5000}"
BIND_HOST="${HOST:-127.0.0.1}"
URL="http://${BIND_HOST}:${PORT}"

health_ok() { curl -sf --max-time 2 "${URL}/api/health" >/dev/null 2>&1; }

open_browser() {
  # shellcheck disable=SC2143
  if [ "$(uname -s)" = "Darwin" ]; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  else echo "请手动打开浏览器访问 ${URL}"; fi
}

# ---------- 停止模式 ----------
if [ "${1:-}" = "--stop" ]; then
  pkill -f "python.*app\.py" && echo "🛑 已停止服务" || echo "未发现运行中的服务"
  exit 0
fi

# ---------- 定位 Python ----------
PY=""
for c in python3 python; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done
if [ -z "$PY" ]; then echo "❌ 未找到 Python（需 3.10+）"; exit 1; fi
echo "🐍 Python: $($PY -V 2>&1)"

# ---------- 已在运行？直接体验 ----------
if health_ok; then
  echo "♻️  服务已在运行：${URL}"
  [ -z "${NO_BROWSER:-}" ] && open_browser
  exit 0
fi

# ---------- 虚拟环境（失败回退 backend/.deps） ----------
USE_VENV=1
if [ ! -x "venv/bin/python" ]; then
  echo "🔧 创建虚拟环境 venv/ ..."
  "$PY" -m venv venv 2>/dev/null || true
fi
if [ ! -x "venv/bin/python" ]; then
  rm -rf venv
  USE_VENV=0
  echo "⚠️  venv 不可用，回退方案：系统 Python + backend/.deps（app.py 自动识别）"
fi

# ---------- 安装依赖（marker 防重复） ----------
if [ "$USE_VENV" = "1" ]; then
  PYRUN="venv/bin/python"
  if [ ! -f "venv/.deps-ok" ] || [ "${REINSTALL:-0}" = "1" ]; then
    echo "📦 安装依赖到 venv ..."
    "$PYRUN" -m pip install --disable-pip-version-check -q -r backend/requirements.txt \
      && touch venv/.deps-ok
  else
    echo "📦 依赖已就绪（REINSTALL=1 ./run.sh 可强制重装）"
  fi
else
  PYRUN="$PY"
  if [ ! -d "backend/.deps" ] || [ "${REINSTALL:-0}" = "1" ]; then
    echo "📦 安装依赖到 backend/.deps ..."
    "$PYRUN" -m pip install --disable-pip-version-check -q --no-cache-dir \
      --target backend/.deps -r backend/requirements.txt
  else
    echo "📦 backend/.deps 已存在，跳过安装"
  fi
fi

# ---------- 前端构建（Vite → frontend/dist） ----------
if [ ! -f "frontend/dist/index.html" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "🔨 首次构建前端（npm install + vite build，约 1~2 分钟）..."
    ( cd frontend && [ -d node_modules ] || npm install --no-audit --no-fund )
    ( cd frontend && npm run build )
  else
    echo "⚠️ 未检测到 npm（Node.js），跳过前端构建——页面将提示未构建，API 仍可用。"
    echo "   安装 Node 18+ 后重跑本脚本；或手动：cd frontend && npm install && npm run build"
  fi
else
  echo "🔨 前端产物已存在（frontend/dist），跳过构建"
fi

# ---------- 启动后端（后台） ----------
export FLASK_DEBUG="${FLASK_DEBUG:-0}" HOST="$BIND_HOST" PORT="$PORT"
echo "🚀 启动后端服务（${URL}）..."
( cd backend && exec "$PYRUN" app.py ) &
APP_PID=$!
trap 'kill "$APP_PID" 2>/dev/null' EXIT INT TERM

# ---------- 轮询就绪（最多 15s）→ 开浏览器 ----------
if command -v curl >/dev/null 2>&1; then
  for _ in $(seq 1 30); do
    health_ok && break
    kill -0 "$APP_PID" 2>/dev/null || break
    sleep 0.5
  done
else
  sleep 2   # 无 curl 时退回固定等待
fi

if health_ok; then
  echo "✅ 服务就绪：${URL}"
  [ -z "${NO_BROWSER:-}" ] && open_browser
elif ! kill -0 "$APP_PID" 2>/dev/null; then
  echo "❌ 服务启动失败（进程已退出）。端口可能被占用：lsof -i :${PORT}"
  exit 1
else
  echo "⏳ 就绪探测超时，请稍后手动访问 ${URL}"
fi

# ---------- 挂起等待 Ctrl+C ----------
echo "✔ 完成，按 Ctrl+C 终止服务。"
wait "$APP_PID"
