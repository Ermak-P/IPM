# Stage 3.2 — read-only existing knowledge inspector

The implementation follows the reviewed Stage 3.1 assessment in
existing-knowledge-compatibility.md. It is an inspector, not an installer,
migration/conversion adapter, validator replacement or integration activation.
Contract v1.0, manifest and all canonical schemas remain unchanged.

## Run from a trusted external checkout

```sh
python -B /trusted/IPM/.ai/tools/kb.py inspect-compatibility --root /existing/project --json
python -B /trusted/IPM/.ai/tools/kb.py inspect-compatibility --root /existing/project
```

API: `CompatibilityInspector().inspect(Path('/existing/project'))` from
`tools/compatibility_inspector.py`. The inspected project need not contain the
universal scaffold, a recognized manifest or Python tools. No init is called.
Only --root and --json apply; population, graph-view, output-write and exclusion
options are rejected. There is no output-path flag: stdout only. An external
caller may save stdout in a separately approved location, never by assuming a
foreign generated/ directory is disposable.

The command deliberately inspects foreign transaction-state metadata without
entering the universal normal-operation lock or treating unknown journals as
universal receipts. It never opens a coordination lock for writing and cannot
recover or activate anything. Any .ai/state/population path is an explicit
operation blocker requiring ownership/protocol review, including an empty or
apparently committed tree. This is diagnostic access only; it grants no bypass
for existing validate, build, report, normalize or populate recovery gates.

The trusted scaffold installer includes the new module/tests/docs and the
existing synthetic fixture bundle for portability of installed tooling/tests.
Its existing preservation rules are unchanged. This packaging update does not
make inspect-compatibility install anything; no new integration installer or
installation mode was implemented.

## Snapshot and inventory

Scope is **the existing .ai subtree**, not arbitrary host source files or the
entire repository. The API field repository_snapshot_fingerprint explicitly
states its scope. Every observed entry includes root-relative POSIX path, object
type, provisional role/ownership, content fingerprint when safely available,
occupied framework-path flag and disposable=false. Directories have no content
hash. Source/domain/decision/evidence/tool locations are identified structurally
by directories, not inferred from natural-language contents. Other locations are
unknown and preserved.

Inventory uses lstat, checks ancestors for symlinks/junctions, opens regular files
read-only with available O_NOFOLLOW/O_NONBLOCK protections, compares descriptor
identity and metadata before/after reads, then repeats the bounded inventory at
the end. Changed bytes, entries, identity or observable stat metadata make
inspection incomplete. File handles are closed on completion/error. Final stat
comparisons include mtime/ctime and inode identity in memory; those variable
values are not serialized into the content-based fingerprint or report.

Stable inputs produce deterministic node-free inventory/report JSON: sorted paths,
diagnostics, tool metadata and schema declarations; no current timestamps,
absolute target root, source snippets or complete source-file contents. No graph
is built. Snapshot hash uses canonical JSON of paths/types/roles/hashes/coverage
metadata; derived occupied-path labels are excluded from the hash. Copying an
identical .ai tree to another root preserves its content fingerprint.

Limits per pass: 4096 inventory entries (enumeration and queued work bounded),
32 directory levels, 1 MiB per file, 32 MiB total hashed bytes; strict JSON is
bounded to depth 48 and 50,000 values. Limits are fixed constants, not overrides
that can disable security defaults. JSON duplicate keys, nonfinite numbers,
nonobjects and malformed encodings are rejected as unsupported structured data.
JSON parser resource-limit failures also make coverage incomplete.

Links/junctions, hardlinks, special files, unreadable/changing paths, unsafe names
or exceeded inventory/content limits are diagnosed without unsafe traversal/read.
Casefold/NFC path aliases are reported conservatively without renaming anything.
Sensitive/cache names (.env variants, secret/credential directories, key/cert
extensions, .git, node_modules, __pycache__, .venv, .cache) are inventoried but not
read/traversed. Such exclusions make coverage explicitly incomplete. Filename
exclusions are not secret detection; selected paths/IDs/declared IO metadata can
itself be sensitive and owners must review reports before sharing.

Portable checks require a stable trusted tree. They detect observable races,
not malicious same-user ancestor swaps or changes after the final check. Reading
may update filesystem access-time metadata according to OS mount policy; the tool
requests no writes or timestamp changes. Byte contents/record lifecycle remain
unchanged. Native Windows/NTFS behavior remains a separate open acceptance gate.

