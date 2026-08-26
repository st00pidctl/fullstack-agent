PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS domains (
    name TEXT PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_types (
    name TEXT PRIMARY KEY,
    review_after_days INTEGER,
    decay_enabled INTEGER NOT NULL DEFAULT 0 CHECK (decay_enabled IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'verified', 'disputed', 'superseded', 'rejected')),
    primary_domain TEXT,
    domain_confidence REAL CHECK (domain_confidence IS NULL OR (domain_confidence >= 0.0 AND domain_confidence <= 1.0)),
    domain_verified INTEGER NOT NULL DEFAULT 0 CHECK (domain_verified IN (0, 1)),
    memory_type TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    relevance REAL NOT NULL DEFAULT 0.5 CHECK (relevance >= 0.0 AND relevance <= 1.0),
    freshness REAL NOT NULL DEFAULT 1.0 CHECK (freshness >= 0.0 AND freshness <= 1.0),
    source_type TEXT NOT NULL CHECK (source_type IN ('user_correction', 'user_explicit', 'tool_observation', 'verified_memory', 'strong_inference', 'weak_inference')),
    source_ref TEXT,
    source_timestamp TEXT,
    user_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (user_confirmed IN (0, 1)),
    impact TEXT NOT NULL DEFAULT 'normal' CHECK (impact IN ('low', 'normal', 'high')),
    likely_action_driver INTEGER NOT NULL DEFAULT 0 CHECK (likely_action_driver IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT,
    last_validated_at TEXT,
    supersedes_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (primary_domain) REFERENCES domains(name),
    FOREIGN KEY (memory_type) REFERENCES memory_types(name),
    FOREIGN KEY (supersedes_id) REFERENCES memories(id),
    CHECK (status = 'candidate' OR primary_domain IS NOT NULL),
    CHECK (status != 'verified' OR (primary_domain IS NOT NULL AND domain_verified = 1))
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    stance TEXT NOT NULL CHECK (stance IN ('supports', 'contradicts')),
    source_type TEXT NOT NULL CHECK (source_type IN ('user_correction', 'user_explicit', 'tool_observation', 'verified_memory', 'strong_inference', 'weak_inference')),
    source_ref TEXT,
    observed_at TEXT NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    note TEXT,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    from_memory_id TEXT NOT NULL,
    to_memory_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('inferred', 'verified', 'disputed', 'rejected')),
    primary_domain TEXT NOT NULL,
    domain_confidence REAL CHECK (domain_confidence IS NULL OR (domain_confidence >= 0.0 AND domain_confidence <= 1.0)),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (from_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (to_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (primary_domain) REFERENCES domains(name),
    CHECK (from_memory_id != to_memory_id)
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
    id TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL,
    stance TEXT NOT NULL CHECK (stance IN ('supports', 'contradicts')),
    source_type TEXT NOT NULL CHECK (source_type IN ('user_correction', 'user_explicit', 'tool_observation', 'verified_memory', 'strong_inference', 'weak_inference')),
    source_ref TEXT,
    observed_at TEXT NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    note TEXT,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_queue (
    id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL CHECK (item_type IN ('memory', 'relationship', 'domain_assignment')),
    item_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('normal', 'high')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'resolved', 'deferred')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE (item_type, item_id, reason, status)
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id TEXT PRIMARY KEY,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('weekly', 'quantity', 'high_impact_quantity', 'point_of_use', 'manual')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS engine_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(primary_domain);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_evidence_memory ON evidence(memory_id);
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_memory_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_memory_id);
CREATE INDEX IF NOT EXISTS idx_relationships_status ON relationships(status);
CREATE INDEX IF NOT EXISTS idx_audit_queue_status ON audit_queue(status);
