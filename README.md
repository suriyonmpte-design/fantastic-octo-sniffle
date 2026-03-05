# Prime Tech Enterprise — Full Workflow System (TH/EN)

ระบบต้นแบบแบบ **เต็มระบบของจริง** สำหรับงานบริการองค์กร (ลิฟต์, UPS, ทีมภาคสนาม) พร้อมทั้ง CLI, API และ Web Dashboard สองภาษา TH/EN

## Features
- TH/EN master data: client, project, task
- Service tickets / incident tracking
- KPI dashboard (project progress, task completion, open tickets)
- CSV export for reporting
- Audit log for traceability
- Built-in Web Portal + REST API (no external framework)

## Quick Start
```bash
bash tools/run_demo.sh
python3 src/enterprise_workflow.py --db data/workflow.db serve-web --port 8080
```

Open: `http://127.0.0.1:8080`

## Main Commands
- `init-db`
- `seed-full-system`
- `dashboard`
- `add-client`
- `add-project`
- `add-task`
- `update-task`
- `export-csv`
- `serve-web`

## API Endpoints
- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/tasks.csv`
- `POST /api/task/update`
- `POST /api/ticket/create`

## Documentation
- `docs/workflow_full_service_th.md`
- `docs/workflow_full_service_th_en.md`
