import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory_engine import MemoryEngine


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "memory" / "schema.sql"


class MemoryEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "memory.db"
        self.engine = MemoryEngine(self.db, SCHEMA)
        self.engine.initialize()
        self.engine.add_domain("Personal")
        self.engine.add_domain("Project")

    def tearDown(self):
        self.tmp.cleanup()

    def add_candidate(self, claim="Atomic claim", **kwargs):
        defaults = {
            "memory_type": "stable_fact",
            "confidence": 0.9,
            "source_type": "user_explicit",
            "primary_domain": "Personal",
            "domain_confidence": 1.0,
            "domain_verified": False,
        }
        defaults.update(kwargs)
        return self.engine.add_candidate(claim, **defaults)

    def test_unverified_memory_is_blocked_at_point_of_use(self):
        memory_id = self.add_candidate(impact="high")
        gate = self.engine.point_of_use_gate([memory_id])
        self.assertFalse(gate.allowed)
        self.assertIn(memory_id, gate.memory_ids)

        self.engine.verify_memory(memory_id)
        gate = self.engine.point_of_use_gate([memory_id])
        self.assertTrue(gate.allowed)

    def test_verification_requires_primary_domain(self):
        memory_id = self.engine.add_candidate(
            "Needs classification",
            memory_type="idea",
            confidence=0.7,
            source_type="user_explicit",
        )
        with self.assertRaises(ValueError):
            self.engine.verify_memory(memory_id)
        self.engine.verify_memory(memory_id, primary_domain="Personal")
        self.assertEqual(self.engine.get_memory(memory_id)["status"], "verified")

    def test_correction_preserves_history(self):
        old_id = self.add_candidate("Old statement")
        self.engine.verify_memory(old_id)
        new_id = self.engine.supersede_memory(old_id, "Corrected statement")

        old = self.engine.get_memory(old_id)
        new = self.engine.get_memory(new_id)
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(new["status"], "verified")
        self.assertEqual(new["source_type"], "user_correction")
        self.assertEqual(new["supersedes_id"], old_id)

    def test_contradicting_evidence_disputes_memory(self):
        memory_id = self.add_candidate()
        self.engine.verify_memory(memory_id)
        self.engine.add_evidence(
            memory_id,
            stance="contradicts",
            source_type="user_explicit",
            note="new conflicting statement",
        )
        memory = self.engine.get_memory(memory_id)
        self.assertEqual(memory["status"], "disputed")
        self.assertTrue(any(item["reason"] == "contradiction" for item in self.engine.list_audit_items()))

    def test_inferred_relationship_is_audited(self):
        first = self.add_candidate("First")
        second = self.add_candidate("Second")
        relationship_id = self.engine.add_relationship(
            first,
            second,
            "related_to",
            primary_domain="Personal",
            confidence=0.6,
            inferred=True,
        )
        items = self.engine.list_audit_items()
        self.assertTrue(
            any(
                item["item_type"] == "relationship"
                and item["item_id"] == relationship_id
                and item["reason"] == "inferred_relationship"
                for item in items
            )
        )

    def test_quantity_trigger_at_twenty_unresolved_candidates(self):
        for index in range(20):
            self.add_candidate(f"candidate {index}", impact="low")
        status = self.engine.audit_due()
        self.assertIn("quantity", status["triggers"])

    def test_high_impact_trigger_at_five(self):
        for index in range(5):
            self.add_candidate(f"important {index}", impact="high")
        status = self.engine.audit_due()
        self.assertIn("high_impact_quantity", status["triggers"])

    def test_type_aware_staleness_only_after_policy_is_configured(self):
        memory_id = self.add_candidate(memory_type="project_status")
        self.engine.verify_memory(memory_id)

        with self.engine.connect() as conn:
            old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            conn.execute(
                "UPDATE memories SET created_at = ?, last_validated_at = ? WHERE id = ?",
                (old, old, memory_id),
            )

        self.assertTrue(self.engine.point_of_use_gate([memory_id]).allowed)
        self.engine.configure_memory_type("project_status", 7)
        gate = self.engine.point_of_use_gate([memory_id])
        self.assertFalse(gate.allowed)
        self.assertTrue(any(reason.endswith(":stale") for reason in gate.reasons))

    def test_physical_deletion_requires_explicit_intent(self):
        memory_id = self.add_candidate()
        with self.assertRaises(ValueError):
            self.engine.delete_memory(memory_id)
        self.engine.delete_memory(memory_id, explicit=True)
        with self.assertRaises(KeyError):
            self.engine.get_memory(memory_id)

    def test_source_precedence_matches_contract(self):
        ordered = [
            "user_correction",
            "user_explicit",
            "tool_observation",
            "verified_memory",
            "strong_inference",
            "weak_inference",
        ]
        ranks = [self.engine.source_rank(item) for item in ordered]
        self.assertEqual(ranks, sorted(ranks, reverse=True))


if __name__ == "__main__":
    unittest.main()
