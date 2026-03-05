#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-data/workflow.db}"

python3 src/enterprise_workflow.py --db "$DB_PATH" seed-demo
python3 src/enterprise_workflow.py --db "$DB_PATH" dashboard
