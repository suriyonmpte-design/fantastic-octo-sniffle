# Prime Tech Enterprise — Ultimate Full Workflow System (TH/EN)

ระบบฟรีแบบครบวงจรสำหรับงานบริการองค์กร (ลิฟต์ / UPS / ทีมช่างภาคสนาม) พร้อม CLI, API, Web Dashboard, workflow gate processing, ticket lifecycle และเครื่องมือทดสอบอัตโนมัติ

## What is included
- Workflow core: client/project/task/ticket + audit log
- Stage-gate progression (`gate_0` -> `gate_4`)
- Ticket lifecycle (open -> in_progress -> resolved -> closed)
- TH/EN dashboard and reporting API
- CSV export for external BI
- End-to-end smoke script + unit tests

## Quick Start
```bash
bash tools/run_demo.sh
python3 src/enterprise_workflow.py --db data/workflow.db serve-web --port 8080
```

Open `http://127.0.0.1:8080`

## Main CLI Commands
- `init-db`
- `seed-full-system`
- `dashboard`
- `add-client`
- `add-project`
- `add-task`
- `update-task`
- `advance-gate`
- `close-ticket`
- `export-csv`
- `serve-web`

## API Endpoints
- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/tasks.csv`
- `POST /api/task/update`
- `POST /api/ticket/create`
- `POST /api/project/advance-gate`
- `POST /api/ticket/close`

## Validation Commands
```bash
python3 -m py_compile src/enterprise_workflow.py
python3 -m unittest discover -s tests
bash tools/full_system_check.sh
```

## Documents
- `docs/workflow_full_service_th.md`
- `docs/workflow_full_service_th_en.md`
