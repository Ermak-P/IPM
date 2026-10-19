# Stage 3.1 — Existing knowledge compatibility assessment

**Decision:** existing-project source discovery/extraction is usable within the
current safety boundary. Generic integration or migration using the current
`init` is **NO-GO**. Stage 3.2 implementation remains **NO-GO pending review of
this assessment and explicit approval of its bounded scope**.

This is a design/assessment, not an installer change, migration, canonical
population or new architecture capability. Contract v1.0, pinned canonical
schemas, validator, Stage 2 implementations and canonical knowledge are unchanged.
All example knowledge is fictional. No corporate repository data was used.

## 1. Baseline, inspection and executed verification

Repository Ermak-P/IPM, branch `work`, baseline
`e530a374bbdbf5ccd42dc67adbd260225c5c6dc3`. Initial git status was clean.
Environment: Linux x86_64, Python 3.12.14, existing pinned .NET SDK 10.0.402;
.NET runtime 10.0.13. Native Windows/NTFS was unavailable and is not accepted
by this assessment; the existing Stage 2 Windows gate remains open.

Inspected: contract-v1.md, knowledge-lifecycle.md, evidence-and-confidence.md,
manifest, all three schemas; kb.py installer/path checks/schema and dataset
validator; normalization, population coordination/snapshot protocol, GraphBuilder
and graph semantics documentation; existing installer/population/graph tests.
No additional Graph Builder is needed or proposed.

| Actual command / probe | Exit | Executed result |
| --- | ---: | --- |
| git rev-parse HEAD; git status --short (separate commands) | 0 | Exact baseline above, clean |
| python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py' | 0 | 209 passed; 0 failures/errors/skips |
| dotnet vstest tests/SyntheticIpm.UnitTests/bin/Debug/net10.0/SyntheticIpm.UnitTests.dll tests/SyntheticIpm.IntegrationTests/bin/Debug/net10.0/SyntheticIpm.IntegrationTests.dll --ResultsDirectory:/tmp/ipm-stage31-dotnet | 0 | 27 passed: 12 unit + 15 integration, 0 failed/skipped |
| python -B .ai/tools/kb.py validate --json | 0 | Valid existing canonical store |
| python -B .ai/tools/kb.py check-scaffold --json | 0 | Existing scaffold complete |
| python -B .ai/tools/kb.py version --json | 0 | CLI 1.0.0, format 1.0.0 |
| python -B /tmp/stage31_probe.py > /tmp/ipm-stage31-probes.json (final harness) | 0 | Seven installer cases, two dataset validations, five source/canonical-operation cases, five legacy schema rejections; hash assertions passed |
| git diff --check | 0 | No tracked whitespace errors |

`dotnet` here is `/workspace/.ipm-tools/dotnet/dotnet`, with
DOTNET_ROOT=/workspace/.ipm-tools/dotnet,
DOTNET_CLI_HOME=/workspace/.ipm-tools/cli-home,
DOTNET_CLI_TELEMETRY_OPTOUT=1 and TESTINGPLATFORM_TELEMETRY_OPTOUT=1.
Existing compiled Linux test DLLs were used; no build/restore was needed.
The temporary probe harness had a text-edit error during extension of the
schema-check section; that harness run failed before writing results. The harness
was corrected, rerun in fresh disposable roots, and all final assertions passed.
This was not a product defect and no implementation fix was made.

## 2. Synthetic existing project

Fixture: tools/examples/existing-knowledge/fixture.json, with a companion README.
It is a bundle of 19 root-relative UTF-8 file contents, materialized only under
unique temporary directories. It is test data, never a second canonical store.

The fictional Harbor Tickets project has business concepts Ticket/Closure,
RULE/17 (business policy), ARCH/4 (component responsibility), EV/17 (meeting note),
EV/18 (withdrawn source evidence), a domain glossary, ADR-017, component-level
`calls` relationships, a custom manifest/schema and project-owned graph-tool
entrypoint/contract/output. Deliberately problematic examples include missing
capture/verification details, invalid v1 IDs, a confidence number without a v1
meaning, enduring notes under generated/ and a durable decision under state/.
A synthetic .csproj supplies exactly two source observations: project existence
and a literal TargetFramework declaration.

The bundled tools/knowledge_graph.py is an **inert ownership sentinel** at a
conflicting path. The existing-tool contract describes an already owned legacy
builder; its implementation is deliberately omitted and was never imported or
executed. The fixture exercises installer/ownership collisions, not correctness
of an invented legacy graph algorithm. No new/competing Graph Builder was
implemented. Actual compatibility with a host's real builder contract remains
a Stage 3.2 test requirement, not a passed result here.

## 3. Installer assessment: preservation is not integration

Current `init` requires the exact JSON-compatible manifest object, not simply a
matching version string. A nonempty foreign `.ai` without that manifest is
rejected. On a recognized manifest it checks directory types and occupied
installer-template paths; differing files are preserved and cause rejection
before normal template writes. Linked paths are rejected by current path checks.
It creates missing directories/files using mkdir/exclusive file creation; it
never intentionally replaces existing content.

However, `init` is a scaffold installer, not a schema/ownership migration planner:

- It does not validate existing canonical record content before filling missing
  scaffold files. `validate` is a separate operation.
