# Evidence and confidence

Every evidence record has source, description, actor/method provenance,
captured_at and an explicit substantiates array of claim IDs. This v1 refinement
makes the evidence-to-claim relationship inspectable. source and location accept
either a nonblank string or an object with a nonblank reference field.
Optional content_hash uses sha256: followed by 64 lowercase hexadecimal digits.

CONFIRMED requires last_verified and at least one referenced, structurally valid
evidence record that is active, has an appropriate direct type, has a nonempty
location, and explicitly lists the claim in substantiates.
All references must resolve, including references in inactive evidence.

- business_rule: direct-authoritative evidence is required.
- technical_fact: direct-technical or direct-authoritative evidence is allowed.
- architecture: either direct type is allowed, but interpretation stays INFERRED
  unless a reviewer finds direct support for the architectural assertion.
- supporting and derived evidence never independently confirm a claim.

An authorized human's explicit confirmation is recorded as direct-authoritative
evidence: source identifies the approval record and authority, provenance.actor
identifies the approver, provenance.method describes approval, location identifies
the specific decision, and substantiates lists the approved claim. The validator
cannot authenticate a human or establish their authority.

Inactive evidence is retained for audit. It does not invalidate a claim that has
another acceptable active direct basis. Evidence age alone never changes status.
No source files are scanned, hashes recalculated, URLs fetched or authority
registries consulted. content_hash is checked for syntax only.
Validation always reports that truth, authority and freshness require review.
These structural indicators do not prove that a source supports arbitrary prose.
