# Stage 2, Increment A: discovery

Increment A implements discovery. Increment B adds the separate
[declared .NET extractor](population-extract.md). Candidate normalization,
approval, population, graph building and the final report command remain future increments.
No Graph Builder exists in Stage 1; none is introduced or replaced here.

From the repository root (Python 3.12+, standard library only):

```text
python -B .ai/tools/kb.py scan --json
python -B .ai/tools/kb.py scan --exclude vendor --exclude 'samples/*' --json
python -B .ai/tools/kb.py scan --root /path/to/repository
python -B .ai/tools/tests/test_acceptance.py
python -B .ai/tools/tests/test_scan.py
python -B .ai/tools/kb.py validate --json
python -B .ai/tools/kb.py check-scaffold --json
```

The Scanner protocol in tools/population_scan.py is the separate discovery
boundary: scan(root, exclusions) returns an inventory dictionary. It does not
produce canonical records or parse/evaluate projects. The .NET analyzer
consumes this inventory in Increment B. Candidate/evidence contracts are
unchanged; no alternative knowledge registry or schema is introduced.

The report_version 1.0 inventory has command, ok, sources, skipped, errors,
warnings, exclusions and counts. Each discovered source has a root-relative
POSIX path and kind: dotnet-project (.csproj), dotnet-solution (.sln), or
dotnet-solution-xml (.slnx). Extensions are matched case-insensitively; paths
are preserved. Malformed project contents remain discovery candidates; only
an analyzer can diagnose their syntax. C# semantic discovery is not implemented.

Every unsupported file is reported as unsupported-source-type. Excluded
directories are reported once as excluded with the matching pattern; their
descendants are neither inspected nor enumerated. Link entries are reported
as link-not-followed, including internal, external and dangling links.
Special files (including FIFOs) are skipped without opening. Traversal errors
produce stable path/reason diagnostics and exit code 1, never a success claim.
Invalid roots or exclusion patterns also fail. Otherwise exit code is 0.
Human output includes counts and the detailed inventory; --json emits one JSON
object. No absolute paths, file contents, timestamps or machine-specific
exception text are included. Identical inventories produce identical JSON.

Exclusions are additive and repeatable; defaults cannot be removed. A pattern
without / matches an entry basename at any depth; a pattern containing /
matches the complete relative POSIX path using Python fnmatchcase semantics
(* can match /). Matching is case-sensitive. A trailing / is ignored.
Absolute patterns, backslashes, colons, control characters and parent traversal
components are rejected. This is not gitignore syntax; there are no negations.
The effective sorted patterns are included in the report. Defaults are defined
in DEFAULT_EXCLUSIONS and cover .git, .ai, common build outputs, caches,
vendored packages, secret filenames and generated filenames.

Scanning requires no initialized .ai, network, packages, LLM, build or project
execution. The CLI writes only stdout, not a report file, and reads directory
metadata only. Do not redirect output into host files. Reports are disposable
and never canonical knowledge. Secret exclusion is name-based, not a guarantee
that arbitrary filenames contain no sensitive information; filenames themselves
appear in reports. Add project-specific exclusions as needed.

All symbolic links and junctions are skipped rather than resolving targets.
The requested root itself must be a real directory, not a link/junction.
Do not scan a concurrently modified tree: traversal is not a filesystem
snapshot or protection against hostile concurrent link replacement. A new
scan reflects removals, but Increment A does not persist history, hash source
contents or report differences from prior inventories.

The format manifest, schemas, schema hashes and Stage 1 version remain 1.0.0.
Manifest capabilities retain the pinned Stage 1 core contract; scan is an
additive CLI extension documented here. init distributes this module, its tests
and this documentation so installed CLIs remain portable. Existing differing
scaffold files are still preserved and reported for manual reconciliation.
