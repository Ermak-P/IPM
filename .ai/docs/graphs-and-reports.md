# Increment E: disposable graphs and knowledge reports

Baseline inspected: ca7a159a950be7e0f810d70f17bdb6ef8e2948d1 (work).
No Graph Builder existed: Stage 1 and A–D.1 explicitly deferred it. The single
project-owned builder is now tools/knowledge_graph.py, shared by both views and
reporting. Contract v1.0, schemas, core validator and A–D.1 implementations are
unchanged. These are optional CLI extensions; manifest core capabilities remain
pinned. There is no second authoritative store or graph write-back.

## Actual canonical relationship semantics (preflight)

See knowledge-lifecycle.md and the pinned relationship.schema.json. Claim
`depends_on` arrays are directed acyclic claim dependencies, not project/runtime
dependencies. `conflicts_with` arrays are symmetric, allow conflict cycles and
forbid self-links. Optional relationship records permit only these two types,
must match claim arrays and cannot duplicate an edge, including reversed
conflicts. They document an existing claim edge; they never independently add it.

A claim's `evidence` array cites evidence. Evidence `substantiates` explicitly
identifies the claims it supports; a citation alone does not imply substantiation.
Retracted/superseded evidence remains visible with its original status. A valid
CONFIRMED claim needs appropriate active direct evidence, a location, an explicit
substantiation link and last_verified. The validator checks structure and these
invariants, not semantic truth or source freshness. Building does not reverify or
approve any claim.

## Commands and trust boundaries

```sh
python -B .ai/tools/kb.py build --json
python -B .ai/tools/kb.py build --view canonical --json
python -B .ai/tools/kb.py build --view technical-preview --json
python -B .ai/tools/kb.py build --view technical-preview --exclude vendor --json
python -B .ai/tools/kb.py report --json
python -B .ai/tools/kb.py report
python -B .ai/tools/kb.py build --view canonical --write-generated --json
python -B .ai/tools/kb.py build --view technical-preview --write-generated --json
python -B .ai/tools/kb.py report --write-generated --json
```

Default build: **canonical only**, no host scan. `--view technical-preview` is an
explicit noncanonical preview, never merged into the canonical graph. Report
always contains separately named canonical and technical_observations sections
plus a comparison of proposals to retained knowledge. `--exclude` is additive and
applies only to technical-preview/report, never to canonical records.

Without --write-generated, stdout is the only output. With it, fixed filenames
are used under .ai/generated/: canonical-graph.json, technical-preview-graph.json,
knowledge-report.json. JSON on stdout and in the file represents the same result.
There is no arbitrary output-path option. Writes reject links, hardlinks and
unexpected objects; write handles are closed before atomic single-file replace.
A replacement failure preserves the previous artifact and removes the temporary
file. Cross-file atomicity and Windows power-loss durability are not claimed.
Artifacts can be deleted in their entirety and regenerated; the CLI recreates
`generated/` if absent. No unique knowledge, registry or input cache lives there.

Exit 0 means a view/report was successfully produced, not that claims are true.
Exit 1 rejects invalid, stale, unsafe, busy or recovery-required input. Invalid
canonical records prevent both graph views and reporting. An incomplete scan,
unsafe/malformed XML or invalid normalization prevents technical previews and
reports instead of yielding an apparently complete graph. Error results include
validation or extraction diagnostics where available; no partial graph is emitted.
Canonical-only building can succeed independently of broken host XML.

## Public API and schema-level separation

```python
from knowledge_graph import GraphBuilder
builder = GraphBuilder()
canonical = builder.build(root)  # view='canonical'
preview = builder.build(root, view='technical-preview', exclusions=['vendor'])
report = builder.report(root, exclusions=['vendor'])
```