- It does not identify equivalent project-owned tools at different paths, or
  negotiate ownership/responsibilities with an existing graph pipeline.
- A recognized manifest does not authorize taking over README, tools, schema,
  generated/ or state/. Identical template bytes do not establish ownership.
- It has no integration dry-run, ownership map, selective component installation,
  adoption receipt or transactional rollback of all newly created scaffold files.
  Population's separate transaction protocol does not make `init` transactional.
- Unexpected I/O failure/concurrency during installation may leave some new
  scaffold files. Do not claim whole-tree atomicity or protection against hostile
  same-user ancestor swaps from the ordinary preflight checks.

In the disposable probes, exact bytes of every pre-existing file were checked
before/after. NO-GO is about absent integration semantics, not observed overwrite.
Do not forge/replace the legacy manifest, schema, README or tool to force `init`
through these guards.

## 4. Ownership and schema mapping matrix

The existing project owns every pre-existing file until its owner explicitly
agrees otherwise. The universal framework owns its externally distributed code
and v1 contract; those do not confer ownership of a host path.

| Existing resource / schema | v1 meaning or boundary | Automatic assessment permitted | Human decision / integration rule |
| --- | --- | --- | --- |
| .ai/manifest.yaml, custom format/revision/owners | Pinned universal manifest differs | Parse recognized safe data; compare exact values | Preserve foreign manifest; no replacement or extra capability flags. Choose non-installing mode or later explicitly reviewed adoption |
| README.md, docs and custom schema | Existing team documentation/schema authority | Inventory hashes/paths; compare candidate schemas without writing | No template takeover; retain original schema. v1 validation uses pinned schema only in isolated temporary context |
| business/concepts.yaml; domain Markdown | v1 has business_rule claims plus unstructured domain prose, not a concept registry schema | Inventory/reference existing documents; do not NLP-extract rules | Keep prose/concepts authoritative in original paths. A concept is not automatically a business rule; authors define any atomic assertion |
| Claim id RULE/17 or ARCH/4 | v1 IDs match ^[A-Za-z][A-Za-z0-9._:-]*$; global uniqueness across groups | Report invalid ID and exact references | Slash IDs cannot be retained as v1 IDs. Do not escape/rename silently; propose explicit old→new mapping only after owner decisions, no writes in 3.1 |
| kind business-policy + text | Potential business_rule + statement | Report field/type candidate mapping | Confirm semantic equivalence/atomicity; retain original data and extra tags in its owner format, never silently drop fields |
| kind component-responsibility | Potential architecture claim | Identify incompatibility | Names or component edges do not establish architectural intent; require direct evidence and reviewer judgment |
| state approved/verified | Not automatically CONFIRMED | Enumerate lifecycle labels and required missing fields | Review approval scope/authority and verification event. No invented last_verified or historical approval; conservative proposed statuses require explicit semantic mapping |
| Unknown legacy state or confidence=0.9 | No supported v1 numeric confidence field | Report unsupported field/meaning | Do not translate a score into status or discard it invisibly. Preserve in legacy source; no canonical schema extension |
| support ['EV/17'] | Claim evidence IDs; evidence must explicitly substantiate claim | Trace candidate references/dangling IDs | Citation is not an asserted substantiation link. Add one only when direct source/reviewer establishes it, not from adjacency alone |
| EV/17 meeting-note/current | Could be supporting/active; not inherently direct-authoritative | Show candidate fields and missing provenance/time/location | Reviewer identifies the actual source authority, actor, capture event and location. An accepted ADR heading is not authenticated approval |
| EV/18 source-code/withdrawn | Potential direct-technical only for narrow declared facts; withdrawn may mean retracted | Report semantic/status mismatch | Withdrawn semantics require owner agreement; never reactivate. Source structure cannot confirm business rules or architecture intent |
| uri, excerpt_ref, observed_on date-only/unknown | v1 source, location, captured_at with timezone, provenance actor/method, description, substantiates; hash optional | Check known path syntax, missing values and field shapes | Resolve URI base/context explicitly; no fetching, date-at-midnight fabrication or invented actor/verification timestamp |
| content hash absent/old | Optional sha256 syntax; observation identity != content hash | Report absence/staleness only where safely observable | New capture time reflects actual observation, not prior review. Preserve human evidence timestamps; no automatic refresh writes |
| Relationship component calls / conditional | v1 only claim-level depends_on and conflicts_with | Report unsupported subject/type/condition | Do not relabel as depends_on. Keep original edge with owner builder; optional nonauthoritative views must retain declared/conditional semantics |
| Valid v1 claims/evidence/relationships already present | Can be reused in place, validated without schema conversion | Validate pinned structures and explicit invariants, detect globally duplicate IDs | Preserve IDs/status/provenance/dates/dependencies/conflicts byte-for-byte. No ownership transfer from structural validity |
| Decisions/domains/sources Markdown | Project-owned durable context | Inventory/reference | No rewriting, automatic claim extraction or timestamp generation |
| tools/knowledge_graph.py, other graph entrypoints, graph contract | Existing project owns graph construction | Detect occupied paths and declared tool responsibility; inspect data contract only | Exactly one chosen builder per responsibility. Do not install/invoke a competing builder or execute discovered scripts |
| generated/architecture.json, curator-notes.md | Universal generated/ is disposable; legacy directory may not be | Classify outputs provisionally, record hashes | Do not clear legacy generated/. Owner identifies reproducible outputs vs unique knowledge; separate approved output filenames/namespace only later |
| state/team-decisions.md, state/population | Universal state is operational; legacy state may be durable or unrelated | Identify incompatible content/protocol | No cleanup, relocation or interpretation as a universal journal. Unknown/pending recovery protocol is a stop condition |

