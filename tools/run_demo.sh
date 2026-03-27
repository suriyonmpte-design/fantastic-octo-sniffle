#!/usr/bin/env bash
set -euo pipefail
DB_PATH="${1:-data/workflow.db}"

python3 src/enterprise_workflow.py --db "$DB_PATH" seed-full-system
python3 src/enterprise_workflow.py --db "$DB_PATH" dashboard
python3 src/enterprise_workflow.py --db "$DB_PATH" export-csv --output exports/tasks_demo.csv