Both API methods acquire the existing population coordinator for their complete
read, enforce pending transaction/recovery gates, validate an isolated canonical
snapshot using the unmodified kb.validate, and recheck canonical fingerprints
before returning. Technical views use the existing Scanner, DotNetAnalyzer and
CandidateNormalizer; the latter authenticates/re-observes extraction and validates
its proposals. A final observation comparison rejects changed source inputs.
Low-level pure mapping helpers require already validated input; callers should
use GraphBuilder. Direct API failures raise PopulationError/GraphInputError or an
I/O exception; CLI converts them into nonzero JSON error results.

Build result: `{command, ok, graph, validation}`. Graph payload:

| Field | Canonical | Technical preview |
| --- | --- | --- |
| graph_version | derived-graph-v1 | derived-graph-v1 |
| view | canonical | technical-preview |
| authority | validated-canonical-records | noncanonical-technical-observation-preview |
| semantic_truth_established | false | false |
| dependency_interpretation | explicit-claim-dependencies-only | declared-not-evaluated; runtime-dependencies-unknown |
| nodes, edges | canonical mapping below | observed mapping below |

Every node has `id`, `kind`, `data`, `source_references`,
`supporting_claim_ids`, `supporting_evidence_ids`, `provenance`.
Every edge has `id`, `kind`, `from`, `to`, `directed`, `metadata`,
`source_references`, `supporting_claim_ids`, `supporting_evidence_ids`,
`canonical_relationship_ids`, `provenance`. Empty arrays mean no such canonical
support was asserted. No numerical confidence is invented.

### Canonical mapping

| Input | Derived representation |
| --- | --- |
| Claim | claim node with exact canonical ID and original fields/status/last_verified |
| Evidence | evidence node with exact canonical ID and original type/status/location/hash/observation time |
| Claim evidence array | directed cites_evidence claim → evidence |
| Evidence substantiates array | directed substantiates evidence → claim, original evidence status attached |
| Claim depends_on array | directed depends_on claim → claim |
| Symmetric conflicts_with arrays | one undirected conflicts_with per unordered claim pair |
| Optional relationship record | canonical_relationship_ids and provenance attached to the matching edge |
| Claim/evidence provenance | provenance node and has_provenance edge, deduplicated by actor/method |
| Evidence source | source_reference node and references_source edge; a reference is never fetched |

Nodes retain original canonical records so historical facts and lifecycle data
remain visible. Source references and provenance are descriptive metadata, not
new assertions about inaccessible external sources. Claim-only connectivity
excludes provenance/source nodes to avoid shared extractor actors connecting
otherwise unrelated claims. Full connectivity is also provided.

### Technical observation mapping

| Analyzer/normalizer input | Derived representation |
| --- | --- |
| project candidate | observed_project with root-relative path, filename label, observed-file existence |
| scanned .sln/.slnx | observed_solution with inventory-file existence (including empty solutions) |
| solution_membership | declared_solution_membership solution → project/reference placeholder |
| project_reference | declared_project_reference project → project/reference placeholder |
| package_reference | declared_package_reference project → declared_package with literal Include |
| package_version | declared_package_version project → declared_package with literal Version/VersionOverride |
| project_property | declared_project_property to target_framework_declaration or project_property_declaration |

An unresolved target is an unresolved_project_reference node with
existence=not-established. Inventory resolution (`discovered`) does not establish
conditional activation, runtime dependence or architectural responsibility.
Framework lists remain literal TargetFrameworks declarations; expressions are not
expanded. Package nodes do not establish availability, restored versions or
transitive packages. Project edges are direct only, with no transitive closure.

All declaration edges have metadata.interpretation=declared-not-evaluated, original
conditions, resolution, declared_value, active_evaluated_dependency (unknown for
ProjectReferences), extraction_ids and **proposed** claim/evidence IDs. Those IDs
are references to normalized proposals, not canonical supporting IDs or approval.
Project nodes also expose proposed_claim_ids/proposed_evidence_ids. Source refs
contain root-relative paths, precise analyzer locations, source hashes and
extractor provenance. No source snippets, code or fresh captured_at values are
embedded. Duplicate declarations produce one edge with all evidence occurrences.
No observed edge has canonical kind depends_on or conflicts_with.

