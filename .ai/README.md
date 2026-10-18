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

No scanners, stack analyzers, graph construction, RAG, integrations or automatic
knowledge population are implemented. Stage 2 requires separate acceptance.
