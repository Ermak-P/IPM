# Stage 3.3 — bounded read-only compatibility adapter PoC

Baseline: 7c52bfcc5b8b262c2334d291d2d2f88ba89e32bd, branch work.
This extends the reviewed Stage 3.1 assessment and Stage 3.2 Inspector with
nonauthoritative proposals only. Contract v1.0, schemas, validator, existing
normalizer, Inspector and knowledge are unchanged. There is no migration,
installation mode, approval workflow, population apply or integration activation.

## CLI and API

```sh
python -B /trusted/IPM/.ai/tools/kb.py adapt-compatibility --root /synthetic/project --json
python -B /trusted/IPM/.ai/tools/kb.py adapt-compatibility --root /synthetic/project
```

Only --root and --json are accepted. No output, write-generated, approve, plan,
dry-run or exclude option exists. Reports go to stdout only. Do not redirect
into the inspected .ai. The bundled example is explicitly saved under this
framework checkout's disposable generated/, not inside the legacy fixture.
Optional command packaging is registered in the existing scaffold; the adapter
never invokes installation and no new installation feature was added.

```python
from compatibility_inspector import CompatibilityInspector
from compatibility_adapter import CompatibilityAdapter
inspection = CompatibilityInspector().inspect(root)
proposal = CompatibilityAdapter().propose(root, inspection)
# Or omit inspection to request a fresh authenticated inspection internally.
```

Adapter Protocol exposes profile and map_fields(group, safely_parsed_record).
ContractV1Adapter and HarborRevision3Adapter implement the explicit rules below;
CompatibilityAdapter coordinates authentication, identities, closure and actual
v1 dataset validation. Low-level field mappers are not safe public entrypoints
for arbitrary saved input; use propose(). There is no plugin execution/discovery.

The supplied inspection is never trusted on its own. propose() runs the existing
Inspector, requires complete/ok, and compares the complete report if supplied.
It obtains raw metadata only through the Inspector's bounded Inventory, compares
snapshot fingerprints and rechecks inspection/stat observations after mapping
and validation. Tampered/stale reports, unsafe/incomplete inventory, unsupported
manifest/container or observable changes refuse/discard proposals. Any
state/population presence refuses projection: incomplete transactions must not
be presented as safe knowledge. No lock/journal is interpreted or written.
Discovered graph ownership blocks integration, but does not prevent a safe,
clearly nonauthoritative compatibility proposal from reporting representable data.

## Supported synthetic containers

1. Exact Contract v1 manifest: records in knowledge/claims, evidence and
   knowledge/relationships must already satisfy the pinned v1 schema. Compatible
   IDs, fields, statuses, timestamps, provenance and relationships are retained.
2. Harbor Tickets format=harbor-team-architecture, integer revision=3: the explicit
   JSON fields below are supported. This is the documented **synthetic** PoC
   profile, including complete test records with explicitly supplied provenance/
   observation fields. Original incomplete records remain blocked. Exact v1-shaped
   records without a legacy kind field may coexist as verbatim candidates for
   collision/reference testing; this is not automatic adoption of mixed formats.

No arbitrary YAML, Markdown, business concepts/prose extraction, future revision,
unknown container or natural-language inference is supported. Original Harbor
fixture.json remains unchanged test input, not a second canonical store. All
mapping tests materialize inputs in disposable repositories. No corporate data
was used.

## Exact Harbor revision 3 field specification

| Legacy claim field | Proposed v1 field | Rule |
| --- | --- | --- |
| id | id | Stable identity rules below; original ID/source retained separately |
| kind | type | business-policy → business_rule; component-responsibility → architecture; technical-fact → technical_fact; explicit synthetic type labels, never inferred from names |
| text | statement | Literal selected assertion, bounded to 4096 serialized characters; not a claim of semantic equivalence or truth |
| state | status | Only exact CONFIRMED, INFERRED, UNKNOWN, NEEDS_HUMAN_CONFIRMATION; no conversion from approved/verified |
| support | evidence | Explicit original evidence IDs, fully resolved to proposed IDs |
| provenance | provenance | Explicit actor/method copied unchanged; reviewer/reviewed_by is not a replacement |
| last_verified | last_verified | Must explicitly exist (null allowed for unverified claims); no date/event invented |
| depends_on, conflicts_with | same fields | Explicit claim IDs only; required arrays, no inferred edges or fabricated empty-array defaults |

