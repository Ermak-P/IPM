# Stage 2, Increment B: declared .NET metadata

Increment B adds a separate static extractor consuming Increment A inventory.
Contract v1.0, the core manifest, schemas, validator and canonical storage remain
unchanged. No canonical claims, evidence or relationships are written. Candidates
are disposable extraction output, not a second knowledge store.

Python 3.12+, standard library only:

~~~text
python -B .ai/tools/kb.py extract --json
python -B .ai/tools/kb.py extract --root /path/to/repository --exclude vendor --json
python -B .ai/tools/kb.py extract
python -B .ai/tools/tests/test_acceptance.py
python -B .ai/tools/tests/test_scan.py
python -B .ai/tools/tests/test_extract.py
~~~

The command first invokes the existing Scanner with additive exclusions, then
passes its inventory to DotNetAnalyzer.extract(root, inventory). The Analyzer
protocol defines this boundary for later language analyzers. The CLI writes
stdout only; reports may be saved explicitly under .ai/generated/. No files
are written by extraction. init distributes the extension and its tests.

## Supported declarations

- .csproj: XML Project, PropertyGroup, ItemGroup, ProjectName, AssemblyName,
  ProjectGuid, TargetFramework, TargetFrameworks, ProjectReference Include and
  PackageReference Include. Framework lists remain declared strings.
- Package versions: Version and VersionOverride attributes and child elements.
  No local version means package-version-not-declared, not an invented version.
- Conditions: Project, group, item and supported metadata Condition attributes
  are retained in outer-to-inner order, never evaluated or combined.
- .sln: Visual Studio format 12.00 Project declarations, including declared name,
  project-type GUID, project GUID and path. Solution folders are skipped.
  UTF-8 (with optional BOM) and BOM-marked UTF-16 are supported.
- .slnx: Solution/Project and Solution/Folder/.../Project membership Path and
  optional Id. Folder names do not alter project path resolution.

Each project has a filename-derived label explicitly marked name_origin=filename.
ProjectName and AssemblyName declarations remain separate property candidates;
neither overwrites that label nor implies an architectural responsibility.
Direct project references are declarations, never inferred transitive edges.
Reference resolution=discovered means only that the .csproj path exists in the
Scanner inventory, not that its XML parsed or that a build would select it.
References not in inventory are diagnosed (missing, excluded, linked, different
path casing or otherwise undiscovered); those cases are not guessed apart.
Only inventory sources are read; referenced files and external imports are
never opened implicitly.

Relative paths accept Windows backslashes and normalize against the declaring
file's directory using platform-independent lexical rules. Drive paths, UNC,
rooted paths, repository escapes, wildcard/list or percent-escaped project references and MSBuild
expressions remain unresolved with explicit diagnostics. Non-C# project targets
are unsupported. Path matching remains exact and case-sensitive on every OS.

## Output and identities

The extraction report contains analyzer, report_version, ok, counts, candidates,
diagnostics, limitations and the original scan report. A candidate contains:

- id: dotnet. plus SHA-256 of analyzer version, source path, kind, declared
  value and conditions serialized with sorted keys. Reference resolution status
  is excluded so target removal does not rename an unchanged declaration.
- kind: project, project_property, project_reference, package_reference,
  package_version or solution_membership.
- source: repository-relative POSIX path.
- value and conditions: only the supported declared metadata.
- interpretation: declared-not-evaluated.
- evidence: source path, XML selector or solution declaration selector,
  one-based line and column, SHA-256 of the source bytes and actor/method
  provenance. XML locations are start tags; version attributes use their
  owning element's location.

Candidates intentionally have no canonical claim status, evidence status,
captured_at or last_verified. An extraction is not a confirmation event.
Canonical normalization and contract validation belong to Increment C, which
is not implemented here; future normalization must use Contract v1.0 rather
than treating this transport output as validated canonical records.

Equivalent declarations have stable IDs across traversal order, metadata
formatting, line shifts, and XML attribute order. Only surrounding metadata
text whitespace is trimmed; conditions are retained verbatim. Equivalent
declarations in the same source aggregate occurrence evidence and produce a
duplicate-declaration diagnostic. Reordering occurrences can change evidence
locations, but not IDs. Source-byte hashes change on formatting-only edits.
Substantive value changes change IDs; no history or incremental state is stored.
Removed files disappear on a fresh scan; a stale inventory produces a source
read error. No canonical record is silently deleted.

## Safety and limitations

The XML parser uses standard-library Expat callbacks, rejects DTD declarations
before entity expansion, and rejects entity declarations, external entity
requests and undefined entities. UTF-16 cannot bypass DTD rejection. The parser
never resolves schemas, XInclude, URLs or external resources. Supported XML
namespaces are absent or the legacy MSBuild namespace. Namespace extensions
are rejected. Input is bounded to 2 MiB per file, 20,000 XML elements, 128 nested
elements and 4,096 serialized characters per candidate value/conditions.
Oversized or malformed inputs produce diagnostics and nonzero exit status.

Extraction checks all source path components against links/junctions and scan
exclusions before opening regular files. Special files are rejected. POSIX
O_NOFOLLOW is used where available. As in Increment A, a stable input tree is
required: protection from hostile concurrent filesystem replacement is not
guaranteed. Secret handling uses the existing exclusions. Evidence copies no
source snippets or complete files; only selected metadata is emitted. Do not
put secrets in project names, dependency values or conditions: these selected
fields are intentionally reported.

No SDK, MSBuild, restore, targets, project scripts, network, telemetry or LLM is
invoked. Imports (including implicit Directory.Build.props/targets and SDK
imports), central package management, Choose/When, Update/Remove/Exclude,
unknown properties/items, nested metadata and semantic C# analysis are not
evaluated. They produce diagnostics where encountered. The extractor does not
claim complete evaluated dependencies or framework coverage: for example, this
host's frameworks reside in Directory.Build.props and remain undiscovered.
SLN parsing covers membership declarations, not full solution validation,
configuration activation, SolutionItems, build order or ProjectDependencies.
SLNX configuration/build metadata is diagnosed as unsupported.

ok means no scan/input/parser errors; warnings may still include unresolved or
unsupported declarations. Malformed XML contributes no candidates from that
file. Valid declarations in other files remain available in an error report.
An invalid/incomplete scan inventory prevents extraction. Errors yield exit 1;
otherwise exit 0. Structural parsing never proves semantic truth.

Platform tests use Windows-style reference strings on every OS. FIFO tests are
guarded by os.mkfifo availability. Symlink tests skip explicitly when the OS or
user cannot create links. Native Windows execution must be reported separately
from these portable tests.

No populate, approval, canonical normalization, graph builder or final report
command is added. Increment C must wait for review and acceptance of B.
