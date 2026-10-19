# Universal Architecture Knowledge Base — Stage 1

This .ai directory is the sole canonical architecture knowledge base. The host
project owns its build, CI, settings and agent instructions. This scaffold does
not modify them. No host dependencies, network access or LLM calls are needed.

Requires Python 3.12 or later, standard library only. Use any local Python
interpreter; no installation into the host project is required.

From the host repository root:

```text
python -B .ai/tools/kb.py version
python -B .ai/tools/kb.py validate --json
python -B .ai/tools/kb.py check-scaffold --json
python -B .ai/tools/tests/test_acceptance.py
```

Install into another existing directory using:
`python -B /path/to/this/.ai/tools/kb.py init --root /path/to/host --json`.
The installer copies its explicitly listed scaffold files, not this repository's
claims, evidence, state, generated outputs or verification reports. Retain the
complete distribution as the installer source. Installation creates only .ai.
No command requires interactive input. Zero means success; nonzero means error.
Human and JSON output contain deterministic diagnostics and explicit limitations.

An unrecognized nonempty .ai is a conflict, even if it lacks the expected files.
A recognized installation can have missing scaffold files restored. Different
existing scaffold content is preserved and reported for manual reconciliation;
there is no force/overwrite mode. Symlinks and Windows junctions anywhere under
.ai are rejected. Do not run against a concurrently modified target tree.
check-scaffold verifies current completeness, manifest, schemas and records.
It cannot reconstruct historical changes to host files; acceptance tests compare
host snapshots to demonstrate installation safety.

- knowledge/claims and knowledge/relationships: schema-validated JSON records.
- knowledge/domains, decisions, open-questions: canonical human-authored Markdown.
- evidence/: provenance and source references, not copied host source files.
- sources/: human-authored source metadata and access rules.
- generated/: disposable reproducible outputs; no unique knowledge belongs here.
- state/: technical execution metadata only, never decisions or durable explanations.
- docs/: lifecycle, evidence rules, versioning and the approved baseline contract.
- tools/examples/: synthetic examples, not claims about the host.
- tools/tests/: offline acceptance tests in disposable synthetic repositories.

validate reads record directories recursively and never changes records or status.
Each record is a UTF-8 JSON object in a .json file; duplicate JSON keys, unknown
fields and unsupported record formats are rejected. IDs are globally unique.
The manifest uses JSON syntax, a YAML 1.2 subset; other YAML syntax is deliberately
not supported by this dependency-free v1 CLI.

Stage 2 Increment A adds read-only discovery through
`python -B .ai/tools/kb.py scan --json`. See
[discovery usage and boundaries](docs/population-scan.md).
Increment B adds declared .NET metadata extraction through
`python -B .ai/tools/kb.py extract --json`; see
[extraction usage and limitations](docs/population-extract.md).
Increment C adds read-only v1 proposals and isolated validation through
`python -B .ai/tools/kb.py normalize --json`; see
[normalization, time policy and review limitations](docs/population-normalize.md).
Increment D adds explicitly approved add-only population through
`python -B .ai/tools/kb.py populate prepare --json`; see
[approval, transaction states and recovery](docs/population-apply.md).
The manifest lists pinned core capabilities; scan/extract/normalize/populate/build/report are optional CLI
extensions listed by --help, without a canonical format version change.
Increment E adds disposable canonical and technical-preview graphs and reports:
`python -B .ai/tools/kb.py build --json` and `python -B .ai/tools/kb.py report`;
see [graph semantics and trust boundaries](docs/graphs-and-reports.md).
RAG and integrations are not implemented. Population always
requires exact-plan approval; it does not confirm claims. Canonical contracts remain v1.0.

Stage 3.2 adds strictly read-only inspection of independently owned `.ai`:
`python -B .ai/tools/kb.py inspect-compatibility --root /existing/project --json`.
No installation, migration or graph activation is performed; see
[scope, output, ownership and safety limits](docs/compatibility-inspector.md).

Stage 3.3 provides bounded read-only compatibility proposals for explicit synthetic
formats: `python -B .ai/tools/kb.py adapt-compatibility --root /synthetic/project --json`.
See [mapping rules, closure validation and blocking policy](docs/compatibility-adapter.md).
Proposals never authorize migration, canonical insertion or graph activation.
