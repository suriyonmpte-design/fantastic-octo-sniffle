#!/usr/bin/env bash
set -euo pipefail
DB_PATH="${1:-/tmp/pte_full.db}"
PORT="${2:-8091}"

python3 src/enterprise_workflow.py --db "$DB_PATH" seed-full-system
python3 src/enterprise_workflow.py --db "$DB_PATH" serve-web --port "$PORT" >/tmp/pte_web.log 2>&1 &
PID=$!
trap 'kill $PID' EXIT
sleep 1
curl -s "http://127.0.0.1:${PORT}/api/health"
curl -s "http://127.0.0.1:${PORT}/api/dashboard" | python3 -m json.tool >/dev/null
curl -s "http://127.0.0.1:${PORT}/api/tasks.csv" | head -n 2