## Supported metadata; no conversion

- Manifest: .ai/manifest.yaml is inspected only if it is a bounded UTF-8 JSON
  object (the same JSON-compatible YAML subset as v1). An exact v1 declaration
  is identified but accepted_as_contract=false and integration_approved=false.
  Foreign JSON is classified without treating it as v1. YAML syntax outside the
  subset is reported unsupported; no YAML constructors are executed.
- Schemas: JSON objects under schema/ and identifiable *.schema.json files are
  compared with the trusted pinned v1 schemas and known dialect URI. Foreign
  schemas/regexes are never evaluated, imported or fetched. Arbitrary schema
  $id/$schema content is not copied into reports.
- Records: strict JSON objects in knowledge/claims, evidence and
  knowledge/relationships. V1-shaped objects get existing kb.schema_errors
  checks against trusted pinned schemas, plus explicit ID/reference/lifecycle
  diagnostics. Only error counts and known missing-field names are emitted,
  not arbitrary foreign property names or record prose.
- Harbor Tickets format harbor-team-architecture/revision=3 additionally permits
  literal id/kind/state/support/supports field diagnostics for the synthetic
  profile. Illegal IDs and unrecognized labels remain unchanged; component calls
  remain unsupported claim relationships. No field or status is converted.
- Unknown record shapes, non-JSON record/schema formats, Markdown/YAML prose,
  scripts, binary data and arbitrary configs are never semantically interpreted.
  Opaque files are fingerprinted when safe; unknown contents and unsupported
  structured forms remain explicit review items.

For recognized records the inspector diagnoses global duplicate IDs, missing,
ambiguous or wrong-kind references; v1 self-links, asymmetric conflicts, dependency
cycles, mismatched/duplicate explicit relationship edges and insufficient direct
support for CONFIRMED claims where the known schema makes those checks possible.
Missing fields/provenance/verification data are reported, never manufactured.
Business rules retain the requirement for active direct-authoritative evidence;
inactive/supporting evidence does not become confirmation. Valid historical
fields are not modified. This is partial structural compatibility diagnosis,
**not** complete canonical validation, source authentication, semantic truth,
verification or migration approval. The existing validate command remains the
canonical validation interface; canonical_validation_performed=false is explicit.

## Graph Builder ownership

Discovery is deliberately nonexecuting and conservative:

1. A JSON manifest graph_builder path is a declaration, not an executable command.
2. A bounded tools/graph-contract.json object can declare entrypoint, input paths,
   output path and owner. Paths must be bounded safe relative references; parent
   traversal, URLs, drive paths or command strings are not followed/executed.
3. Script/binary filenames containing graph under tools/ are candidates regardless
   of whether they occupy the framework's tools/knowledge_graph.py path.

Declarations are retained per origin; conflicting owner declarations remain
unresolved, not chosen by order. A declared owner is not authenticated ownership.
Missing targets and unsafe declared paths get diagnostics. Every possible graph
builder overlap blocks operation with graph-builder-ownership-selection-required.
Tools can be undeclared, named unexpectedly or built outside .ai; discovery is
not exhaustive. Unknown tool ownership is also explicit.

No tool source is imported or executed; no Graph Builder is installed or activated.
No component call/ProjectReference is turned into canonical claim depends_on.
Human decisions explicitly retain canonical-versus-declared-technical-preview
trust boundaries. The Harbor sentinel stays inert; it is fictional ownership test
data, not a second canonical store or another graph implementation.

## Output/exit contract

JSON fields include inspection_format=existing-knowledge-compatibility,
inspection_version=1.0, scoped initial/final fingerprints, inventory/summary,
provisional_ownership, manifest/schema declarations, recognized_capabilities,
graph_tools, diagnostics, blockers, unresolved_human_decisions and
suggested_integration_mode. No canonical records or complete file payloads are
emitted. Selected ID/path/owner metadata is bounded; unsupported values are
omitted or represented by fingerprints.

`ok`/`complete` mean the bounded filesystem inventory and final comparison
completed safely. They do not mean all formats were understood or knowledge is
compatible: malformed/unsupported structured files remain explicitly diagnosed
opaque entries even in a complete inventory. Secret/cache exclusions, inaccessible
objects, links, resource-limit failures or observed changes yield complete=false.
CLI exit **0** means completed inspection, even with blockers; exit **1** means
incomplete/unsafe/changed inspection, not integration authorization. Invalid CLI
options exit **2**. JSON is returned for failures. Human output summarizes entry
count, mode and blockers; --json gives full detail.

