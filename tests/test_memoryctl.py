import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORYCTL = ROOT / "memoryctl.py"
VERIFY_GRAPH = ROOT / "verify-memory-graph.py"


class MemoryCtlTests(unittest.TestCase):
    def test_runtime_init_requires_explicit_domains_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "agent"
            first = subprocess.run(
                [sys.executable, str(MEMORYCTL), "runtime-init", "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            first_result = json.loads(first.stdout)
            self.assertFalse(first_result["ready"])
            self.assertEqual(first_result["active_domains"], [])
            self.assertTrue((root / "memory/memory.db").is_file())
            self.assertTrue((root / "config/memory-domains.txt").is_file())

            configured = subprocess.run(
                [
                    sys.executable, str(MEMORYCTL), "runtime-init", "--root", str(root),
                    "--domains", "Personal,Project Alpha,Personal",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            configured_result = json.loads(configured.stdout)
            self.assertTrue(configured_result["ready"])
            self.assertEqual(configured_result["active_domains"], ["Personal", "Project Alpha"])

            added = subprocess.run(
                [
                    sys.executable, str(MEMORYCTL), "--db", str(root / "memory/memory.db"),
                    "add", "Preserve this claim", "--type", "stable_fact",
                    "--confidence", "0.9", "--source", "user_explicit",
                    "--domain", "Personal",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            memory_id = json.loads(added.stdout)["memory_id"]

            verified = subprocess.run(
                [sys.executable, str(VERIFY_GRAPH), "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("MEMORY_GRAPH_VERIFIED", verified.stdout)

            repeated = subprocess.run(
                [sys.executable, str(MEMORYCTL), "runtime-init", "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(repeated.stdout)["active_domains"], ["Personal", "Project Alpha"])
            preserved = subprocess.run(
                [sys.executable, str(MEMORYCTL), "--db", str(root / "memory/memory.db"), "show", memory_id],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(preserved.stdout)["claim"], "Preserve this claim")

            (root / "config/memory-domains.txt").write_text("# intentionally unconfigured\n", encoding="utf-8")
            unconfigured = subprocess.run(
                [sys.executable, str(MEMORYCTL), "runtime-init", "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertFalse(json.loads(unconfigured.stdout)["ready"])
            failed = subprocess.run(
                [sys.executable, str(VERIFY_GRAPH), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn("MEMORY_GRAPH_NOT_READY", failed.stdout)
            listed = subprocess.run(
                [sys.executable, str(MEMORYCTL), "--db", str(root / "memory/memory.db"), "domain", "list"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(listed.stdout)["domains"], [])

    def test_init_sync_and_list_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "memory.db"
            domains = tmp_path / "domains.txt"
            domains.write_text("# explicit configuration\nPersonal\nProject Alpha\nPersonal\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(MEMORYCTL), "--db", str(db), "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            sync = subprocess.run(
                [sys.executable, str(MEMORYCTL), "--db", str(db), "domain", "sync", str(domains)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(sync.stdout)["active_domains"], ["Personal", "Project Alpha"])
            listed = subprocess.run(
                [sys.executable, str(MEMORYCTL), "--db", str(db), "domain", "list"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(listed.stdout)["domains"], ["Personal", "Project Alpha"])


if __name__ == "__main__":
    unittest.main()
