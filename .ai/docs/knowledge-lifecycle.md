# Knowledge lifecycle

1. Register source metadata in sources/ without copying sensitive source contents.
2. Capture evidence with actor, method, time and a precise source location.
3. Write atomic claims with provenance. Extraction and LLM output do not confirm them.
4. Record uncertainty as UNKNOWN, INFERRED or NEEDS_HUMAN_CONFIRMATION.
5. A reviewer assesses whether direct evidence actually substantiates each statement.
6. Only then set CONFIRMED, evidence links and last_verified.
7. Run validate for structural and explicit invariant checks; it does not prove truth.
8. Reverify when sources or requirements change. Retain superseded/retracted evidence.
9. Resolve conflicts through a separate documented human decision, never by validation.

Claim depends_on edges are directed and must be acyclic. Self-dependencies are
invalid. conflicts_with links must be symmetric and cannot reference the same
claim. Cycles of conflicts are allowed. A valid unresolved conflict is reported
with both claim IDs and file locations, without changing either claim.

Relationship records optionally document depends_on or conflicts_with edges
between claim IDs. They must agree with claim arrays, cannot be self-edges,
and cannot duplicate an edge (including reversed conflict edges). Claim arrays
remain mandatory; a relationship record never silently adds an edge.

Substantive decisions, explanations and cross-session memory belong in knowledge/.
state/ is for operational metadata only. generated/ is disposable. The CLI does
not infer semantic directory misuse from arbitrary Markdown or JSON text.