| Legacy evidence field | Proposed v1 field | Rule |
| --- | --- | --- |
| id | id | Same identity rules; no timestamp/hash in generated IDs |
| kind | type | meeting-note → supporting, source-code → direct-technical; exact supporting/derived/direct-technical/direct-authoritative literals retained. No meeting-note/source-code → authoritative conversion |
| state | status | Only exact active/retracted/superseded; current/withdrawn remain blocked, not guessed |
| uri | source | Literal reference; only explicit http/https/urn scheme, or safe relative reference with uri_base=repository-root. No URL fetch/source read; unsupported scheme/base blocked |
| uri_base | proposal metadata only | Only repository-root supported; retained as legacy_source_base, not added to canonical evidence |
| provenance | provenance | Explicit actor/method preserved; no human/reviewer/authority inference |
| captured_at | captured_at | Explicit existing timezone-qualified v1 timestamp required; observed_on, a date-only value or current clock cannot substitute |
| location, description | same fields | Explicit selected metadata; no source snippets or file copying; bounded fields |
| supports | substantiates | Explicit original claim IDs, not synthesized by reversing claim citations |
| content_hash | content_hash | Optional existing v1 sha256 value retained; never manufactured from the legacy JSON file hash |

Harbor relationships are **unsupported** in this PoC, including component calls
and conditional edges; there is no guess at claim-level meaning. Compatible
native v1 relationships can pass through only with complete claim-array agreement
and validator-accepted closure. No canonical relationship type is introduced.

All other properties, including tags, confidence, reviewed_by, reviewed_on,
reviewer, excerpt_ref, observed_on and conditional, are explicit blocking data-loss
risks. Each unsupported property is diagnosed by a safe bounded name and/or field
fingerprint; nested properties in schema-constrained objects are also checked.
Unknown values are not copied into a side registry or dropped to make an otherwise
valid proposal pass. The original file remains untouched, with its source/hash
in metadata. Fields inside an entirely unsupported property subtree are covered
by the blocking diagnostic for that whole property; no part is converted.

Unknown/missing/ambiguous mappings remain blocked. None is repaired into a new
status, source authority, evidence event or architectural interpretation. A
literal kind-to-type rule is a declared synthetic format convention, not a
semantic-equivalence determination about arbitrary human prose.

## IDs, references and preserved provenance

Each mapping includes source (root-relative original JSON path),
source_content_hash, original_id, original_id_fingerprint, proposed_id,
record_type, profile, original_lifecycle, legacy_source_base, reasons,
classification and human_review_required. Metadata is outside canonical records.
Opaque/oversized original IDs are blocked, represented by fingerprint/source
rather than copied unboundedly; originals remain intact at that source.

Valid v1 IDs are retained. Invalid but bounded Harbor IDs such as RULE/17 map to
`claim.legacy.harbor3.<SHA-256 of canonical-JSON original ID>` (evidence and
relationship prefixes use their singular record kind). No traversal position,
source hash, root path, clock or mutable text enters the generated identity.
Original global duplicates are blocked even across record kinds; generated IDs
are compared with every other proposed/native ID and collisions block all
participants. No automatic ID registry, deduplication/merge or filename rewrite.
Invalid native v1 IDs are blocked, not repaired using the Harbor namespace.

Reference lists and scalar relationship endpoints must have their original valid
shape; a bad string/list is not silently repaired into an empty array or scalar.
Every original ID must resolve uniquely to the expected record kind. Missing,
ambiguous and wrong-kind references retain safe target metadata/diagnostics;
references are not discarded to manufacture validity. Closure is propagated:
records citing blocked claims/evidence are blocked as well. Independent complete
components may still be proposed, with the blocked originals separately reported.

Original evidence provenance/captured_at and claim status/last_verified are
preserved. The legacy JSON content hash is only an observation of the input
record, not the source-evidence content_hash. No extraction or mapping timestamp
is generated. All records, including structurally valid CONFIRMED records,
require human review before any later insertion decision.

## Complete structural validation

The adapter reuses the unmodified **kb.validate** on the full candidate dataset
with complete reference closure. Its staging harness follows the existing
normalizer staging layout: pinned framework manifest/schema bytes, numeric JSON
filenames (never input IDs as paths), one object per file, outside the inspected
repository. The existing validation/normalization functions are not changed.