All diagnostics are conservative integration blockers requiring review; their
scope distinguishes inspection failure, operating-state/tool blockers and ordinary
integration/ownership risks. No review decision is automatically granted.

| Suggested mode | Meaning |
| --- | --- |
| read-only-source-analysis | No operation/inspection blocker found and .ai absent or manifest exactly matches v1; still no integration approval or assurance about source-scanner support |
| read-only-compatibility-inspection | Complete foreign/missing manifest inspection without discovered graph/state/unsafe-operation blocker; use diagnostics and owner review, not migration |
| integration-blocked | Discovered graph responsibility/state conflict or incomplete/unsafe/changed inspection requires resolution before progressing |

Mode is advice only. It never activates existing commands, bypasses recovery,
confirms claims or declares full integration compatibility. There is no Stage 3.3.

## Harbor example and regression

Example: ../generated/harbor-compatibility-inspection.json, produced from the
unchanged 19-file Harbor Tickets bundle in a disposable directory. Only its .ai
subtree is inspected: **30 entries, 17 files, 13 directories, five recognized
legacy records**, one graph-tool entrypoint. The inspector reports foreign
manifest/custom schema, occupied paths, invalid legacy IDs/lifecycle and missing
v1 fields/provenance, unsupported component relationships and protected
potentially durable generated/state content. Ownership remains unknown-provisional;
mode is integration-blocked, despite a complete read-only inspection. Raw
business/architecture prose and tool/source contents are not copied.

```sh
python -B -m unittest discover -s .ai/tools/tests -p 'test_compatibility.py'
python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
python -B .ai/tools/kb.py validate --json
python -B .ai/tools/kb.py check-scaffold --json
```

The fixture bundle is copied as test data when installing the trusted scaffold,
never expanded into the target's canonical directories by the inspector. Tests
materialize it only in disposable repositories. The example can be regenerated
without init or population:

```python
import json, subprocess, sys, tempfile
from pathlib import Path
cli = Path('.ai/tools/kb.py').resolve()
bundle = json.loads((cli.parent / 'examples/existing-knowledge/fixture.json').read_text())
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    for name, text in bundle['files'].items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    run = subprocess.run([sys.executable, '-B', str(cli), 'inspect-compatibility',
                          '--root', str(root), '--json'], capture_output=True,
                         text=True, check=True)
    print(json.dumps(json.loads(run.stdout), indent=2, sort_keys=True))
```

No real canonical population, migration, graph replacement, schema/status
conversion, approval, restore, network/LLM or discovered project/tool execution is
part of this inspector. Native Windows/NTFS execution remains NOT TESTED here;
portable Windows guards/tests do not substitute for the native acceptance gate.

## Executed Stage 3.2 verification

Baseline: a04ce1b51a9799b4b356aacef5930c583d3a0ac8, branch work,
Linux x86_64 / Python 3.12.14 / pinned .NET SDK 10.0.402.
This command is an optional CLI extension; the pinned core manifest is unchanged.

- Baseline Python: 209 passed, 0 failures/errors/skips.
- Final `python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'`:
  **252 passed, 0 failures/errors/skips**, including 43 new inspector tests.
- Existing .NET tests via `dotnet vstest` on the two existing net10.0 test DLLs:
  **27 passed** (12 unit + 15 integration), 0 failed/skipped, no build/restore.
- validate, check-scaffold, version and git diff --check: exit 0.
- Harbor CLI output repeated byte-identically; example regenerated from a
  temporary fixture with no installation, apply, tool activation or writes there.
- SHA-256 comparison: 1148 existing host files and 11 canonical/schema/source-
  metadata/manifest files unchanged; no host files added or removed. Harbor bundle
  and Stage 3.1 assessment unchanged. No real population apply performed.
- Core validator, strict canonical JSON parser, existing path checks and installer
  function bodies remain identical. CLI dispatch/packaging registry was extended;
  A–E/D.1 modules and all pre-existing tests are unchanged.
- The portable junction branch test is simulated; native Windows/NTFS is
  **NOT TESTED**, and its acceptance gate remains open.

Changed files: tools/compatibility_inspector.py, tools/tests/test_compatibility.py,
tools/kb.py, docs/compatibility-inspector.md, README.md and the disposable example
generated/harbor-compatibility-inspection.json. No Stage 3.3 work was started.
