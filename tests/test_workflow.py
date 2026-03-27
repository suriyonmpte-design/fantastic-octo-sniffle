import tempfile
import unittest
from pathlib import Path

from src.enterprise_workflow import WorkflowDB, seed_full_system


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.db = WorkflowDB(self.db_path)
        self.db.init_db()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_seed_and_dashboard(self):
        seed_full_system(self.db)
        dash = self.db.dashboard()
        self.assertEqual(dash["metrics"]["clients"], 1)
        self.assertEqual(dash["metrics"]["projects"], 1)
        self.assertGreaterEqual(dash["metrics"]["tasks"], 5)

    def test_advance_gate(self):
        client = self.db.add_client("a", "b", "c", "x@y.com", "1")
        project = self.db.add_project(client, "P-1", "th", "en", "sth", "sen", "2026-01-01", "2026-12-01")
        next_gate = self.db.advance_project_gate(project)
        self.assertEqual(next_gate, "gate_1")

    def test_close_ticket(self):
        client = self.db.add_client("a", "b", "c", "x@y.com", "1")
        project = self.db.add_project(client, "P-2", "th", "en", "sth", "sen", "2026-01-01", "2026-12-01")
        self.db.add_ticket(project, "INC-1", "elevator", "high", "issue", "team")
        self.db.close_ticket("INC-1")
        dash = self.db.dashboard()
        self.assertEqual(dash["tickets"][0]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