Temporary staging parent is selected without tempfile.gettempdir() probing an
inspected directory: cached tempdir, otherwise explicit TMPDIR/TEMP/TMP, otherwise
OS default /tmp or SystemRoot/Temp. If the chosen parent is absent, inside the
inspected root or resolves inside it, the proposal is refused before any staging
write. Temp directories are closed/removed by context management. Staging contains
only candidate v1 records and pinned schemas, never entire legacy .ai/source files.
It is disposable validation context, not a second authoritative store. I/O/cleanup
errors fail the request rather than authorizing target writes or weakening checks.

Schema/provenance/status failures block records before staging. For remaining
reference-closed candidates the actual validator checks global IDs, references,
cycles, symmetric conflicts, optional relationship agreement and CONFIRMED support.
Business-rule confirmation needs explicit active direct-authoritative evidence,
location, substantiation and genuine supplied verification date; supporting,
inactive or technical evidence alone cannot satisfy it. A passed structural check
does not authenticate that authority or event, so semantic_acceptance_established
and both insertion/integration approval flags always remain false.

If the complete remaining dataset fails, this conservative PoC blocks that entire
attempt rather than guessing which records to remove. The failed validation and
errors are retained. Returned proposals become an empty separately validated
dataset. nonempty_candidates_validated=false and candidate count=0 make clear
that an empty PASS is not evidence that any legacy knowledge is representable.
No failed/unclosed record is returned in records.

## Report/exit semantics and measured coverage

Proposal version 1.0 includes records, explicit id_mappings, blocked_mappings,
unresolved_records, diagnostics, complete Inspector report (including ownership/
graph blockers), graph_boundary, validation and metrics. No graph is constructed.
All output is reproducible for unchanged inputs; formatting edits preserve IDs/
selected candidate records while source fingerprints change.

Exit 0 / ok=true means authenticated bounded mapping analysis completed, even
when every mapping is blocked. Exit 1 means unsafe, incomplete, changed,
unsupported-container or staging-failed processing; no usable records are emitted.
Invalid options exit 2. mapping_complete says whether the successfully analyzed
records are all representable, not whether integration is approved. metrics_complete
is false on failed processing; partial/zero counts then are not coverage claims.
validation.proposal_usable refers only to a structurally checked output and must
never be interpreted as authorization.

| Metric | Definition |
| --- | --- |
| legacy_records_inspected | All non-placeholder files in the three record directories considered, including opaque blocked formats |
| structurally_representable_records | Number of returned records accepted by complete isolated validation |
| blocked_records, unresolved_mappings | Number of mappings not emitted, retaining reasons/source/identity |
| id_reference_conflicts | Number of mappings with duplicate/colliding/unusable identities, unresolved refs or blocked reference closure; not a count of individual diagnostic messages |
| missing_provenance | Number of parsed records lacking explicit actor/method provenance; opaque formats remain unresolved, never assumed absent or filled from reviewers |
| unsupported_relationship_types | Number of unsupported Harbor or native relationship-type records |
| candidates_passing_isolated_structural_validation | Returned candidate count, zero on discarded/failed processing or empty-only output |
| records_requiring_human_review | Every inspected record, including structurally valid proposals |

### Original Harbor Tickets result

Example: ../generated/harbor-compatibility-proposal.json. Original fixture is
unchanged. Five records inspected: two claims, two evidence records and one
component relationship. **0/5 structurally representable, 5 blocked/unresolved,
0 candidates passing validation, 5 missing explicit provenance, 1 unsupported
relationship type, 0 ID/reference collisions, 5 requiring human review.** Slash
IDs have deterministic proposed IDs; unsupported lifecycle/properties and missing
fields prevent emission. No invalid ID or missing field is silently repaired.
The empty candidate dataset passes the validator but nonempty_candidates_validated
is false. This is measured zero coverage, not migration success.

- EV/17 and EV/18: unknown relative URI bases, unsupported lifecycle labels,
  missing explicit capture/provenance/description/substantiation fields and custom
  properties. withdrawn is not reactivated or automatically retracted.
- ARCH/4 and RULE/17: verified/approved are not v1 statuses; provenance,
  verification/dependency/conflict fields are incomplete; confidence, tags and
  review metadata are not silently discarded.
