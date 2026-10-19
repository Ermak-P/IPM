# Stage 2 Increment C: read-only canonical proposals

Contract v1.0, its pinned schemas, lifecycle and validator are unchanged.
The separate CandidateNormalizer consumes Increment B output, re-observes the
repository with the existing Scanner and .NET analyzer, and refuses stale or
tampered extraction reports. Only the exact current analyzer output is accepted.
Normalization performs no restore, MSBuild evaluation, project execution, network
access, telemetry, LLM calls, canonical writes, approval or application.

~~~text
python -B .ai/tools/kb.py normalize --json
python -B .ai/tools/kb.py normalize --exclude vendor --json
python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
~~~

The command writes stdout only. Staging validation writes temporary datasets
under the operating system's temporary directory and removes them on completion.
Do not redirect reports into host files. An example may explicitly be saved under
.ai/generated/; it is disposable, never canonical storage or a side registry.
The API is CandidateNormalizer.normalize(root, extraction_report).
An initialized, valid .ai installation and a stable input tree are required.
Exclusions and all Increment A/B security restrictions remain in force.

## Proposed v1 records

Every supported B kind maps to a narrowly worded technical_fact: a source file
exists with a filename-derived label, or a file declares a specific property,
ProjectReference, PackageReference, package version, or solution membership.
Names never imply business rules, component responsibilities or runtime behavior.
All new claims use NEEDS_HUMAN_CONFIRMATION, last_verified=null, and empty
depends_on/conflicts_with arrays. Even a directly observed literal declaration
does not cause automatic confirmation. There is no approval or verification
event invented by the normalizer.

Evidence uses the existing v1 fields only: id, direct-technical type, active
status, root-relative source, extractor actor/method provenance with normalization
method, captured_at, location.reference, description, content_hash and explicit
substantiates. The source bytes, selected declaration, source hash and exact
occurrences are revalidated by the local analyzer before evidence is proposed.
No snippets or complete source files are copied. Conditions and selected metadata
can themselves contain sensitive values; apply the existing exclusions and do
not put credentials in these selected fields.

The location reference contains a deterministic list of XML selectors or solution
declaration locations, with one-based lines/columns. Duplicate occurrences of
the same fact share one evidence record with all locations. Extraction IDs and
resolution details (including lexically resolved target paths) are in disposable
contexts, not extra canonical fields or literal declaration assertions.

Project file existence is distinguished from an XML Project evaluation condition.
A ProjectReference declaration does not establish target existence: the separate
project-file observation can do that. A discovered target is only inventory
resolution, not an evaluated dependency. Conditions and unresolved expressions
remain literal; active evaluated dependencies remain unknown.

## Identity and time policy

The canonical identifier prefix is claim.dotnet or evidence.dotnet, followed by
two SHA-256 components: the subject slot and the declared value. The subject is
source, candidate kind, identifying key (property name, package identifier and
version metadata name, or declared reference path) and exact condition scope.
Source hashes, timestamps, evidence locations, extraction IDs and resolution
status are excluded from IDs. No index or registry is persisted: comparisons use
the canonical records and their stable IDs directly.

Formatting-only edits keep IDs and propose refresh of the same evidence record,
with updated source hash/locations. Substantive changes get distinct fact IDs;
prior records are reported as stale or potentially superseded, never removed.
Inactive evidence is retained and reactivation is a conflict requiring review.
There is no canonical update or historical observation migration in C.

captured_at is the actual UTC clock time immediately after a successful live
re-observation, shared by new/refreshed evidence in that run. An unchanged
canonical observation retains its original captured_at. This is observation time,
not source modification time, approval time, or semantic verification time.
No last_verified date is assigned. There is no option to supply an invented
historical timestamp.

Record IDs, classifications and the complete change_set are deterministic for
unchanged source/canonical inputs. Observation timestamps live in the records
and observation envelope, not the change_set or stable IDs. Thus fresh live runs
can have different captured_at values while producing identical change sets.
With the same observation clock value the entire report is reproducible.

## Comparisons, conflicts and relationships

change_set entries contain record_type, id, classification, reasons, related_ids.
Classifications are add, unchanged, potential update, conflict, unresolved.
They reference the separate records payload; none authorizes application.
Known canonical IDs with different values in the same subject slot are flagged.
Existing confirmed or human-owned knowledge is preserved and conflicting
proposals require review. Exact ID collisions never authorize replacement.
Equivalent existing observations are unchanged without timestamp churn.

Different literal values for the same property/package-version subject and
condition scope are flagged as a candidate conflict. Both narrow declaration
claims can be true (for example, sequential MSBuild property assignments).
The normalizer does not evaluate override order and does not invent canonical
conflicts_with edges. Different condition scopes are kept separate.

Arbitrary human prose is not semantically parsed. Exact statement matches under
another ID, or shared source evidence with unrecognized canonical claims, are
reported as unresolved overlaps, not automatically merged. This does not detect
all possible natural-language contradictions. No exhaustive conflict detection
or semantic proof is claimed.

Missing declarations and changed/unobserved source evidence are reported as
potentially stale, with supporting claims identified. Unobserved can mean removed,
excluded or unsupported; the tool does not guess which. Human records unrelated
to current observations remain unchanged. Retraction/supersession, dependencies,
conflicts, provenance and verification dates in existing records are preserved.

The proposed relationships array is intentionally empty for current B inputs.
Contract v1 permits only claim-level depends_on and conflicts_with. Project
dependency edges provide no direct evidence for those claim semantics, so they
remain in contexts with an explicit limitation. Existing valid v1 relationships
are preserved and validated in the combined context. No project edge types or
parallel graph store are introduced.

## Existing validator and structural versus semantic outcomes

The unmodified kb.validate runs in three isolated staging views using the actual
manifest and schema bytes:

1. Complete existing canonical snapshot.
2. Complete proposed claims, evidence and relationships.
3. Existing plus new IDs, preserving existing records on any ID collision.

Each result includes record counts, errors and warnings. No colliding canonical
record is overwritten even in the combined validation context. Proposed records
are independently validated so preservation cannot hide an invalid proposal.
This combined view is validation context, not an application transaction.
Staging filenames use generated numeric names, never record IDs or host paths.
Invalid canonical records stop processing without repair.

Structural errors are in validation; semantic/resolution issues are in diagnostics
and contexts. ok requires all three views to pass and no input integrity errors.
It does not mean declarations are active dependencies, claims are semantically
proven, conflicts are resolved, or proposals approved. Input failures and
structural errors return exit 1; structurally valid review proposals return 0.

This normalization layer performs no application, approval, rollback, graph
construction or canonical mutation. See population-apply.md for Increment D and
graphs-and-reports.md for the separate Increment E derived views.
