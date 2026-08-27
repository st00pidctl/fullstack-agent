#!/usr/bin/env python3
"""Deterministic live-turn bridge for the portable memory graph.

This module is intentionally provider-neutral. Backtalk or any future shell calls
pre_turn() before invoking a reasoning core and post_turn() after it returns.
The reasoning provider never owns durable memory.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from memory_engine import MemoryEngine

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "memory" / "memory.db"
SCHEMA = ROOT / "memory" / "schema.sql"
DEFAULT_DOMAINS = ("CTS", "GHV", "GS Tech", "IQVIA", "Personal", "Homelab")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,}")

DOMAIN_HINTS = {
    "CTS": ("cts", "cassady tech", "cassady tech solutions"),
    "GHV": ("ghv", "greenhorn valley tech", "greenhorn"),
    "GS Tech": ("gs tech", "gstek"),
    "IQVIA": ("iqvia",),
    "Homelab": ("homelab", "proxmox", "pve", "jellyfin", "tailscale", "vm", "server"),
    "Personal": ("personal", "family", "home", "wife", "son", "daughter"),
}

HIGH_IMPACT_TERMS = (
    "password", "credential", "delete", "remove", "deploy", "publish", "merge",
    "purchase", "pay", "invoice", "deadline", "contract", "security", "production",
)

@dataclass(frozen=True)
class TurnContext:
    prompt_context: str
    domain: str | None
    domain_confidence: float
    verified_memory_ids: tuple[str, ...]
    blocked_memory_ids: tuple[str, ...]
    clarification: str | None
    audit_due: bool

    def as_dict(self) -> dict:
        return {
            "prompt_context": self.prompt_context,
            "domain": self.domain,
            "domain_confidence": self.domain_confidence,
            "verified_memory_ids": list(self.verified_memory_ids),
            "blocked_memory_ids": list(self.blocked_memory_ids),
            "clarification": self.clarification,
            "audit_due": self.audit_due,
        }


def engine(db_path: str | Path | None = None) -> MemoryEngine:
    eng = MemoryEngine(db_path or DEFAULT_DB, SCHEMA)
    eng.initialize()
    for domain in DEFAULT_DOMAINS:
        eng.add_domain(domain)
    return eng


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in TOKEN_RE.finditer(text)}


def classify_domain(text: str) -> tuple[str | None, float]:
    lower = text.lower()
    scored: list[tuple[int, str]] = []
    for domain, hints in DOMAIN_HINTS.items():
        score = sum(1 for hint in hints if hint in lower)
        if score:
            scored.append((score, domain))
    if not scored:
        return None, 0.0
    scored.sort(reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] == best_score:
        return None, 0.45
    return best, min(1.0, 0.75 + 0.1 * (best_score - 1))


def _candidate_rows(eng: MemoryEngine, utterance: str, domain: str | None, limit: int = 12):
    query_tokens = _tokens(utterance)
    if not query_tokens:
        return []
    with eng.connect() as conn:
        rows = conn.execute(
            """SELECT id, claim, status, primary_domain, domain_verified, confidence,
                      relevance, freshness, impact, likely_action_driver, memory_type
               FROM memories
               WHERE status IN ('verified','candidate','disputed')
                 AND status != 'superseded'
               ORDER BY updated_at DESC LIMIT 250"""
        ).fetchall()
    ranked = []
    for row in rows:
        overlap = len(query_tokens & _tokens(row["claim"]))
        if not overlap:
            continue
        domain_bonus = 2 if domain and row["primary_domain"] == domain else 0
        score = overlap * 4 + domain_bonus + float(row["relevance"])
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in ranked[:limit]]


def pre_turn(utterance: str, db_path: str | Path | None = None) -> TurnContext:
    eng = engine(db_path)
    domain, domain_confidence = classify_domain(utterance)
    rows = _candidate_rows(eng, utterance, domain)
    verified, blocked = [], []
    for row in rows:
        gate = eng.point_of_use_gate([row["id"]])
        if gate.allowed:
            verified.append(row)
        else:
            blocked.append(row)

    lines = [
        "PORTABLE MEMORY CONTEXT (shell-owned, evidence-gated):",
        f"Primary domain for this turn: {domain or 'UNRESOLVED'} (confidence {domain_confidence:.2f}).",
        "Treat only VERIFIED items below as durable facts. Never promote inference by repetition.",
    ]
    if verified:
        lines.append("VERIFIED RELEVANT MEMORY:")
        for row in verified[:8]:
            lines.append(f"- [{row['id']}] ({row['primary_domain']}) {row['claim']}")
    else:
        lines.append("VERIFIED RELEVANT MEMORY: none retrieved.")

    clarification = None
    if blocked:
        lines.append("UNVERIFIED/DISPUTED MEMORY: do not rely on these claims without user confirmation.")
        for row in blocked[:5]:
            lines.append(f"- [{row['id']}] {row['claim']}")
        clarification = "Relevant memory exists but is not verified. Confirm it before relying on it."

    if domain is None:
        lines.append("DOMAIN RULE: durable memory from this turn must remain candidate until one primary domain is resolved.")

    audit = eng.audit_due()
    if audit.get("due"):
        lines.append("MEMORY AUDIT DUE: surface this naturally when it will not derail an urgent task.")

    return TurnContext(
        prompt_context="\n".join(lines),
        domain=domain,
        domain_confidence=domain_confidence,
        verified_memory_ids=tuple(row["id"] for row in verified),
        blocked_memory_ids=tuple(row["id"] for row in blocked),
        clarification=clarification,
        audit_due=bool(audit.get("due")),
    )


def _atomic_user_claims(utterance: str) -> list[str]:
    """Conservative extraction of explicit first-person durable statements.

    This is deliberately precision-biased. Richer model-assisted extraction can be
    added later, but ambiguous text must not silently become fact.
    """
    text = " ".join(utterance.strip().split())
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    durable = []
    markers = (
        "i want ", "i need ", "i prefer ", "i use ", "i have ", "i am ", "i'm ",
        "we use ", "we have ", "we are ", "my ", "our ", "the decision is ",
    )
    for sentence in sentences:
        lower = sentence.lower().strip()
        if len(sentence) < 8 or len(sentence) > 500:
            continue
        if any(marker in lower for marker in markers):
            durable.append(sentence.strip())
    return durable[:6]


def post_turn(utterance: str, response: str, db_path: str | Path | None = None) -> dict:
    eng = engine(db_path)
    domain, domain_confidence = classify_domain(utterance)
    claims = _atomic_user_claims(utterance)
    created = []
    immediate_review = []
    lower = utterance.lower()
    high_impact = any(term in lower for term in HIGH_IMPACT_TERMS)

    for claim in claims:
        memory_type = "preference" if any(x in claim.lower() for x in ("i want", "i prefer", "i need")) else "stable_fact"
        memory_id = eng.add_candidate(
            claim,
            memory_type=memory_type,
            confidence=0.72,
            source_type="user_explicit",
            primary_domain=domain,
            domain_confidence=domain_confidence if domain else None,
            domain_verified=False,
            source_ref="live_turn:user",
            relevance=0.65,
            freshness=1.0,
            impact="high" if high_impact else "normal",
            likely_action_driver=high_impact,
            metadata={"capture": "live_turn", "assistant_response_present": bool(response.strip())},
        )
        created.append(memory_id)
        if high_impact or domain is None:
            immediate_review.append(memory_id)

    audit = eng.audit_due()
    return {
        "created_memory_ids": created,
        "immediate_review_ids": immediate_review,
        "domain": domain,
        "domain_confidence": domain_confidence,
        "audit": audit,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pre", "post"))
    parser.add_argument("--utterance", required=True)
    parser.add_argument("--response", default="")
    parser.add_argument("--db")
    args = parser.parse_args()
    result = pre_turn(args.utterance, args.db).as_dict() if args.mode == "pre" else post_turn(args.utterance, args.response, args.db)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