Strict v1 additionalProperties=false means custom fields cannot be slipped into
canonical claims/evidence/relationships. Relationships must agree with claim
arrays; dependency cycles/self-links and asymmetric conflicts are invalid.
Inactive evidence still needs valid references; it cannot independently confirm
a claim. Business_rule CONFIRMED requires active direct-authoritative evidence
with location and explicit substantiation plus actual last_verified. Technical
and architecture claims have the existing direct-evidence requirements; semantic
truth and approver authority remain outside structural validation.

## 5. Identifier, provenance and lifecycle ownership

A compatible valid ID is retained. Identity comparisons are global across claims,
evidence and relationships, not per filename. Equal IDs with different content
are conflicts; equal text with different IDs is not a safe merge. Include
case-insensitive path aliases, Unicode normalization aliases and root-relative
reference bases in the inventory: filename safety and semantic identity are
separate checks. Filesystem case folding does not authorize case-folding claim IDs.

The current claim.dotnet/evidence.dotnet identifiers are stable deterministic
technical fact IDs, not proof that a matching human-created record belongs to the
extractor. A future inventory must examine exact ID/content/provenance; any
collision, including a human record that happens to use this prefix, is blocked.
No separate persistent ID registry is needed: authoritative source records plus
a reviewed proposal enumerate all mappings and references. Proposed aliases are
review material, never a second source of knowledge.

Legacy evidence must not acquire invented approval/capture/verification events.
A parser may prove that a source declares a string; it cannot prove a meeting
note was authoritative, a person approved an architectural assertion, or an
unknown historical date was a real capture timestamp. Unknowns stay unresolved;
missing provenance/time may make an item unrepresentable as v1 evidence. Keep its
original record, report that limitation and seek a new genuine observation/review
if needed. No downgrade/promotion/reactivation occurs to work around validation.

## 6. Proposed non-destructive integration architecture (not implemented)

### 6.1. Explicit authority and capability tiers

**Tier 0 — unknown/unsafe:** foreign schema/ownership, links, unsupported formats,
conflicting transaction state or unstable inputs. Inventory/diagnostics only;
stop before writing or invoking any host tool.

**Tier 1 — source-only companion:** use a trusted external framework checkout
for existing `scan`/`extract --root <project>` without installing a scaffold.
This is currently usable only when path safety and the existing transaction gate
allow it; a foreign state/population path is not bypassed. The legacy `.ai` stays
excluded, authoritative and untouched. Output is noncanonical source candidates.
Do not call normalize/build/report on a foreign schema and treat failure as
permission to change it. No .ai-imported/, shadow .ai or second canonical store.

**Tier 2 — already v1-native owned knowledge:** after explicit owner agreement,
reuse exact existing v1 records/schema in place and validate with the current
validator. Tooling may remain external; no initializer is necessary for a read
if the required v1 layout is already complete. Host-owned existing graph tooling
remains the selected graph authority. Current installer lacks a selective
ownership-aware integration mode and must not be substituted for that decision.

**Heterogeneous legacy knowledge:** retain the original store as sole authority.
A future adapter may create an in-memory or isolated disposable candidate
projection for compatibility checking. It must be labeled nonauthoritative and
must not feed the current canonical graph as accepted knowledge. Do not keep a
second durable v1 copy synchronized with legacy records. Converting the original
active format, if ever desired, requires a separately approved migration scope;
it is not implicitly authorized by this assessment or read-only Stage 3.2.

### 6.2. Bounded read-only pipeline

1. Inventory all existing `.ai` paths, file types, hashes and declared owners;
   classify known knowledge/schema/tool/output/state roles and unknowns. Never
   execute discovered scripts or follow links outside the allowed root. Compare
   a second fingerprint before returning results; reject observable input races.
2. Detect exact path/content/ID conflicts, unsupported formats and lifecycle/
   graph semantic differences. Inventory classifications are provisional until
   reviewed. Never classify an existing file as disposable based on its path alone.
3. Owners review authority, tool responsibility, reference bases, write locations,
   unresolved records and mapping rules. Approval applies only to the concrete
   fingerprinted compatibility proposal, not to arbitrary later migration.
4. If approved in a future stage, parse only explicitly supported legacy formats
   as data, produce candidate mappings and diagnostics, validate complete
   representable datasets using unmodified v1 validation in an isolated staging
   directory. Unrepresentable evidence/relationships remain original and blocked.
5. Produce a deterministic compatibility report/diff with affected references,
   reasons, blockers and input fingerprints. No canonical writes, source execution
   or status changes. Structural validity must not be described as adopted truth.

The first implementable Stage 3.2 scope should be inventory, capability negotiation
and read-only compatibility proposals. It is not a general migration/apply feature.

### 6.3. Required adapter boundaries

