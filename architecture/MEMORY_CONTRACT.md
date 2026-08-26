# Evidence Based Memory Contract

This document defines the shell owned memory behavior for the universal agent.

## Purpose

Memory exists to provide continuity without allowing an assumption, inference, stale fact, or provider session artifact to silently become truth.

The shell owns memory. Cores consume memory through a controlled retrieval interface. Provider sessions are disposable.

## Canonical unit

The canonical durable unit is an atomic claim.

Conversation summaries, transcripts, files, tool outputs, and other rich context are evidence or supporting context. They are not canonical facts by themselves.

A claim should express one independently correctable proposition.

## Memory lifecycle

A claim moves through explicit states:

- `candidate`: observed or proposed, but not trusted as verified truth
- `verified`: explicitly accepted or supported strongly enough by allowed evidence policy
- `disputed`: conflicting evidence exists and the conflict is unresolved
- `superseded`: a newer claim replaces this claim while preserving history
- `rejected`: reviewed and intentionally not accepted

Corrections are append only by default. A corrected claim creates a new record and marks the prior claim as superseded or disputed. Physical deletion is reserved for an explicit forget or delete request.

## Separate scores

Do not collapse uncertainty into one score.

Each claim tracks at least:

- confidence: strength of evidence supporting the claim
- relevance: usefulness to the current context
- freshness: likelihood that the claim is still current
- domain confidence: confidence in the domain classification, separate from truth confidence

Relationships have their own confidence and verification state.

Graph density must never substitute for evidence. Multiple uncertain claims pointing at one another do not become truth through repetition.

## Evidence and provenance

Every claim must retain provenance sufficient to answer: `Why do you believe this?`

Evidence records should identify source type, source reference when available, timestamp, whether the evidence supports or contradicts the claim, and any explanatory note.

Source precedence is ordered as follows:

1. explicit user correction
2. explicit user statement
3. directly observed tool or file evidence
4. previously verified memory
5. strong inference
6. weak inference

Precedence is not a license to ignore recency or contradiction. A newer explicit statement can supersede older verified information while the old history remains available.

## Domain assignment

Every verified durable claim has exactly one primary domain.

Every stored relationship also has exactly one primary domain.

No generic `other` domain exists as an escape hatch. If the primary domain cannot be assigned confidently, the claim remains a candidate and is queued for clarification or audit.

Cross domain meaning is represented through relationships, not multiple primary domains.

The set of valid domains is explicit configuration. The memory engine must not invent a new domain silently.

## Inferred relationships

The agent may create inferred relationships automatically when a primary domain is assigned.

Examples include:

- related project or client
- likely contradiction
- preference pattern
- person to project association
- possible causal or explanatory relationship

Every inferred relationship:

- is marked `inferred`
- carries its own confidence and evidence
- is included in audits
- cannot become verified merely because more inferred relationships point to it

User confirmation may promote an inferred relationship to verified.

## Dual verification triggers

Verification is both creation time and point of use.

### Creation time trigger

Ask immediately when a candidate is:

- high impact
- ambiguous
- contradictory
- likely to drive a future action
- domain ambiguous

Low impact non urgent candidates may be queued without interrupting the conversation.

### Point of use trigger

Queued does not mean trusted.

Before an important answer, recommendation, plan, or action relies on an unverified, disputed, stale, domain ambiguous, or contradictory claim, the agent must stop and request clarification.

## Memory audits

Audits are event driven and periodic.

An audit is due when any of these conditions is met:

- one week has passed since the previous periodic audit
- unresolved candidate count reaches 20
- high impact or contradictory unresolved item count reaches 5
- a point of use gate requires verification

Audits include candidate claims, disputed claims, stale claims, domain assignments needing review, and inferred relationships.

An audit should expose the claim or relationship, current state, confidence, domain, evidence trail, contradiction state, and the action available to the user: confirm, correct, reject, reclassify, defer, or delete.

## Freshness and type aware decay

Confidence that a statement was once made is different from confidence that it is still current.

Memory types therefore carry configurable freshness review or decay policy. Stable facts may have little or no decay. Project status, system configuration, schedules, pricing, and other current state may require faster review.

The framework must support type specific policies, but concrete decay intervals are configuration, not assumptions embedded in the engine.

## Action safety

Memory retrieval may provide uncertain context to a core, but consequential action must use a memory gate.

The gate must report whether all required claims are sufficiently verified for the requested use. If not, it returns the reasons and the unresolved memory IDs rather than silently proceeding.

## Non goals for this phase

This contract does not select a future model or core. Codex remains the active core while memory is made shell owned and portable.

This contract does not require Neo4j, a vector database, or another external service. SQLite is sufficient for the first implementation and preserves portability.