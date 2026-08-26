#!/usr/bin/env python3
"""Operator CLI for the shell owned memory graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from memory_engine import MemoryEngine


DEFAULT_DB = Path.home() / "universal-agent" / "memory" / "memory.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the universal agent memory graph")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the memory database")

    domain = sub.add_parser("domain", help="Manage explicit memory domains")
    domain_sub = domain.add_subparsers(dest="domain_command", required=True)
    domain_add = domain_sub.add_parser("add")
    domain_add.add_argument("name")
    domain_sub.add_parser("list")

    add = sub.add_parser("add", help="Add an atomic candidate claim")
    add.add_argument("claim")
    add.add_argument("--type", required=True, dest="memory_type")
    add.add_argument("--confidence", type=float, required=True)
    add.add_argument("--source", required=True, dest="source_type")
    add.add_argument("--source-ref")
    add.add_argument("--domain")
    add.add_argument("--domain-confidence", type=float)
    add.add_argument("--domain-verified", action="store_true")
    add.add_argument("--relevance", type=float, default=0.5)
    add.add_argument("--freshness", type=float, default=1.0)
    add.add_argument("--impact", choices=("low", "normal", "high"), default="normal")
    add.add_argument("--action-driver", action="store_true")
    add.add_argument("--contradiction", action="store_true")

    show = sub.add_parser("show", help="Show a claim and its evidence")
    show.add_argument("memory_id")

    verify = sub.add_parser("verify", help="Verify a candidate claim")
    verify.add_argument("memory_id")
    verify.add_argument("--domain")

    reject = sub.add_parser("reject", help="Reject a candidate claim")
    reject.add_argument("memory_id")

    correct = sub.add_parser("correct", help="Append a correction and supersede the old claim")
    correct.add_argument("memory_id")
    correct.add_argument("new_claim")
    correct.add_argument("--domain")
    correct.add_argument("--type", dest="memory_type")
    correct.add_argument("--source-ref")

    evidence = sub.add_parser("evidence", help="Attach evidence to a claim")
    evidence.add_argument("memory_id")
    evidence.add_argument("--stance", choices=("supports", "contradicts"), required=True)
    evidence.add_argument("--source", required=True, dest="source_type")
    evidence.add_argument("--source-ref")
    evidence.add_argument("--confidence", type=float)
    evidence.add_argument("--note")

    relate = sub.add_parser("relate", help="Create a graph relationship")
    relate.add_argument("from_memory_id")
    relate.add_argument("to_memory_id")
    relate.add_argument("relation_type")
    relate.add_argument("--domain", required=True)
    relate.add_argument("--confidence", type=float, required=True)
    relate.add_argument("--domain-confidence", type=float)
    relate.add_argument("--verified", action="store_true")

    verify_rel = sub.add_parser("verify-relationship", help="Verify an inferred relationship")
    verify_rel.add_argument("relationship_id")

    delete = sub.add_parser("delete", help="Physically delete a memory after an explicit forget request")
    delete.add_argument("memory_id")
    delete.add_argument("--explicit", action="store_true", required=True)

    gate = sub.add_parser("gate", help="Check whether memories are safe to rely on")
    gate.add_argument("memory_ids", nargs="+")

    audit = sub.add_parser("audit", help="Inspect and manage audit state")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)
    audit_sub.add_parser("status")
    audit_sub.add_parser("list")
    begin = audit_sub.add_parser("begin")
    begin.add_argument(
        "trigger",
        choices=("weekly", "quantity", "high_impact_quantity", "point_of_use", "manual"),
    )
    complete = audit_sub.add_parser("complete")
    complete.add_argument("audit_id")
    complete.add_argument("--notes")

    policy = sub.add_parser("freshness-policy", help="Configure type specific staleness review")
    policy.add_argument("memory_type")
    policy.add_argument("--days", type=int)
    policy.add_argument("--disable", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    engine = MemoryEngine(args.db)

    if args.command == "init":
        engine.initialize()
        print(json.dumps({"initialized": str(Path(args.db).expanduser())}, indent=2))
        return 0

    if args.command == "domain":
        if args.domain_command == "add":
            engine.add_domain(args.name)
            print(json.dumps({"domain_added": args.name}, indent=2))
        else:
            print(json.dumps({"domains": engine.list_domains()}, indent=2))
        return 0

    if args.command == "add":
        memory_id = engine.add_candidate(
            args.claim,
            memory_type=args.memory_type,
            confidence=args.confidence,
            source_type=args.source_type,
            source_ref=args.source_ref,
            primary_domain=args.domain,
            domain_confidence=args.domain_confidence,
            domain_verified=args.domain_verified,
            relevance=args.relevance,
            freshness=args.freshness,
            impact=args.impact,
            likely_action_driver=args.action_driver,
            contradiction=args.contradiction,
        )
        print(json.dumps({"memory_id": memory_id}, indent=2))
        return 0

    if args.command == "show":
        print(json.dumps(engine.get_memory(args.memory_id), indent=2, sort_keys=True))
        return 0

    if args.command == "verify":
        engine.verify_memory(args.memory_id, primary_domain=args.domain)
        print(json.dumps({"verified": args.memory_id}, indent=2))
        return 0

    if args.command == "reject":
        engine.reject_memory(args.memory_id)
        print(json.dumps({"rejected": args.memory_id}, indent=2))
        return 0

    if args.command == "correct":
        new_id = engine.supersede_memory(
            args.memory_id,
            args.new_claim,
            memory_type=args.memory_type,
            primary_domain=args.domain,
            source_ref=args.source_ref,
        )
        print(json.dumps({"superseded": args.memory_id, "replacement": new_id}, indent=2))
        return 0

    if args.command == "evidence":
        evidence_id = engine.add_evidence(
            args.memory_id,
            stance=args.stance,
            source_type=args.source_type,
            source_ref=args.source_ref,
            confidence=args.confidence,
            note=args.note,
        )
        print(json.dumps({"evidence_id": evidence_id}, indent=2))
        return 0

    if args.command == "relate":
        relationship_id = engine.add_relationship(
            args.from_memory_id,
            args.to_memory_id,
            args.relation_type,
            primary_domain=args.domain,
            confidence=args.confidence,
            domain_confidence=args.domain_confidence,
            inferred=not args.verified,
        )
        print(json.dumps({"relationship_id": relationship_id}, indent=2))
        return 0

    if args.command == "verify-relationship":
        engine.verify_relationship(args.relationship_id)
        print(json.dumps({"verified_relationship": args.relationship_id}, indent=2))
        return 0

    if args.command == "delete":
        engine.delete_memory(args.memory_id, explicit=args.explicit)
        print(json.dumps({"deleted": args.memory_id}, indent=2))
        return 0

    if args.command == "gate":
        result = engine.point_of_use_gate(args.memory_ids)
        print(json.dumps(result.as_dict(), indent=2))
        return 0 if result.allowed else 2

    if args.command == "audit":
        if args.audit_command == "status":
            print(json.dumps(engine.audit_due(), indent=2))
        elif args.audit_command == "list":
            print(json.dumps(engine.list_audit_items(), indent=2))
        elif args.audit_command == "begin":
            print(json.dumps({"audit_id": engine.begin_audit(args.trigger)}, indent=2))
        elif args.audit_command == "complete":
            engine.complete_audit(args.audit_id, args.notes)
            print(json.dumps({"completed": args.audit_id}, indent=2))
        return 0

    if args.command == "freshness-policy":
        days = None if args.disable else args.days
        if not args.disable and days is None:
            raise SystemExit("provide --days N or --disable")
        engine.configure_memory_type(args.memory_type, days)
        print(json.dumps({"memory_type": args.memory_type, "review_after_days": days}, indent=2))
        return 0

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