| Boundary | Input/output contract to agree | May automate later | Must not do |
| --- | --- | --- | --- |
| Inventory reader | Approved root, exclusions, safe file descriptors → sorted paths/types/hash/role diagnostics | Deterministic discovery and occupied-path checks | Follow unsafe links, copy secrets/full source, clear generated/state, infer ownership from names |
| Legacy parser | Explicit supported format/limits/version → raw structured legacy records + precise source references | Local data parsing only | Execute YAML object constructors, scripts, MSBuild, plugin hooks or graph tools; fetch schemas/URLs |
| Semantic mapping | Reviewed field/type/status/URI/ID rules → candidate records + unresolved diagnostics | Mechanical mappings only after approved definitions | Infer responsibilities, forge provenance/times, silently drop custom data or merge IDs |
| Validator bridge | Complete candidate/reference closure + pinned v1 schema → isolated existing validator result | Existing structural validation | Patch schemas, weaken evidence requirements or claim truth/authority |
| Existing graph-tool bridge | Owner-declared input/output schema, supported edge meanings, stable IDs and trust labels | Prepare approved input projection or references for the chosen builder | Install another builder, run discovered code without separate authorization, relabel component calls as claim dependencies |
| Review/proposal boundary | Input fingerprints + complete inventory/diff → explicit review decision | Summaries and blocker classification | Interpret generic approval as permission for writes or future regenerated plans |
| Optional later installation wrapper | Exact externally supplied artifacts, owner-approved unused paths, coordinated plan → additions-only receipt | Only after a separate approved scope with rollback tests | Reuse population apply as arbitrary installer/migrator; overwrite existing files |

No adapter is implemented in Stage 3.1. The existing universal GraphBuilder is
retained, not replaced. Where a host builder already serves the same role, select
and adapt to that builder under owner control; keep unused framework graph tooling
outside the host. Distinct canonical and declared technical-preview semantics
remain separate even if the selected builder supports both views. If it cannot
preserve these trust labels, graph integration is blocked. Do not introduce a
second active pipeline merely because output filenames differ.

### 6.4. Write, rollback and recovery boundaries

Assessment and future read-only compatibility checking require no canonical
rollback because they make no canonical changes. Temporary staged projections
are disposable test material, not authority. Until an output location is
explicitly agreed, inventory/proposals go to stdout; do not assume a foreign
`.ai/generated` or `.ai/state` is safe to write.

A separately reviewed future tooling installation may add only approved absent
paths. It needs a before-state hash inventory, exact additions, coordination,
collision-safe creation, journal/receipt and tested interruption behavior. Its
rollback may remove only still-owned, unchanged additions; changed/concurrently
edited paths remain preserved and blocked for review. Original knowledge, tool,
schema, README, metadata, generated notes and state files are never rollback
material. Restoring a snapshot must never silently erase a concurrent human edit.
No such installer transaction exists today or was added here. Existing population
locks/recovery gates must remain respected; a foreign state path is not assumed
to be a valid universal transaction journal.

## 7. Conflicts and risks

| Severity | Risk evidenced or assessed | Required control / disposition |
| --- | --- | --- |
| High | Current init can succeed without existing dataset validity | Pre-install complete compatibility validation; don't infer integration success from init=0 |
| High | Differently named existing builder isn't detected; init adds universal builder | Explicit tool inventory/owner selection; no current automatic install |
| High | Approved/verified business/architecture labels lack v1 confirmation evidence | No status conversion without substantiated approval/verification; preserve unresolved originals |
| High | ID collisions/dangling references, slash IDs, namespace ownership confusion | Global ID/reference inventory and reviewed mapping; block collisions |
| High | Legacy generated/state contains unique knowledge; cleanup would lose data | No cleanup/relocation; explicit ownership and reproducibility review |
| High | Concurrent modifications or interrupted future install | Stable snapshot/recheck, coordination, receipts and owned-addition rollback tests; not present in init |
| Medium | URI bases, missing timezone/capture events, withdrawn semantics ambiguous | Report unrepresentable evidence; no guessed values/reactivation |
| Medium | Component calls versus claim depends_on, numeric confidence differences | Preserve original semantics with chosen builder; unsupported mapping blocks |
| Medium | Custom schemas/fields, YAML variants and Markdown claims | Allowlisted data-only parser scope; no auto schema broadening or prose inference |
| Medium | Windows case aliases/NTFS sharing, links, ACLs and path limits | Native platform tests before platform acceptance; existing Windows gate remains open |
| Medium | Human data mistaken for extractor-owned dotnet IDs | Exact provenance/content comparison; prefix alone never authorizes mutation |

These are integration risks and observed capability limitations, not a reason to
silently repair Stage 2 or bypass existing protections.

## 8. Synthetic integration test plan and measurable criteria

The fixture permits extending tests without corporate data. E=executed in this
assessment; P=planned test for a reviewed Stage 3.2 implementation, not a pass.