- EDGE/4: component calls/conditional metadata is not a v1 claim relationship;
  provenance/required canonical relationship fields are incomplete.

Positive synthetic tests separately provide the complete documented fields:
a linked Harbor claim/evidence pair maps to two v1 records, with unchanged
provenance/time/status; explicit native v1 relationships validate unchanged.
Those tests prove representability of the supported synthetic format, not that
the incomplete original fixture can be accepted or its evidence is authoritative.

## Graph ownership boundary and next decision

No discovered graph tool is imported, executed, installed or replaced. The full
Inspector graph contract/entrypoints/declared IO and ownership blockers remain in
the report; unknown ownership is never resolved by successful validation.

Future integration requires the chosen owner-controlled builder to explicitly
agree to consume a nonauthoritative proposal envelope: records plus id_mappings
(original/proposed IDs, source/hash), validation results, Inspector snapshot,
blocked/unresolved entries and lifecycle/provenance. It must retain those trust
labels in its output; never treat records as accepted canonical knowledge or
reinterpret component calls/declared technical observations as claim dependencies.
Harbor currently declares filesystem inputs knowledge/claims, relationships and
domains and output generated/architecture.json. This adapter does not write those
inputs or that output; that existing path-based contract is not activation of a
proposal-data interface. Output paths/disposability require explicit owner
selection; a host generated/ directory is not presumed safe.

Recommended decision: **NO migration/integration GO**. Review unsupported fields,
URI bases, lifecycle semantics and actual missing evidence events with synthetic
knowledge/tool owners first. Decide whether any separately authorized future
interface should consume noncanonical proposals without a second active graph
pipeline. Do not add facts/timestamps merely to improve coverage. No Stage 3.4
implementation or approval is implied by this PoC.

## Tests and limitations

```sh
python -B -m unittest discover -s .ai/tools/tests -p 'test_adapter.py'
python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
```

Tests use only disposable fixtures. Inspector safety limits/exclusions remain in
force; observable final changes discard all proposals. Stable trusted trees are
still required: portable checks do not isolate hostile same-user path swaps.
Full validation failures conservatively suppress the whole attempted candidate
dataset, rather than finding maximal salvageable subgraphs. Formats and metadata
sizes are deliberately bounded, graph discovery is not exhaustive, no source
URLs/authority registries are consulted, and no semantic equivalence is established.
Native Windows/NTFS acceptance remains separately pending; Linux or mocks do not
close that gate.

## Executed verification and changed files

Environment: Linux x86_64, Python 3.12.14, pinned .NET SDK 10.0.402.
Baseline Python suite: 252 passed. Final commands actually executed:

- `python -B -m unittest discover -s .ai/tools/tests -p 'test_adapter.py'`:
  38 passed, 0 failures/errors/skips.
- `python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'`:
  **290 passed**, 0 failures/errors/skips, including all prior regressions.
- Existing .NET unit/integration DLLs via `dotnet vstest`:
  **27 passed** (12 unit, 15 integration), 0 failed/skipped, no build/restore.
- validate, check-scaffold, version and git diff --check: exit 0.
- Harbor adapt-compatibility CLI repeated with byte-identical stdout; the Stage
  3.2 Harbor Inspector example still matches unchanged. The new proposal example
  was regenerated only from the disposable fixture.
- Positive synthetic pair: 2/2 complete reference-closed candidates validated;
  native claim/relationship fixture: 3/3 unchanged compatible records validated.
  Original Harbor: 0/5 coverage, all five blocked, no empty-dataset success claim.
- SHA-256 comparison: 1148 real host files and 11 canonical/schema/source-
  metadata/manifest files unchanged, no host/canonical files added or removed.
  Inspector, existing normalizer, core validator/parser/installer function bodies,
  schemas, Contract v1.0 and original Harbor fixture remain unchanged.
- No real population apply, migration, approval, graph invocation or corporate
  data access was performed. Native Windows/NTFS: NOT TESTED; gate stays open.

Changed files: tools/compatibility_adapter.py, tools/tests/test_adapter.py,
tools/kb.py, docs/compatibility-adapter.md, README.md and disposable
example generated/harbor-compatibility-proposal.json. CLI dispatch/packaging is
extended only to make the read-only command available. Stage 3.4 was not started.
