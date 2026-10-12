#!/bin/zsh
# 启动本地阅读服务
#
# 用法：
#   ./start-reader.sh                     # 微软课程，默认 http://127.0.0.1:8777/
#   ./start-reader.sh hello               # Hello-Agents，默认 http://127.0.0.1:8778/
#   ./start-reader.sh hello 9000          # 指定端口
#   ./start-reader.sh hello 9000 noopen   # 不自动打开浏览器
#
# 两个工程可以同时开，端口不冲突。

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY=/Users/yes/.workbuddy/binaries/python/envs/default/bin/python
VENV=/Users/yes/.workbuddy/binaries/python/envs/default
BASE=/Volumes/DATA/agentLearn

PRESET=agents
if [[ -n "$1" && "$1" != <-> ]]; then
  PRESET="$1"; shift
fi

case "$PRESET" in
  agents|ai-agents-for-beginners) PRESET=agents; DEFPORT=8777 ;;
  hello|hello-agents)            PRESET=hello;  DEFPORT=8778 ;;
  *) echo "未知工程：$PRESET（可选 agents / hello）"; exit 1 ;;
esac

PORT="${1:-$DEFPORT}"
OPEN="${2:-open}"

if [[ ! -x "$PY" ]]; then
  echo "隔离环境不存在，正在创建…"
  /Users/yes/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q markdown pygments
fi

if [[ "$PRESET" == "agents" ]]; then ROOT="$BASE/ai-agents-for-beginners"; else ROOT="$BASE/hello-agents"; fi
if [[ ! -d "$ROOT" ]]; then
  echo "内容目录不存在：$ROOT"
  echo "请先运行：python3 $DIR/../fetch-repos.py"
  exit 1
fi

while lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  echo "端口 $PORT 已被占用，改用 $((PORT + 1))"
  PORT=$((PORT + 1))
done

URL="http://127.0.0.1:$PORT/"
echo "阅读服务启动中…  $URL"
echo "（按 Ctrl+C 停止）"

if [[ "$OPEN" == "open" ]]; then
  ( sleep 1.5; open "$URL" ) &
fi

exec "$PY" "$DIR/serve.py" --preset "$PRESET" --port "$PORT"