| Test | Measurable expected outcome | Status |
| --- | --- | --- |
| Foreign/missing manifest | init exit 1, 0 new files, every old hash identical | E PASS |
| Recognized manifest, occupied README/schema/tool | init exit 1, 0 new files, old hashes identical | E PASS |
| Recognized manifest with invalid existing records | Observe init=0 but validate=1; no pre-existing bytes changed | E PASS (documented limitation, not integration acceptance) |
| Native v1 dataset plus differently named graph tool | Observe init=0/validate=0 and both tool paths; no existing bytes changed | E PASS (ownership detector absent) |
| Foreign .ai source-only vs canonical commands | scan/extract=0, normalize/build/report=1; 2 source candidates; all bytes unchanged | E PASS |
| Legacy business/architecture/evidence/component records | Existing v1 schema rejects all five with concrete missing/invalid/extra field diagnostics | E PASS |
| Native valid record retention | Existing native ID/status/provenance/evidence/document hashes preserved; validate=0 | E PASS |
| Full ownership inventory | Every original file classified or explicitly unknown, SHA-256/root-relative path recorded; no tool execution | E PASS for bundled fixture; P for a new general inventory API |
| Global duplicate IDs across record groups; same/different content | 100% collisions listed, no merge or write; all dependent refs enumerated | P |
| Slash IDs and reviewed alias mapping | Deterministic complete old→candidate ID proposal, all refs accounted for; zero implicit renames | P |
| Lifecycle approved/verified/unknown, withdrawn and missing timestamps | Zero fabricated CONFIRMED/last_verified/captured_at events; blocked evidence explained | P |
| Valid CONFIRMED business rules vs supporting/inactive-only evidence | Existing validator accepts only actual v1-complete cases; no relaxed checks | P integration-specific cases; covered generally by current regressions |
| Extra fields/unsupported YAML/nested input/schema declarations | Every unsupported construct diagnosed; no dropped data or unsafe constructors/network | P |
| Unknown relative URI bases/external evidence | No source fetch; every ambiguous base unresolved | P |
| Existing builder graph contract and tool name collisions | Exactly one selected builder; no discovered script executed; component/claim edges and trust views kept distinct | P; fixture sentinel does not test real builder behavior |
| Legacy generated/state durable notes | 0 deletions/relocations; old byte hashes preserved through every path | P automatic integration; preserved in executed probes |
| No second authority | No shadow canonical directory/registry/cache; projections disposable and explicitly nonauthoritative | P integration implementation audit |
| Repeated inventory/proposal and reordered traversal | Identical IDs/order/serialized proposal bytes for identical inputs | P |
| Source/canonical/tool edits after proposal | Fingerprint mismatch blocks action; external edit retained | P |
| Foreign/pending population state, unknown recovery protocol | Stop with actionable diagnostic; no bypass/cleanup | P integration-specific tests; existing known-protocol gates remain tested |
| Symlinks/junctions/FIFO/hardlinks and escaping roots | No unsafe reads/writes/tool execution; diagnostic, no lost bytes | P integration-specific inventory; current protections unchanged |
| Case-fold/Unicode/path aliases and NTFS locks/sharing | Collision diagnostics, preserved bytes, native Windows evidence required | P; native Windows NOT TESTED |
| Future optional tool-addition rollback | Fault each create/journal step; recover exact baseline plus external edits; remove only unchanged owned additions | P, separate approval required before implementing writes |
| No project execution/network/LLM | Blocked process/network APIs, zero calls; deterministic offline proposals | P adapters; current offline regression tests PASS |
| Full regression compatibility | Existing Stage 1/2 suite and .NET tests all pass; unchanged contracts | E PASS now; mandatory again for any 3.2 code |

## 9. Explicit Stage 3.2 GO / NO-GO gate

Stage 3.1 deliverables are available for review. **No Stage 3.2 implementation has
started and no review approval is inferred.** Conditional GO is limited to a
bounded read-only inventory/compatibility proposal implementation if all of the
following are explicitly agreed:

1. The knowledge owner reviews this assessment and confirms the existing store
   remains the sole authority; no migration/canonical writes are in that scope.
2. Tool owner identifies the existing graph entrypoint and its actual input/output
   contract; a single responsible builder and both graph trust boundaries are agreed.
3. Supported legacy formats and exact field/status/ID/URI mappings are specified;
   unsupported records remain blocked, not guessed or weakened into validity.
4. Every occupied/reserved path, evidence/provenance gap, durable generated/state
   file and conflicting transaction protocol has an explicit preservation rule.
5. Temporary/output locations and write-free defaults are approved; no shadow store
   or schema/manifest replacement is proposed. Source-only operation stays available
   independently when safe.
6. The applicable planned tests above have concrete assertions and fixtures before
   implementation; all regressions must continue passing. Platform acceptance is
   limited to actually executed environments, with native Windows separately pending.

**NO-GO** if any owner/graph responsibility is unknown; an adapter must infer
business/architecture truth; approval/time/provenance would be fabricated; IDs or
URI bases cannot be reconciled; legacy data would be deleted/overwritten; a second
canonical store/builder is required; validation must be relaxed; unsafe paths or
pending/unknown recovery state would be bypassed. Generic migration/apply remains
NO-GO even after approval of a read-only Stage 3.2 scope. Any future migration
needs separate explicit authorization and an independently reviewed rollback plan.

## 10. Changes and integrity

