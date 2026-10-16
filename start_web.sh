#!/usr/bin/env bash
# DouyinLiveRecorder 可视化控制台启动脚本（macOS / Linux）
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python3" ]; then
  PY=".venv/bin/python3"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x "venv/bin/python3" ]; then
  PY="venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "[错误] 没有找到 Python，请先安装 Python 3.10 或更高版本"
  exit 1
fi

echo "使用的解释器: $PY"

if ! "$PY" -c "import requests, loguru, httpx, execjs" >/dev/null 2>&1; then
  echo "[提示] 缺少运行依赖，正在安装 requirements.txt ..."
  "$PY" -m pip install -r requirements.txt
fi

exec "$PY" web/server.py --open "$@"
