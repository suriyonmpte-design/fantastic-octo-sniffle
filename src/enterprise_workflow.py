#!/usr/bin/env python3
"""Prime Tech Enterprise - Full Workflow System TH/EN (CLI + API + Web)."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DB_DEFAULT = "data/workflow.db"
ALLOWED_TASK_STATUSES = {"todo", "in_progress", "blocked", "done"}
ALLOWED_PROJECT_STATUSES = {"planning", "active", "on_hold", "done"}
ALLOWED_TICKET_STATUSES = {"open", "in_progress", "resolved", "closed"}
STAGE_GATES = ["gate_0", "gate_1", "gate_2", "gate_3", "gate_4"]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_th TEXT NOT NULL,
    name_en TEXT NOT NULL,
    industry TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    code TEXT NOT NULL UNIQUE,
    name_th TEXT NOT NULL,
    name_en TEXT NOT NULL,
    scope_th TEXT NOT NULL,
    scope_en TEXT NOT NULL,
    status TEXT NOT NULL,
    stage_gate TEXT NOT NULL,
    start_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    phase TEXT NOT NULL,
    title_th TEXT NOT NULL,
    title_en TEXT NOT NULL,
    owner TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    estimate_hours REAL NOT NULL,
    actual_hours REAL NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS service_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    ticket_code TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass
class WorkflowDB:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _now(self) -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    def _log(self, action: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_logs(action, payload, created_at) VALUES (?, ?, ?)",
                (action, json.dumps(payload, ensure_ascii=False), self._now()),
            )
            conn.commit()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        self._log("init_db", {"db_path": str(self.db_path)})

    def add_client(self, name_th: str, name_en: str, industry: str, email: str, phone: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO clients(name_th, name_en, industry, contact_email, contact_phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name_th, name_en, industry, email, phone, self._now()),
            )
            conn.commit()
            client_id = int(cur.lastrowid)
        self._log("add_client", {"client_id": client_id, "name_en": name_en})
        return client_id

    def add_project(self, client_id: int, code: str, name_th: str, name_en: str, scope_th: str, scope_en: str, start_date: str, due_date: str, status: str = "planning", stage_gate: str = "gate_0") -> int:
        if status not in ALLOWED_PROJECT_STATUSES:
            raise ValueError(f"invalid project status: {status}")
        if stage_gate not in STAGE_GATES:
            raise ValueError(f"invalid stage gate: {stage_gate}")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects(client_id, code, name_th, name_en, scope_th, scope_en, status, stage_gate, start_date, due_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (client_id, code, name_th, name_en, scope_th, scope_en, status, stage_gate, start_date, due_date, self._now()),
            )
            conn.commit()
            project_id = int(cur.lastrowid)
        self._log("add_project", {"project_id": project_id, "code": code})
        return project_id

    def advance_project_gate(self, project_id: int) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT stage_gate FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise ValueError("project not found")
            current = row["stage_gate"]
            index = STAGE_GATES.index(current)
            next_gate = STAGE_GATES[min(index + 1, len(STAGE_GATES) - 1)]
            conn.execute("UPDATE projects SET stage_gate = ? WHERE id = ?", (next_gate, project_id))
            conn.commit()
        self._log("advance_project_gate", {"project_id": project_id, "from": current, "to": next_gate})
        return next_gate

    def add_task(self, project_id: int, phase: str, title_th: str, title_en: str, owner: str, priority: str, estimate_hours: float, due_date: str, status: str = "todo") -> int:
        if status not in ALLOWED_TASK_STATUSES:
            raise ValueError(f"invalid task status: {status}")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks(project_id, phase, title_th, title_en, owner, priority, status, estimate_hours, actual_hours, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (project_id, phase, title_th, title_en, owner, priority, status, estimate_hours, due_date, self._now(), self._now()),
            )
            conn.commit()
            task_id = int(cur.lastrowid)
        self._log("add_task", {"task_id": task_id, "title_en": title_en})
        return task_id

    def update_task(self, task_id: int, status: str, actual_hours: float | None = None) -> None:
        if status not in ALLOWED_TASK_STATUSES:
            raise ValueError(f"invalid task status: {status}")
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("task not found")
            if actual_hours is None:
                conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (status, self._now(), task_id))
            else:
                conn.execute("UPDATE tasks SET status = ?, actual_hours = ?, updated_at = ? WHERE id = ?", (status, actual_hours, self._now(), task_id))
            conn.commit()
        self._log("update_task", {"task_id": task_id, "status": status, "actual_hours": actual_hours})

    def add_ticket(self, project_id: int, ticket_code: str, category: str, severity: str, title: str, assignee: str, status: str = "open") -> int:
        if status not in ALLOWED_TICKET_STATUSES:
            raise ValueError(f"invalid ticket status: {status}")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO service_tickets(project_id, ticket_code, category, severity, title, status, assignee, opened_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, ticket_code, category, severity, title, status, assignee, self._now()),
            )
            conn.commit()
            ticket_id = int(cur.lastrowid)
        self._log("add_ticket", {"ticket_id": ticket_id, "ticket_code": ticket_code})
        return ticket_id

    def close_ticket(self, ticket_code: str) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM service_tickets WHERE ticket_code = ?", (ticket_code,)).fetchone()
            if row is None:
                raise ValueError("ticket not found")
            conn.execute(
                "UPDATE service_tickets SET status = 'closed', closed_at = ? WHERE ticket_code = ?",
                (self._now(), ticket_code),
            )
            conn.commit()
        self._log("close_ticket", {"ticket_code": ticket_code})

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as conn:
            summary = conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM clients) clients,
                  (SELECT COUNT(*) FROM projects) projects,
                  (SELECT COUNT(*) FROM tasks) tasks,
                  (SELECT COUNT(*) FROM tasks WHERE status = 'done') tasks_done,
                  (SELECT COUNT(*) FROM service_tickets WHERE status IN ('open', 'in_progress')) open_tickets,
                  (SELECT IFNULL(SUM(estimate_hours), 0) FROM tasks) est_hours,
                  (SELECT IFNULL(SUM(actual_hours), 0) FROM tasks) actual_hours
                """
            ).fetchone()
            projects = conn.execute(
                """
                SELECT p.id, p.code, p.name_th, p.name_en, p.status, p.stage_gate,
                       COUNT(t.id) task_count,
                       SUM(CASE WHEN t.status='done' THEN 1 ELSE 0 END) done_count
                FROM projects p
                LEFT JOIN tasks t ON p.id=t.project_id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                """
            ).fetchall()
            tasks = conn.execute(
                """
                SELECT t.id, p.code AS project_code, t.title_th, t.title_en, t.owner, t.priority, t.status, t.due_date
                FROM tasks t JOIN projects p ON p.id=t.project_id
                ORDER BY t.due_date ASC LIMIT 20
                """
            ).fetchall()
            tickets = conn.execute(
                """
                SELECT ticket_code, category, severity, title, status, assignee
                FROM service_tickets ORDER BY opened_at DESC LIMIT 20
                """
            ).fetchall()
        metrics = dict(summary)
        metrics["completion_rate_percent"] = round((metrics["tasks_done"] / metrics["tasks"] * 100) if metrics["tasks"] else 0, 2)
        return {
            "generated_at": self._now(),
            "metrics": metrics,
            "projects": [dict(x) for x in projects],
            "tasks": [dict(x) for x in tasks],
            "tickets": [dict(x) for x in tickets],
        }

    def export_tasks_csv(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT p.code, t.phase, t.title_th, t.title_en, t.owner, t.priority, t.status, t.estimate_hours, t.actual_hours, t.due_date
                FROM tasks t JOIN projects p ON p.id=t.project_id
                ORDER BY p.code, t.id
                """
            ).fetchall()
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["project_code", "phase", "title_th", "title_en", "owner", "priority", "status", "estimate_hours", "actual_hours", "due_date"])
            for r in rows:
                writer.writerow([r["code"], r["phase"], r["title_th"], r["title_en"], r["owner"], r["priority"], r["status"], r["estimate_hours"], r["actual_hours"], r["due_date"]])
        self._log("export_tasks_csv", {"path": str(output_path)})
        return output_path


def seed_full_system(db: WorkflowDB) -> None:
    client_id = db.add_client(
        "บริษัท ไพรม์ เทค เอนเตอร์ไพรส์ จำกัด",
        "Prime Tech Enterprise Co., Ltd.",
        "Elevator Maintenance & UPS Power Solutions",
        "primetech.pte@gmail.com",
        "065-424-1655",
    )
    project_id = db.add_project(
        client_id,
        "PTE-FULL-2026",
        "ระบบงานบริการครบวงจร TH/EN",
        "TH/EN Full-Service Operations Platform",
        "งานบริการลิฟต์ + ระบบไฟสำรอง + คลังอะไหล่ + ทีมภาคสนาม + SLA",
        "Elevator service + UPS operations + spare parts + field teams + SLA",
        "2026-01-01",
        "2026-12-31",
        status="active",
        stage_gate="gate_2",
    )
    tasks = [
        ("discovery", "เก็บความต้องการทุกแผนก", "Cross-department requirement discovery", "BA Team", "critical", 60, "2026-02-01"),
        ("design", "ออกแบบระบบ Workflow + SLA", "Design workflow + SLA engine", "Solution Architect", "critical", 100, "2026-03-01"),
        ("build", "พัฒนา Web Portal TH/EN", "Build TH/EN web portal", "Engineering", "high", 140, "2026-04-15"),
        ("integration", "เชื่อมงานช่างภาคสนาม", "Integrate field service operations", "Integration Team", "high", 120, "2026-05-15"),
        ("qa", "ทดสอบ UAT/Security/Performance", "UAT/Security/Performance testing", "QA & Sec", "critical", 110, "2026-06-01"),
    ]
    for phase, th, en, owner, pri, est, due in tasks:
        db.add_task(project_id, phase, th, en, owner, pri, est, due)
    db.add_ticket(project_id, "INC-2026-001", "elevator", "high", "Emergency breakdown @ Pattaya site", "On-call Team", "in_progress")
    db.add_ticket(project_id, "SR-2026-002", "ups", "medium", "UPS battery replacement plan", "Power Team", "open")


DASHBOARD_HTML = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Prime Tech Enterprise - Full System</title><style>
body{font-family:Arial,sans-serif;background:#0b0d12;color:#eef;margin:0}header{padding:20px 28px;border-bottom:1px solid #29313f}
.brand{color:#c7ff10;font-weight:800;font-size:28px}.subtitle{color:#b5bcc8}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;padding:20px}
.card{background:#131824;border:1px solid #2a3143;border-radius:12px;padding:16px}.card h3{margin:0 0 8px;color:#c7ff10}.big{font-size:28px;font-weight:800}
section{padding:0 20px 20px}table{width:100%;border-collapse:collapse;background:#131824;border:1px solid #2a3143}th,td{padding:10px;border-bottom:1px solid #2a3143;text-align:left;font-size:14px}th{color:#c7ff10}
</style></head><body><header><div class='brand'>PRIME TECH ENTERPRISE</div><div class='subtitle'>TH/EN Full-Service Workflow Platform | ระบบบริหารงานบริการครบวงจร</div></header>
<div class='grid' id='metricGrid'></div><section><h2>Projects / โครงการ</h2><table id='projects'><thead><tr><th>Code</th><th>Name EN</th><th>Name TH</th><th>Status</th><th>Gate</th><th>Progress</th></tr></thead><tbody></tbody></table></section>
<section><h2>Tasks / งาน</h2><table id='tasks'><thead><tr><th>Project</th><th>Title EN</th><th>Title TH</th><th>Owner</th><th>Status</th><th>Due</th></tr></thead><tbody></tbody></table></section>
<script>async function load(){const r=await fetch('/api/dashboard');const d=await r.json();const m=d.metrics;const n=[['Clients','ลูกค้า',m.clients],['Projects','โครงการ',m.projects],['Tasks','งาน',m.tasks],['Done %','ความคืบหน้า',m.completion_rate_percent+'%'],['Open Tickets','ทิคเก็ตคงค้าง',m.open_tickets],['Hours (Est/Actual)','ชั่วโมง (แผน/จริง)',`${m.est_hours} / ${m.actual_hours}`]];document.getElementById('metricGrid').innerHTML=n.map(x=>`<div class='card'><h3>${x[0]}</h3><div>${x[1]}</div><div class='big'>${x[2]}</div></div>`).join('');document.querySelector('#projects tbody').innerHTML=d.projects.map(p=>`<tr><td>${p.code}</td><td>${p.name_en}</td><td>${p.name_th}</td><td>${p.status}</td><td>${p.stage_gate}</td><td>${p.done_count}/${p.task_count}</td></tr>`).join('');document.querySelector('#tasks tbody').innerHTML=d.tasks.map(t=>`<tr><td>${t.project_code}</td><td>${t.title_en}</td><td>${t.title_th}</td><td>${t.owner}</td><td>${t.status}</td><td>${t.due_date}</td></tr>`).join('');}load();</script></body></html>"""


def make_handler(db: WorkflowDB):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, body: str, content_type: str = "text/plain", code: int = 200) -> None:
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("empty body")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_text(DASHBOARD_HTML, content_type="text/html")
                return
            if parsed.path == "/api/health":
                self._send_json({"status": "ok", "timestamp": db._now()})
                return
            if parsed.path == "/api/dashboard":
                self._send_json(db.dashboard())
                return
            if parsed.path == "/api/tasks.csv":
                tmp = Path("data/tasks_export.csv")
                db.export_tasks_csv(tmp)
                self._send_text(tmp.read_text(encoding="utf-8"), content_type="text/csv")
                return
            self._send_json({"error": "not found"}, code=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                data = self._read_json()
                if parsed.path == "/api/task/update":
                    db.update_task(int(data["task_id"]), data["status"], data.get("actual_hours"))
                    self._send_json({"ok": True})
                    return
                if parsed.path == "/api/ticket/create":
                    tid = db.add_ticket(
                        int(data["project_id"]),
                        data["ticket_code"],
                        data["category"],
                        data["severity"],
                        data["title"],
                        data["assignee"],
                        data.get("status", "open"),
                    )
                    self._send_json({"ticket_id": tid}, code=HTTPStatus.CREATED)
                    return
                if parsed.path == "/api/project/advance-gate":
                    next_gate = db.advance_project_gate(int(data["project_id"]))
                    self._send_json({"next_gate": next_gate})
                    return
                if parsed.path == "/api/ticket/close":
                    db.close_ticket(data["ticket_code"])
                    self._send_json({"ok": True})
                    return
                self._send_json({"error": "not found"}, code=404)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, code=400)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prime Tech Enterprise Full Workflow TH/EN")
    parser.add_argument("--db", default=DB_DEFAULT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("seed-full-system")
    sub.add_parser("dashboard")

    c = sub.add_parser("add-client")
    c.add_argument("--name-th", required=True)
    c.add_argument("--name-en", required=True)
    c.add_argument("--industry", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--phone", required=True)

    p = sub.add_parser("add-project")
    p.add_argument("--client-id", type=int, required=True)
    p.add_argument("--code", required=True)
    p.add_argument("--name-th", required=True)
    p.add_argument("--name-en", required=True)
    p.add_argument("--scope-th", required=True)
    p.add_argument("--scope-en", required=True)
    p.add_argument("--start-date", required=True)
    p.add_argument("--due-date", required=True)
    p.add_argument("--status", default="planning")
    p.add_argument("--stage-gate", default="gate_0")

    t = sub.add_parser("add-task")
    t.add_argument("--project-id", type=int, required=True)
    t.add_argument("--phase", required=True)
    t.add_argument("--title-th", required=True)
    t.add_argument("--title-en", required=True)
    t.add_argument("--owner", required=True)
    t.add_argument("--priority", required=True)
    t.add_argument("--estimate-hours", type=float, required=True)
    t.add_argument("--due-date", required=True)
    t.add_argument("--status", default="todo")

    u = sub.add_parser("update-task")
    u.add_argument("--task-id", type=int, required=True)
    u.add_argument("--status", required=True)
    u.add_argument("--actual-hours", type=float)

    g = sub.add_parser("advance-gate")
    g.add_argument("--project-id", type=int, required=True)

    k = sub.add_parser("close-ticket")
    k.add_argument("--ticket-code", required=True)

    x = sub.add_parser("export-csv")
    x.add_argument("--output", default="exports/tasks.csv")

    s = sub.add_parser("serve-web")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = WorkflowDB(Path(args.db))
    if args.command == "init-db":
        db.init_db()
        print("Initialized DB")
    elif args.command == "seed-full-system":
        db.init_db()
        seed_full_system(db)
        print("Seeded full system")
    elif args.command == "dashboard":
        print(json.dumps(db.dashboard(), ensure_ascii=False, indent=2))
    elif args.command == "add-client":
        print(db.add_client(args.name_th, args.name_en, args.industry, args.email, args.phone))
    elif args.command == "add-project":
        print(db.add_project(args.client_id, args.code, args.name_th, args.name_en, args.scope_th, args.scope_en, args.start_date, args.due_date, args.status, args.stage_gate))
    elif args.command == "add-task":
        print(db.add_task(args.project_id, args.phase, args.title_th, args.title_en, args.owner, args.priority, args.estimate_hours, args.due_date, args.status))
    elif args.command == "update-task":
        db.update_task(args.task_id, args.status, args.actual_hours)
        print("Updated")
    elif args.command == "advance-gate":
        print(db.advance_project_gate(args.project_id))
    elif args.command == "close-ticket":
        db.close_ticket(args.ticket_code)
        print("Closed")
    elif args.command == "export-csv":
        print(db.export_tasks_csv(Path(args.output)))
    elif args.command == "serve-web":
        server = ThreadingHTTPServer((args.host, args.port), make_handler(db))
        print(f"Serving on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