Added only this assessment and the fictional fixture bundle/README under
`tools/examples/existing-knowledge/`. Existing tracked implementation, Contract
v1.0, schemas, canonical knowledge and host-project files were not modified.
Existing tests and core validate/check-scaffold/version passed. No population
apply was invoked by compatibility probes or on the real repository. Existing
regression tests exercise apply only in their own disposable test fixtures. Installer probes mutated
only freshly created disposable fixtures, preserving every pre-existing fixture
file. No legacy tool sentinel was executed or imported. No real migration,
replacement, deletion, new schema, graph implementation, RAG, MCP or orchestration
was implemented.

## Appendix A. Executed installer and operation outcomes

Variants below were independently arranged in fresh temporary roots **before**
their initial snapshots; alternative manifests/schemas/path occupancy are test
inputs, not a migration procedure or instructions to modify a live store. The
original fixture bundle was never modified by the probes. Each init command was
`python -B /workspace/IPM/.ai/tools/kb.py init --root <temporary-case> --json`.
No probe called populate prepare/apply or invoked the fixture tool sentinel.

| Variant | Init exit | Old files checked/preserved | Files added | Subsequent validate | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| foreign-manifest | 1 | 19/19 | 0 | not invoked | Foreign manifest rejected; no takeover |
| missing-manifest | 1 | 18/18 | 0 | not invoked | Existing unrecognized data rejected |
| recognized-schema-conflict | 1 | 17/17 | 0 | not invoked | Occupied custom claim schema rejected |
| recognized-path-conflicts | 1 | 21/21 | 0 | not invoked | Existing README/tool content rejected |
| recognized-tool-conflict | 1 | 20/20 | 0 | not invoked | Exact builder path occupied: rejected |
| recognized-unchecked-records | 0 | 20/20 | 39 | 1 | Scaffold fills missing files but legacy records invalid; noncolliding legacy tool not discovered |
| native-v1-with-existing-builder | 0 | 9/9 | 39 | 0 | Native v1 records valid; noncolliding existing tool still not discovered |

Rejected installer outputs:

- recognized-schema-conflict: `schema/claim.schema.json: existing content differs; reconcile manually`.
- foreign-manifest: `manifest.yaml: unsupported or malformed manifest; expected format and schema versions 1.0.0`.
- missing-manifest: `.ai: existing data without a recognized manifest; reconcile manually`.
- recognized-path-conflicts: `README.md: existing content differs; reconcile manually`; `tools/knowledge_graph.py: existing content differs; reconcile manually`.
- recognized-tool-conflict: `tools/knowledge_graph.py: existing content differs; reconcile manually`.

The schema-only variant retained the custom claim schema with an exact v1
manifest and unoccupied README/tool paths; init rejected the schema mismatch.
Other recognized variants supplied v1 schema bytes at setup to isolate tool and
record behavior. No live schema/manifest was converted.

External source-only/canonical command probes on the unchanged foreign-manifest
fixture used the same trusted external CLI and `--root <fixture> --json`:

| Command | Exit | Old bytes unchanged |
| --- | ---: | --- |
| scan | 0 | True |
| extract | 0 | True |
| normalize | 1 | True |
| build | 1 | True |
| report | 1 | True |

Legacy schema-check diagnostics (in memory via the existing schema_errors):

- `.ai/evidence/review.json`: `$: missing type`; `$: missing status`; `$: missing source`; `$: missing provenance`; `$: missing captured_at`; `$: missing description`; `$: missing substantiates`; `$: unknown field excerpt_ref`; `$.id: invalid string pattern`; `$: unknown field kind`; `$: unknown field observed_on`; `$: unknown field reviewer`; `$: unknown field state`; `$: unknown field uri`.
- `.ai/evidence/source.json`: `$: missing type`; `$: missing status`; `$: missing source`; `$: missing provenance`; `$: missing captured_at`; `$: missing description`; `$: missing substantiates`; `$.id: invalid string pattern`; `$: unknown field kind`; `$: unknown field observed_on`; `$: unknown field state`; `$: unknown field supports`; `$: unknown field uri`.
- `.ai/knowledge/claims/architecture.json`: `$: missing statement`; `$: missing type`; `$: missing status`; `$: missing evidence`; `$: missing provenance`; `$: missing last_verified`; `$: missing depends_on`; `$: missing conflicts_with`; `$: unknown field confidence`; `$.id: invalid string pattern`; `$: unknown field kind`; `$: unknown field reviewed_by`; `$: unknown field state`; `$: unknown field support`; `$: unknown field text`.
- `.ai/knowledge/claims/rule.json`: `$: missing statement`; `$: missing type`; `$: missing status`; `$: missing evidence`; `$: missing provenance`; `$: missing last_verified`; `$: missing depends_on`; `$: missing conflicts_with`; `$.id: invalid string pattern`; `$: unknown field kind`; `$: unknown field reviewed_by`; `$: unknown field reviewed_on`; `$: unknown field state`; `$: unknown field support`; `$: unknown field tags`; `$: unknown field text`.
- `.ai/knowledge/relationships/component.json`: `$: missing type`; `$: missing from`; `$: missing to`; `$: missing provenance`; `$: unknown field conditional`; `$.id: invalid string pattern`; `$: unknown field kind`; `$: unknown field source`; `$: unknown field target`.

## Appendix B. Exact fixture inventory and ownership