## Determinism and identity

Derived IDs use SHA-256 of canonical JSON, independent of iteration order and
clock time. Canonical record IDs are preserved. Provenance/source IDs hash their
literal values, with `derived/provenance` and `derived/source` namespaces.
The slash is prohibited in v1 canonical IDs, preventing metadata nodes from
colliding with valid canonical record IDs. Edges use `derived/edge` IDs.
Observed project/solution IDs hash paths; package IDs hash literal
Include; unresolved/property IDs hash stable declaration subjects/values. Edge
IDs hash view, kind, endpoints and stable normalized claim ID when applicable.
Conflict endpoints are sorted before hashing. Nodes/edges sort by ID and reference
collections deduplicate/sort. Identical input records/observations produce the
same serialized JSON and no accumulated duplicate entries.

Fresh normalizer captured_at timestamps are deliberately omitted from derived
observations/reports. Historical canonical timestamps remain unchanged in record
nodes: they are input data, not generation time. Formatting edits preserve graph
identities while changing evidence locations/content hashes. Substantive edits
change relevant declaration IDs; removed observations vanish from the preview.
Canonical historical records remain intact. No separate changing observation
envelope is necessary. Canonical record array ordering is retained in node data;
reordering filesystem traversal alone never changes the graph.

## Reports

The human summary and derived-report-v1 JSON include claim totals by type/status,
evidence totals by type/status, insufficiently verified claims, explicit unresolved
conflicts, evidence source observations, project/solution counts, declared direct
references, conditional/unresolved references, discovered/skipped inputs, extraction
diagnostics, comparison classifications/diagnostics and structural validation.
Comparison entries retain add/unchanged/potential update/conflict/unresolved;
none implies acceptance/rejection or authorization to populate.

Connectivity contains sorted weak components and isolated IDs for the full graph
and separately claims/projects. In project-only connectivity, solution/package/
property nodes do not connect projects; only direct resolved project edges do.
Missing/outdated evidence is checked only against safe current source inventory
and analyzer hashes. missing_from_current_inventory=true means no observed source,
no matching inventory entry and no skipped file/ancestor that could hide it.
Otherwise unavailable sources are explicitly removed/excluded/unsupported/external
uncertainties. Same hash is not semantic reverification. Inactive evidence remains
inactive. No arbitrary canonical source path is opened or external URL fetched.

Disagreement uses the existing normalizer's exact identities, subject slots,
source hashes and overlap diagnostics; it does not parse human prose. Existing
claims and current declarations are kept as separate views even when they differ.
No automatic conflict resolution, deletion, supersession, status changes or
verification events occur.

## Security, testing and limits

All operations are offline stdlib Python; no LLM, project execution, restore,
MSBuild evaluation or semantic C# analysis. Existing exclusions, safe XML parsing,
path/link restrictions and validation remain in force. Stable trusted input trees
are required, as in A–D.1: final fingerprints detect observable concurrent edits
but portable filesystem checks do not isolate hostile same-user ancestor swaps
or writes occurring after the final check. Generated artifacts are a snapshot,
not continuously synchronized state. Large views use in-memory JSON and repeated
validation/extraction for correctness; there is no incremental graph cache.

Native Windows execution is not claimed. Existing D.1 mocked branches are retained;
run the full suite on native Windows/NTFS using windows11-ntfs-checklist.md and
add build/report plus --write-generated checks there before asserting native
compatibility. No canonical population of the real repository is needed.

```sh
python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
python -B .ai/tools/kb.py validate --json
python -B .ai/tools/kb.py check-scaffold --json
```

Examples generated from a disposable synthetic fixture are in
../generated/examples/: canonical-graph.json, technical-preview-graph.json,
knowledge-report.json and knowledge-report.txt. The fixture regeneration script is
../tools/examples/graph_demo.py; it seeds example records only in a temporary
repository and prints JSON/text to stdout. It never populates this repository.
