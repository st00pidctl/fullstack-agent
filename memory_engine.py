#!/usr/bin/env python3
"""Shell owned evidence based memory engine.

The engine intentionally uses only the Python standard library and SQLite.
It stores atomic claims, provenance, relationships, audit state, and action gates.
It does not infer truth from graph density and it does not invent domains.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


SOURCE_RANK = {
    "user_correction": 6,
    "user_explicit": 5,
    "tool_observation": 4,
    "verified_memory": 3,
    "strong_inference": 2,
    "weak_inference": 1,
}

DEFAULT_MEMORY_TYPES = (
    "stable_fact",
    "preference",
    "decision",
    "project_status",
    "business_fact",
    "configuration",
    "schedule",
    "pricing",
    "relationship",
    "idea",
)

WEEKLY_AUDIT_DAYS = 7
UNRESOLVED_CANDIDATE_TRIGGER = 20
HIGH_IMPACT_TRIGGER = 5


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    memory_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "memory_ids": list(self.memory_ids),
            "reasons": list(self.reasons),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MemoryEngine:
    def __init__(self, db_path: str | Path, schema_path: str | Path | None = None):
        self.db_path = Path(db_path).expanduser()
        self.schema_path = (
            Path(schema_path).expanduser()
            if schema_path
            else Path(__file__).resolve().parent / "memory" / "schema.sql"
        )

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        now = utc_now()
        with self.connect() as conn:
            conn.executescript(schema)
            for memory_type in DEFAULT_MEMORY_TYPES:
                conn.execute(
                    "INSERT OR IGNORE INTO memory_types(name, review_after_days, decay_enabled, created_at) VALUES (?, NULL, 0, ?)",
                    (memory_type, now),
                )
            self._set_state(conn, "schema_version", "1", now)

    def add_domain(self, name: str) -> None:
        clean = name.strip()
        if not clean:
            raise ValueError("domain name cannot be empty")
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO domains(name, active, created_at) VALUES (?, 1, ?)",
                (clean, utc_now()),
            )

    def list_domains(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM domains WHERE active = 1 ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [row["name"] for row in rows]

    def sync_domains(self, names: Iterable[str]) -> list[str]:
        """Make an explicit operator-owned list the active domain set.

        Retired domains remain in the database so historical claims keep valid
        foreign keys, but they cannot be assigned to new or re-verified memory.
        """
        domains: list[str] = []
        seen: set[str] = set()
        for name in names:
            clean = name.strip()
            if not clean or clean in seen:
                continue
            domains.append(clean)
            seen.add(clean)
        if not domains:
            raise ValueError("domain sync requires at least one explicit domain")

        now = utc_now()
        with self.connect() as conn:
            conn.execute("UPDATE domains SET active = 0")
            for domain in domains:
                conn.execute(
                    """
                    INSERT INTO domains(name, active, created_at) VALUES (?, 1, ?)
                    ON CONFLICT(name) DO UPDATE SET active = 1
                    """,
                    (domain, now),
                )
        return domains

    def deactivate_all_domains(self) -> None:
        """Fail closed when no explicit runtime domain configuration exists."""
        with self.connect() as conn:
            conn.execute("UPDATE domains SET active = 0")

    def configure_memory_type(self, name: str, review_after_days: int | None) -> None:
        if review_after_days is not None and review_after_days <= 0:
            raise ValueError("review_after_days must be positive or null")
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO memory_types(name, review_after_days, decay_enabled, created_at) VALUES (?, NULL, 0, ?)",
                (name, now),
            )
            conn.execute(
                "UPDATE memory_types SET review_after_days = ?, decay_enabled = ? WHERE name = ?",
                (review_after_days, 1 if review_after_days is not None else 0, name),
            )

    def add_candidate(
        self,
        claim: str,
        *,
        memory_type: str,
        confidence: float,
        source_type: str,
        primary_domain: str | None = None,
        domain_confidence: float | None = None,
        domain_verified: bool = False,
        source_ref: str | None = None,
        source_timestamp: str | None = None,
        relevance: float = 0.5,
        freshness: float = 1.0,
        impact: str = "normal",
        likely_action_driver: bool = False,
        contradiction: bool = False,
        metadata: dict | None = None,
    ) -> str:
        self._validate_score("confidence", confidence)
        self._validate_score("relevance", relevance)
        self._validate_score("freshness", freshness)
        if domain_confidence is not None:
            self._validate_score("domain_confidence", domain_confidence)
        self._validate_source_type(source_type)
        if impact not in {"low", "normal", "high"}:
            raise ValueError("impact must be low, normal, or high")

        claim = claim.strip()
        if not claim:
            raise ValueError("claim cannot be empty")

        memory_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            self._require_memory_type(conn, memory_type)
            if primary_domain is not None:
                self._require_domain(conn, primary_domain)
            if domain_verified and primary_domain is None:
                raise ValueError("domain_verified requires a primary_domain")

            conn.execute(
                """
                INSERT INTO memories(
                    id, claim, status, primary_domain, domain_confidence,
                    domain_verified, memory_type, confidence, relevance,
                    freshness, source_type, source_ref, source_timestamp,
                    user_confirmed, impact, likely_action_driver,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    claim,
                    primary_domain,
                    domain_confidence,
                    1 if domain_verified else 0,
                    memory_type,
                    confidence,
                    relevance,
                    freshness,
                    source_type,
                    source_ref,
                    source_timestamp,
                    impact,
                    1 if likely_action_driver else 0,
                    now,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )

            self._queue_audit(conn, "memory", memory_id, "candidate_review", "normal", now)
            if primary_domain is None or not domain_verified:
                self._queue_audit(
                    conn, "domain_assignment", memory_id, "domain_unverified", "high", now
                )
            if impact == "high":
                self._queue_audit(conn, "memory", memory_id, "high_impact", "high", now)
            if likely_action_driver:
                self._queue_audit(
                    conn, "memory", memory_id, "likely_action_driver", "high", now
                )
            if contradiction:
                conn.execute(
                    "UPDATE memories SET status = 'disputed', updated_at = ? WHERE id = ?",
                    (now, memory_id),
                )
                self._queue_audit(conn, "memory", memory_id, "contradiction", "high", now)

        return memory_id

    def add_evidence(
        self,
        memory_id: str,
        *,
        stance: str,
        source_type: str,
        source_ref: str | None = None,
        confidence: float | None = None,
        note: str | None = None,
        observed_at: str | None = None,
    ) -> str:
        if stance not in {"supports", "contradicts"}:
            raise ValueError("stance must be supports or contradicts")
        self._validate_source_type(source_type)
        if confidence is not None:
            self._validate_score("confidence", confidence)
        evidence_id = str(uuid.uuid4())
        now = observed_at or utc_now()
        with self.connect() as conn:
            self._require_memory(conn, memory_id)
            conn.execute(
                """
                INSERT INTO evidence(id, memory_id, stance, source_type, source_ref, observed_at, confidence, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (evidence_id, memory_id, stance, source_type, source_ref, now, confidence, note),
            )
            if stance == "contradicts":
                conn.execute(
                    "UPDATE memories SET status = 'disputed', updated_at = ? WHERE id = ? AND status NOT IN ('superseded', 'rejected')",
                    (utc_now(), memory_id),
                )
                self._queue_audit(
                    conn, "memory", memory_id, "contradiction", "high", utc_now()
                )
        return evidence_id

    def verify_memory(self, memory_id: str, *, primary_domain: str | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            row = self._require_memory(conn, memory_id)
            if row["status"] in {"superseded", "rejected"}:
                raise ValueError(f"cannot verify {row['status']} memory")
            domain = primary_domain or row["primary_domain"]
            if not domain:
                raise ValueError("verification requires exactly one primary domain")
            self._require_domain(conn, domain)
            conn.execute(
                """
                UPDATE memories
                SET status = 'verified', primary_domain = ?, domain_verified = 1,
                    user_confirmed = 1, last_validated_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (domain, now, now, memory_id),
            )
            self._resolve_audits(conn, "memory", memory_id, now)
            self._resolve_audits(conn, "domain_assignment", memory_id, now)

    def reject_memory(self, memory_id: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            self._require_memory(conn, memory_id)
            conn.execute(
                "UPDATE memories SET status = 'rejected', updated_at = ? WHERE id = ?",
                (now, memory_id),
            )
            self._resolve_audits(conn, "memory", memory_id, now)
            self._resolve_audits(conn, "domain_assignment", memory_id, now)

    def supersede_memory(
        self,
        old_memory_id: str,
        new_claim: str,
        *,
        memory_type: str | None = None,
        primary_domain: str | None = None,
        confidence: float = 1.0,
        source_ref: str | None = None,
    ) -> str:
        new_claim = new_claim.strip()
        if not new_claim:
            raise ValueError("replacement claim cannot be empty")
        now = utc_now()
        self._validate_score("confidence", confidence)
        with self.connect() as conn:
            old = self._require_memory(conn, old_memory_id)
            domain = primary_domain or old["primary_domain"]
            if not domain:
                raise ValueError("correction requires exactly one primary domain")
            self._require_domain(conn, domain)
            chosen_type = memory_type or old["memory_type"]
            self._require_memory_type(conn, chosen_type)

            new_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO memories(
                    id, claim, status, primary_domain, domain_confidence,
                    domain_verified, memory_type, confidence, relevance,
                    freshness, source_type, source_ref, source_timestamp,
                    user_confirmed, impact, likely_action_driver, created_at,
                    updated_at, last_validated_at, supersedes_id, metadata_json
                ) VALUES (?, ?, 'verified', ?, 1.0, 1, ?, ?, ?, 1.0,
                          'user_correction', ?, ?, 1, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    new_id,
                    new_claim,
                    domain,
                    chosen_type,
                    confidence,
                    old["relevance"],
                    source_ref,
                    now,
                    old["impact"],
                    old["likely_action_driver"],
                    now,
                    now,
                    now,
                    old_memory_id,
                ),
            )
            conn.execute(
                "UPDATE memories SET status = 'superseded', updated_at = ? WHERE id = ?",
                (now, old_memory_id),
            )
            self._resolve_audits(conn, "memory", old_memory_id, now)
            self._resolve_audits(conn, "domain_assignment", old_memory_id, now)
        return new_id

    def delete_memory(self, memory_id: str, *, explicit: bool = False) -> None:
        if not explicit:
            raise ValueError("physical deletion requires explicit=True")
        with self.connect() as conn:
            self._require_memory(conn, memory_id)
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.execute(
                "DELETE FROM audit_queue WHERE item_id = ? AND item_type IN ('memory', 'domain_assignment')",
                (memory_id,),
            )

    def add_relationship(
        self,
        from_memory_id: str,
        to_memory_id: str,
        relation_type: str,
        *,
        primary_domain: str,
        confidence: float,
        domain_confidence: float | None = None,
        inferred: bool = True,
        metadata: dict | None = None,
    ) -> str:
        self._validate_score("confidence", confidence)
        if domain_confidence is not None:
            self._validate_score("domain_confidence", domain_confidence)
        if from_memory_id == to_memory_id:
            raise ValueError("relationship endpoints must be different")
        relation_type = relation_type.strip()
        if not relation_type:
            raise ValueError("relation_type cannot be empty")
        relationship_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            self._require_memory(conn, from_memory_id)
            self._require_memory(conn, to_memory_id)
            self._require_domain(conn, primary_domain)
            status = "inferred" if inferred else "verified"
            conn.execute(
                """
                INSERT INTO relationships(
                    id, from_memory_id, to_memory_id, relation_type, status,
                    primary_domain, domain_confidence, confidence, created_at,
                    updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_id,
                    from_memory_id,
                    to_memory_id,
                    relation_type,
                    status,
                    primary_domain,
                    domain_confidence,
                    confidence,
                    now,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            if inferred:
                self._queue_audit(
                    conn,
                    "relationship",
                    relationship_id,
                    "inferred_relationship",
                    "normal",
                    now,
                )
        return relationship_id

    def verify_relationship(self, relationship_id: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM relationships WHERE id = ?", (relationship_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown relationship: {relationship_id}")
            self._require_domain(conn, row["primary_domain"])
            conn.execute(
                "UPDATE relationships SET status = 'verified', updated_at = ? WHERE id = ?",
                (now, relationship_id),
            )
            self._resolve_audits(conn, "relationship", relationship_id, now)

    def get_memory(self, memory_id: str) -> dict:
        with self.connect() as conn:
            row = self._require_memory(conn, memory_id)
            evidence = conn.execute(
                "SELECT * FROM evidence WHERE memory_id = ? ORDER BY observed_at, id",
                (memory_id,),
            ).fetchall()
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        result["evidence"] = [dict(item) for item in evidence]
        return result

    def list_audit_items(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_queue
                WHERE status = 'queued'
                ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END, created_at, id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def audit_due(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        with self.connect() as conn:
            unresolved_candidates = conn.execute(
                "SELECT COUNT(*) AS n FROM memories WHERE status IN ('candidate', 'disputed')"
            ).fetchone()["n"]
            high_impact = conn.execute(
                """
                SELECT COUNT(DISTINCT item_type || ':' || item_id) AS n
                FROM audit_queue
                WHERE status = 'queued'
                  AND reason IN ('high_impact', 'contradiction')
                """
            ).fetchone()["n"]
            last = conn.execute(
                "SELECT value FROM engine_state WHERE key = 'last_periodic_audit'"
            ).fetchone()

        weekly_due = True
        if last:
            weekly_due = now - parse_time(last["value"]) >= timedelta(days=WEEKLY_AUDIT_DAYS)

        triggers: list[str] = []
        if weekly_due:
            triggers.append("weekly")
        if unresolved_candidates >= UNRESOLVED_CANDIDATE_TRIGGER:
            triggers.append("quantity")
        if high_impact >= HIGH_IMPACT_TRIGGER:
            triggers.append("high_impact_quantity")
        return {
            "due": bool(triggers),
            "triggers": triggers,
            "unresolved_candidates": unresolved_candidates,
            "high_impact_or_contradictory": high_impact,
        }

    def begin_audit(self, trigger_type: str) -> str:
        if trigger_type not in {
            "weekly",
            "quantity",
            "high_impact_quantity",
            "point_of_use",
            "manual",
        }:
            raise ValueError("invalid audit trigger")
        audit_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_runs(id, trigger_type, started_at) VALUES (?, ?, ?)",
                (audit_id, trigger_type, utc_now()),
            )
        return audit_id

    def complete_audit(self, audit_id: str, notes: str | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM audit_runs WHERE id = ?", (audit_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown audit: {audit_id}")
            conn.execute(
                "UPDATE audit_runs SET completed_at = ?, notes = ? WHERE id = ?",
                (now, notes, audit_id),
            )
            if row["trigger_type"] == "weekly":
                self._set_state(conn, "last_periodic_audit", now, now)

    def point_of_use_gate(self, memory_ids: Iterable[str]) -> GateResult:
        blocked: list[str] = []
        reasons: list[str] = []
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            for memory_id in memory_ids:
                row = self._require_memory(conn, memory_id)
                local_reasons: list[str] = []
                if row["status"] != "verified":
                    local_reasons.append(f"{memory_id}:status={row['status']}")
                if row["primary_domain"] is None or not row["domain_verified"]:
                    local_reasons.append(f"{memory_id}:domain_unverified")
                elif conn.execute(
                    "SELECT 1 FROM domains WHERE name = ? AND active = 1",
                    (row["primary_domain"],),
                ).fetchone() is None:
                    local_reasons.append(f"{memory_id}:domain_inactive")
                if self._is_stale(conn, row, now):
                    local_reasons.append(f"{memory_id}:stale")
                if local_reasons:
                    blocked.append(memory_id)
                    reasons.extend(local_reasons)
                    self._queue_audit(
                        conn, "memory", memory_id, "point_of_use", "high", utc_now()
                    )
        return GateResult(not blocked, tuple(blocked), tuple(reasons))

    def source_rank(self, source_type: str) -> int:
        self._validate_source_type(source_type)
        return SOURCE_RANK[source_type]

    def _is_stale(self, conn: sqlite3.Connection, row: sqlite3.Row, now: datetime) -> bool:
        policy = conn.execute(
            "SELECT review_after_days, decay_enabled FROM memory_types WHERE name = ?",
            (row["memory_type"],),
        ).fetchone()
        if not policy or not policy["decay_enabled"] or policy["review_after_days"] is None:
            return False
        baseline = row["last_validated_at"] or row["created_at"]
        return now - parse_time(baseline) >= timedelta(days=policy["review_after_days"])

    def _queue_audit(
        self,
        conn: sqlite3.Connection,
        item_type: str,
        item_id: str,
        reason: str,
        priority: str,
        now: str,
    ) -> None:
        existing = conn.execute(
            """
            SELECT id FROM audit_queue
            WHERE item_type = ? AND item_id = ? AND reason = ? AND status = 'queued'
            """,
            (item_type, item_id, reason),
        ).fetchone()
        if existing:
            return
        conn.execute(
            """
            INSERT INTO audit_queue(id, item_type, item_id, reason, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'queued', ?)
            """,
            (str(uuid.uuid4()), item_type, item_id, reason, priority, now),
        )

    def _resolve_audits(
        self, conn: sqlite3.Connection, item_type: str, item_id: str, now: str
    ) -> None:
        conn.execute(
            """
            UPDATE audit_queue
            SET status = 'resolved', resolved_at = ?
            WHERE item_type = ? AND item_id = ? AND status IN ('queued', 'deferred')
            """,
            (now, item_type, item_id),
        )

    def _require_memory(self, conn: sqlite3.Connection, memory_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown memory: {memory_id}")
        return row

    def _require_domain(self, conn: sqlite3.Connection, domain: str) -> None:
        row = conn.execute(
            "SELECT name FROM domains WHERE name = ? AND active = 1", (domain,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown or inactive domain: {domain}")

    def _require_memory_type(self, conn: sqlite3.Connection, memory_type: str) -> None:
        row = conn.execute(
            "SELECT name FROM memory_types WHERE name = ?", (memory_type,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown memory type: {memory_type}")

    def _set_state(self, conn: sqlite3.Connection, key: str, value: str, now: str) -> None:
        conn.execute(
            """
            INSERT INTO engine_state(key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    @staticmethod
    def _validate_score(name: str, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0")

    @staticmethod
    def _validate_source_type(source_type: str) -> None:
        if source_type not in SOURCE_RANK:
            raise ValueError(f"unsupported source type: {source_type}")