All entries are synthetic-project-owned. The bundle's file values below are the
actual UTF-8 contents used in the foreign-manifest probe; these hashes are the
inventory, not a new registry or source of canonical authority. Relative paths
are relative to the disposable host root. Classification/possible v1 counterpart
is described in the ownership matrix above; unique legacy notes remain protected.

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| .ai/README.md | 192 | `d40622e6c5d064cc882b99f7a9dc9ad3349ea5b9543bf98553a050e1ed874eef` |
| .ai/business/concepts.yaml | 138 | `ccf4549701af64360c27505078d7f579ead8675133d9d3201e6da2b4b4807ff1` |
| .ai/evidence/review.json | 219 | `707d300873557b7dc49e0dac4b268553f7dae1052d0b069dd0d2bb6913d251f1` |
| .ai/evidence/source.json | 163 | `4fa344d30a9bc1be3f7c699051c0bf9b6d4d2942b65f8db67fbcf58cf8d65ab4` |
| .ai/generated/architecture.json | 286 | `9de2aac4b801e67ebbd9d635e8a12df175e8d2f304053c7fc51668edfdf30d84` |
| .ai/generated/curator-notes.md | 178 | `d46e08fb117b81842569a847f82c79dd257897b322384f046b1a56fff28a4430` |
| .ai/knowledge/claims/architecture.json | 229 | `38ad889258f53e9d14296c2943488126b2c60f2a8d29df89ea2dd27c9622a102` |
| .ai/knowledge/claims/rule.json | 280 | `392de03e21e9c0821cf9c2e232da99b61120dd914e41e257ff95c4896135f01b` |
| .ai/knowledge/decisions/ADR-017.md | 189 | `1112c2245200f036845b80c4c4e65e83a1f79956e96c732fbd14fb770615c00f` |
| .ai/knowledge/domains/ticketing.md | 141 | `6523874a1aac1200069273daeb1eecb68f021849920ebb2dcafb8d6232647ebb` |
| .ai/knowledge/relationships/component.json | 115 | `18e59a0ada261ed4da3ec7494e163733873d20a9ec8a82ff45dd6aaa40938e72` |
| .ai/manifest.yaml | 156 | `083199de374ce11f048819e83ef946854cc9e58aecb578051ed416e96d3c3cd2` |
| .ai/schema/claim.schema.json | 183 | `b90b01e9ced0a52e6bd490f4ce2d3af47b9bd3ade894dbb2447383b59da51dfb` |
| .ai/sources/access.md | 105 | `fa7fb813c54d5c7ee54c272b5917ad8bdd11b7eafe6d44ed5fce766059cfa405` |
| .ai/state/team-decisions.md | 166 | `916ae45dfe5fd4eefc900fa5f9f2750172ded1fef61f51ffbb8758620ad59ac0` |
| .ai/tools/graph-contract.json | 378 | `a73e07baf4a0cde0518499d9646975af9b81dbf882c302f7a9e27bf6c3c8bfc7` |
| .ai/tools/knowledge_graph.py | 232 | `05e1d00b0c4faa71aa4b79c2c0ed6e3bac9cd4fe62af1e9ab5d1fa82ade6ae6d` |
| host.txt | 47 | `610da875430d9a627330e7a06ed1341e1d39043253345364007d404c6c04a5c9` |
| src/TicketHub/TicketHub.csproj | 117 | `91275edd3790c4f0cb484653195ccd8ad6af2f1a0a69b84fdb26b88c0b52407f` |

## Appendix C. Reproducible assessment probe (test harness only)

The following final script was actually executed as `/tmp/stage31_probe.py`.
It constructs independent variants, runs the existing CLI and checks old-file
hashes. It has no migration/apply function, is not installed as an adapter and
must never be pointed at a live root. Its root and fixture bundle are explicit.
Transient roots/logs from the final run were at `/tmp/ipm-stage31-s0uxwmi8`;
the result tables/diagnostics/inventory above are retained here independently of
that temporary directory.

<details><summary>Disposable probe script</summary>

