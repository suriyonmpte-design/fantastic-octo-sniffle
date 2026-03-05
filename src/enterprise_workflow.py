#!/usr/bin/env python3
"""Prime Tech Enterprise Pattaya - Full Service Workflow System (Free App)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DB_DEFAULT = "data/workflow.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    contact TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    start_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    phase TEXT NOT NULL,
    title TEXT NOT NULL,
    owner TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    estimate_hours REAL NOT NULL,
    actual_hours REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
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
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        self._log("init_db", {"db_path": str(self.db_path)})

    def _now(self) -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    def _log(self, action: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_logs(action, payload, created_at) VALUES (?, ?, ?)",
                (action, json.dumps(payload, ensure_ascii=False), self._now()),
            )
            conn.commit()

    def add_client(self, name: str, industry: str, contact: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO clients(name, industry, contact, created_at) VALUES (?, ?, ?, ?)",
                (name, industry, contact, self._now()),
            )
            conn.commit()
            client_id = cur.lastrowid
        self._log("add_client", {"client_id": client_id, "name": name})
        return int(client_id)

    def add_project(
        self,
        client_id: int,
        code: str,
        name: str,
        scope: str,
        start_date: str,
        due_date: str,
        status: str = "planning",
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects(client_id, code, name, scope, status, start_date, due_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (client_id, code, name, scope, status, start_date, due_date, self._now()),
            )
            conn.commit()
            project_id = cur.lastrowid
        self._log("add_project", {"project_id": project_id, "code": code})
        return int(project_id)

    def add_task(
        self,
        project_id: int,
        phase: str,
        title: str,
        owner: str,
        priority: str,
        estimate_hours: float,
        status: str = "todo",
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks(project_id, phase, title, owner, priority, status, estimate_hours, actual_hours, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    project_id,
                    phase,
                    title,
                    owner,
                    priority,
                    status,
                    estimate_hours,
                    self._now(),
                    self._now(),
                ),
            )
            conn.commit()
            task_id = cur.lastrowid
        self._log("add_task", {"task_id": task_id, "title": title})
        return int(task_id)

    def update_task_status(self, task_id: int, status: str, actual_hours: float | None = None) -> None:
        with self.connect() as conn:
            if actual_hours is None:
                conn.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                    (status, self._now(), task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ?, actual_hours = ?, updated_at = ? WHERE id = ?",
                    (status, actual_hours, self._now(), task_id),
                )
            conn.commit()
        self._log("update_task_status", {"task_id": task_id, "status": status, "actual_hours": actual_hours})

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as conn:
            totals = conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM clients) AS clients,
                  (SELECT COUNT(*) FROM projects) AS projects,
                  (SELECT COUNT(*) FROM tasks) AS tasks,
                  (SELECT COUNT(*) FROM tasks WHERE status = 'done') AS done_tasks,
                  (SELECT IFNULL(SUM(estimate_hours), 0) FROM tasks) AS est_hours,
                  (SELECT IFNULL(SUM(actual_hours), 0) FROM tasks) AS actual_hours
                """
            ).fetchone()

            rows = conn.execute(
                """
                SELECT p.code, p.name, p.status,
                       COUNT(t.id) AS task_count,
                       SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                """
            ).fetchall()

        projects = [dict(r) for r in rows]
        metrics = dict(totals)
        completion_rate = (metrics["done_tasks"] / metrics["tasks"] * 100) if metrics["tasks"] else 0
        metrics["completion_rate_percent"] = round(completion_rate, 2)
        return {"metrics": metrics, "projects": projects}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prime Tech Enterprise Workflow Full Service CLI")
    parser.add_argument("--db", default=DB_DEFAULT, help="SQLite DB path")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")

    c = sub.add_parser("add-client")
    c.add_argument("--name", required=True)
    c.add_argument("--industry", required=True)
    c.add_argument("--contact", required=True)

    p = sub.add_parser("add-project")
    p.add_argument("--client-id", type=int, required=True)
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--scope", required=True)
    p.add_argument("--start-date", required=True)
    p.add_argument("--due-date", required=True)
    p.add_argument("--status", default="planning")

    t = sub.add_parser("add-task")
    t.add_argument("--project-id", type=int, required=True)
    t.add_argument("--phase", required=True)
    t.add_argument("--title", required=True)
    t.add_argument("--owner", required=True)
    t.add_argument("--priority", required=True, choices=["low", "medium", "high", "critical"])
    t.add_argument("--estimate-hours", type=float, required=True)
    t.add_argument("--status", default="todo")

    u = sub.add_parser("update-task")
    u.add_argument("--task-id", type=int, required=True)
    u.add_argument("--status", required=True, choices=["todo", "in_progress", "blocked", "done"])
    u.add_argument("--actual-hours", type=float)

    sub.add_parser("dashboard")
    sub.add_parser("seed-demo")
    return parser.parse_args()


def seed_demo(db: WorkflowDB) -> None:
    client = db.add_client("Prime Tech Enterprise Pattaya", "Digital Transformation", "ops@primetech.local")
    project = db.add_project(
        client,
        "PTE-ERP-001",
        "Prime Full-Service Workflow App",
        "CRM + Project Ops + Service Desk + KPI Dashboard",
        "2026-01-01",
        "2026-12-31",
        "active",
    )
    db.add_task(project, "discovery", "เก็บ Requirement ทั้งองค์กร", "BA Team", "critical", 80)
    db.add_task(project, "design", "ออกแบบ Enterprise Architecture", "Solution Architect", "high", 120)
    db.add_task(project, "build", "พัฒนา Automation Workflow", "Engineering", "critical", 200)
    db.add_task(project, "qa", "ทำ UAT และ Security Test", "QA/Sec", "high", 100)


def main() -> None:
    args = parse_args()
    db = WorkflowDB(Path(args.db))

    if args.command == "init-db":
        db.init_db()
        print("Initialized DB")
    elif args.command == "add-client":
        cid = db.add_client(args.name, args.industry, args.contact)
        print(f"Created client {cid}")
    elif args.command == "add-project":
        pid = db.add_project(
            args.client_id,
            args.code,
            args.name,
            args.scope,
            args.start_date,
            args.due_date,
            args.status,
        )
        print(f"Created project {pid}")
    elif args.command == "add-task":
        tid = db.add_task(
            args.project_id,
            args.phase,
            args.title,
            args.owner,
            args.priority,
            args.estimate_hours,
            args.status,
        )
        print(f"Created task {tid}")
    elif args.command == "update-task":
        db.update_task_status(args.task_id, args.status, args.actual_hours)
        print(f"Updated task {args.task_id}")
    elif args.command == "dashboard":
        print(json.dumps(db.dashboard(), ensure_ascii=False, indent=2))
    elif args.command == "seed-demo":
        db.init_db()
        seed_demo(db)
        print("Seeded demo data")


if __name__ == "__main__":
    main()