```python
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile
REPO=pathlib.Path('/workspace/IPM');CLI=REPO/'.ai/tools/kb.py'
sys.path.insert(0,str(CLI.parent))
import kb
payload=json.loads((REPO/'.ai/tools/examples/existing-knowledge/fixture.json').read_text())
work=pathlib.Path(tempfile.mkdtemp(prefix='ipm-stage31-'))
def write(root,name,data):
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data,encoding='utf-8')
def snap(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def legacy(name):
 root=work/name;root.mkdir()
 for path,data in payload['files'].items():write(root,path,data)
 return root
def recognize(root):
 write(root,'.ai/manifest.yaml',(REPO/'.ai/manifest.yaml').read_text())
 for path in (REPO/'.ai/schema').glob('*.json'):write(root,'.ai/schema/'+path.name,path.read_text())
results=[]
def probe(root,expected,unchanged=True):
 before=snap(root)
 run=subprocess.run([sys.executable,'-B',str(CLI),'init','--root',str(root),'--json'],capture_output=True,text=True)
 after=snap(root)
 assert run.returncode==expected,run.stdout+run.stderr
 assert all(after.get(name)==content for name,content in before.items())
 if unchanged:assert before==after
 result={'case':root.name,'command':['python','-B',str(CLI),'init','--root',str(root),'--json'],'exit_code':run.returncode,'result':json.loads(run.stdout),'existing_files':len(before),'preserved_files':len(before),'added_files':len(after.keys()-before.keys())}
 results.append(result)
 return result
root=legacy('foreign-manifest');probe(root,1)
root=legacy('missing-manifest');(root/'.ai/manifest.yaml').unlink();probe(root,1)
root=legacy('recognized-schema-conflict');write(root,'.ai/manifest.yaml',(REPO/'.ai/manifest.yaml').read_text());(root/'.ai/README.md').unlink();(root/'.ai/tools/knowledge_graph.py').unlink();probe(root,1)
root=legacy('recognized-path-conflicts');recognize(root);probe(root,1)
root=legacy('recognized-tool-conflict');recognize(root);(root/'.ai/README.md').unlink();probe(root,1)
root=legacy('recognized-unchecked-records');recognize(root);(root/'.ai/README.md').unlink()
(root/'.ai/tools/knowledge_graph.py').rename(root/'.ai/tools/legacy_graph.py')
r=probe(root,0,False)
validation=subprocess.run([sys.executable,'-B',str(CLI),'validate','--root',str(root),'--json'],capture_output=True,text=True)
assert validation.returncode==1
r.update(validation_exit=1,validation=json.loads(validation.stdout),universal_graph_added=(root/'.ai/tools/knowledge_graph.py').is_file(),legacy_graph_preserved=(root/'.ai/tools/legacy_graph.py').is_file())
root=work/'native-v1-with-existing-builder';root.mkdir();recognize(root)
write(root,'.ai/tools/legacy_graph.py',payload['files']['.ai/tools/knowledge_graph.py'])
write(root,'.ai/knowledge/domains/ticketing.md',payload['files']['.ai/knowledge/domains/ticketing.md'])
write(root,'.ai/knowledge/decisions/ADR-017.md',payload['files']['.ai/knowledge/decisions/ADR-017.md'])
claim={'id':'claim.legacy.policy','statement':'Synthetic supervisor approval is required for reopening.','type':'business_rule','status':'NEEDS_HUMAN_CONFIRMATION','evidence':['evidence.legacy.note'],'provenance':{'actor':'fictional-team','method':'existing-fixture-record'},'last_verified':None,'depends_on':[],'conflicts_with':[]}
evidence={'id':'evidence.legacy.note','type':'supporting','status':'active','source':'.ai/knowledge/decisions/ADR-017.md','provenance':{'actor':'fictional-recorder','method':'existing-fixture-note'},'captured_at':'2026-01-10T12:00:00Z','description':'Synthetic prior note, not authenticated confirmation.','substantiates':['claim.legacy.policy']}
write(root,'.ai/knowledge/claims/policy.json',json.dumps(claim));write(root,'.ai/evidence/note.json',json.dumps(evidence))
r=probe(root,0,False)
validation=subprocess.run([sys.executable,'-B',str(CLI),'validate','--root',str(root),'--json'],capture_output=True,text=True)
assert validation.returncode==0,validation.stdout
r.update(validation_exit=0,validation=json.loads(validation.stdout),universal_graph_added=(root/'.ai/tools/knowledge_graph.py').is_file(),legacy_graph_preserved=(root/'.ai/tools/legacy_graph.py').is_file())
# Existing uninitialized foreign .ai: source-only operations versus canonical consumers.
external=work/'foreign-manifest';operation_results=[]
for command,expected in [('scan',0),('extract',0),('normalize',1),('build',1),('report',1)]:
 before=snap(external)
 run=subprocess.run([sys.executable,'-B',str(CLI),command,'--root',str(external),'--json'],capture_output=True,text=True)
 assert run.returncode==expected,run.stdout
 assert before==snap(external)
 output=json.loads(run.stdout)
 if command=='extract':assert output['counts']['candidates']==2
 operation_results.append({'command':command,'exit_code':run.returncode,'output':output,'all_bytes_preserved':True})
schema=kb.read_json(REPO/'.ai/schema/claim.schema.json')
evidence_schema=kb.read_json(REPO/'.ai/schema/evidence.schema.json')
relationship_schema=kb.read_json(REPO/'.ai/schema/relationship.schema.json')
schema_results={}
for path in ['.ai/knowledge/claims/rule.json','.ai/knowledge/claims/architecture.json','.ai/evidence/review.json','.ai/evidence/source.json','.ai/knowledge/relationships/component.json']:
 s=evidence_schema if '/evidence/' in path else relationship_schema if '/relationships/' in path else schema
 issues=kb.schema_errors(json.loads(payload['files'][path]),s)
 assert issues
 schema_results[path]=issues
fixture_inventory=[{'path':name,'bytes':len(data.encode()),'sha256':hashlib.sha256(data.encode()).hexdigest(),'owner':'synthetic-existing-project'} for name,data in sorted(payload['files'].items())]
result={'workspace':str(work),'cases':results,'schema_results':schema_results,'fixture_inventory':fixture_inventory,'external_operations':operation_results}
(work/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2,sort_keys=True))
```

</details>

Final integrity checks: all 1148 existing host-file SHA-256 values and 11
canonical/schema/source-metadata/manifest file SHA-256 values unchanged; no host
paths added or removed. `git diff --exit-code` against the exact baseline reports
no tracked changes. The only additions are the three deliverable files listed
above. Core validate/check-scaffold and whitespace checks pass.
