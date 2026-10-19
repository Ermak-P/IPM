# Stage 3.4 — clean independent deployment

This procedure deploys framework tools and **empty** Contract v1.0 directories.
It never transfers synthetic project knowledge, current observations, generated
reports, prepared plans, approval receipts or transaction state. It does not
migrate/adopt legacy records, execute their tools or authorize population.
All corporate sources/knowledge/reports stay on local, approved storage: no
external API, LLM provider, network upload, package restore or telemetry.

## Package and classification

Build in the trusted development checkout (Python 3.12+, stdlib only):

```sh
mkdir -p .ai/generated/deployment
python -B .ai/tools/deployment_package.py \
  --output .ai/generated/deployment/ua-kb-clean.zip \
  --inventory .ai/generated/deployment/included-excluded-files.json
```

The output parent must exist; differing existing artifacts are refused, not
silently overwritten. To rebuild after changing source, explicitly choose a new
output filename or remove only your own approved disposable old build output.
The source repository and its fixtures/state are never deleted or rewritten.
The package generator is build-only tooling, not a target-repository installer.
The inventory is an external development audit, not a file to copy into IPM.

| Current .ai category | Deployment policy |
| --- | --- |
| Reusable framework code/contracts | Allowlisted runtime CLI/modules and byte-identical v1 manifest/schemas/contracts included; build-only package generator excluded |
| Required scaffold files | Clean README, fixed runtime registry/profile, original .gitignore, standard directories and newly emitted empty .gitkeep files; no original canonical directory contents copied |
| Framework tests/documentation | Operational/lifecycle/format docs included; development tests and historical acceptance/assessment reports excluded because they depend on synthetic fixtures or contain observations |
| Synthetic sample data | All tools/examples content, demos, Harbor bundle and any current knowledge/evidence/source contents excluded regardless of validity |
| Generated artifacts | All current graphs, scan/extract/normalize/population reports and prior packages excluded; generated/ starts with an empty marker only |
| Runtime state/plans/journals | All state contents, coordination locks, prepared plans, receipts/journals and verification history excluded; state/ starts with an empty marker only |

Every current development .ai file is classified in the external inventory,
including ignored local state. Unknown/unsafe objects fail the build for review.
Excluded source bytes and plan contents are not read into the archive. The audit
lists excluded paths/reasons, not source/project knowledge or approval contents.
Its inventory reflects the source tree at build time and may change as new
artifacts appear; it is not the runtime package manifest. Do not publish local
inventories if their filenames/paths are sensitive.

ZIP bytes are reproducible for identical runtime inputs: sorted ASCII paths,
fixed 1980 ZIP timestamps, fixed file/directory attributes, ZIP_STORED (no zlib
version dependence), no clocks, source absolute paths or commit IDs in payload.
`.ai/deployment-profile.json` contains included payload hashes and exclusion
policy. Its own integrity is covered by the trusted outer ZIP SHA-256; it is not
an independent cryptographic signature. Runtime state/observations are absent.

## Why this is an explicit runtime profile

The development CLI FILES registry requires examples/tests. Copying it unchanged
while removing those files makes init/check-scaffold fail, while copying its
fixtures violates clean-deployment requirements. The package therefore replaces
**only** DIRECTORIES/FILES/PLACEHOLDERS declarations in the archive copy of kb.py.
An AST guard verifies every other statement, including all function bodies, is
identical to the original. The development kb.py/registries are unchanged.
Runtime registry includes all eight execution modules and operational docs,
keeps standard in-repository .ai storage and empty tools/examples/tools/tests
directories, and excludes the fixture-specific subdirectory. There is no new
external-store option or modified canonical schema/validator.

All twelve existing CLI command families remain present. Runtime init creates
the same clean profile in another empty host; it does not reintroduce examples.
Ordinary collision/foreign-manifest protections remain in force. Packaged
check-scaffold validates the explicit runtime registry; core validate still uses
the exact same Contract v1.0. This is a distribution profile, not a new canonical
format. Package metadata is tooling configuration, never project knowledge.

Development tests remain in the full checkout. Do not run unittest discovery on
the empty runtime tests directory and claim acceptance from a zero-test result.
Run the full regression suite from the separate development checkout, offline.
The included D.1 Windows checklist likewise requires that development checkout
and disposable fixtures, never real IPM population.

## Preserve legacy by separating evaluation copies, not renaming live data

Do **not** extract over a pre-existing .ai, run init to replace it, or merge
subdirectories. The recommended first deployment is:

1. Preserve the original repository and its .ai byte-for-byte. No in-place rename,
   deletion, chmod or schema replacement there.
2. Create a **new evaluation copy** of its host files, excluding the original .ai
   and .git. This is an explicitly authorized new copy, not a rewrite of the
   original. Inventory every copied host file before deployment.
3. Copy legacy .ai to a separate **sibling review root** containing .ai; mark only
   that new snapshot read-only and record hashes. Keep it outside the evaluation
   source root so existing source scanners cannot discover old/generated sample
   projects. Do not modify legacy provenance/relative references to make them work.
4. Verify package hash and paths, unpack into a new staging directory, then place
   its complete .ai only in the evaluation copy where .ai is absent.
5. Validate emptiness/scaffold and compare original, copied host and legacy hashes.
   Treat legacy as historical read-only reference, not a second synchronized
   universal store or automatically accepted truth. The new canonical store is
   deliberately empty and independent.

Both the clean store and review snapshot use the existing `<root>/.ai` layout;
--root selects a repository/review root, not an external canonical-store path.
No new storage layout or migration-apply mechanism is implemented. A later actual
rollout to a working repository requires separate owner authorization and native
platform acceptance. The original repository remains available unchanged.

## Windows 11 PowerShell installation instructions (NOT EXECUTED natively)

Use native Python 3.12+ on local NTFS, a trusted locally built ZIP and a SHA-256
record obtained from the trusted build. Do not use cloud-synced directories, SMB,
external services or upload corporate data. Run PowerShell with ordinary user
rights and no restore/build. Use fresh nonoverlapping directories; failures stop.
The paths below are placeholders, not actual corporate locations.

```powershell
$ErrorActionPreference = 'Stop'
$python = (Get-Command python.exe).Source
$source = [IO.Path]::GetFullPath('C:\Local\IPM-original')
$target = [IO.Path]::GetFullPath('C:\Local\IPM-clean-evaluation')
$legacy = [IO.Path]::GetFullPath('C:\Local\IPM-legacy-review')
$zip = [IO.Path]::GetFullPath('C:\Local\trusted-build\ua-kb-clean.zip')
$expectedSha256 = '<SHA-256 recorded by the trusted offline build>'
& $python --version
if ($LASTEXITCODE -ne 0) { throw 'Python unavailable' }
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha256.ToLowerInvariant()) {
    throw 'Package hash mismatch'
}
if (!(Test-Path -LiteralPath (Join-Path $source '.ai') -PathType Container)) { throw 'Legacy .ai not found' }
foreach ($path in @($target, $legacy)) {
    if (Test-Path -LiteralPath $path) { throw "Destination already exists: $path" }
}
foreach ($a in @($source, $target, $legacy)) {
    foreach ($b in @($source, $target, $legacy)) {
        if ($a -ne $b -and $a.StartsWith($b.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Roots must not be nested'
        }
    }
}

# Do not follow reparse points while preflighting the source tree.
function Assert-NoReparseTree([string]$root) {
    if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked root' }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($root)
    while ($pending.Count) {
        $directory = $pending.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $directory -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point requires review: $($item.FullName)" }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}
Assert-NoReparseTree $source

function File-Snapshot([string]$root) {
    $items = @{}
    foreach ($file in Get-ChildItem -LiteralPath $root -File -Recurse -Force) {
        $relative = $file.FullName.Substring($root.TrimEnd('\').Length + 1)
        $items[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
    return $items
}
function Assert-SameSnapshot($before, $after) {
    if ($before.Count -ne $after.Count) { throw 'File set changed' }
    foreach ($key in $before.Keys) {
        if (!$after.ContainsKey($key) -or $before[$key] -ne $after[$key]) { throw "Bytes changed: $key" }
    }
}
# Keep validator staging and every later private report outside all project roots.
$privateTemp = Join-Path (Split-Path $target -Parent) ('kb-private-temp-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $privateTemp | Out-Null
$env:TMPDIR = $privateTemp
$env:TEMP = $privateTemp
$env:TMP = $privateTemp
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:TESTINGPLATFORM_TELEMETRY_OPTOUT = '1'
$sourceBefore = File-Snapshot $source
New-Item -ItemType Directory -Path $target, $legacy | Out-Null
& robocopy $source $target /E /XJ /R:0 /W:0 /XD (Join-Path $source '.ai') (Join-Path $source '.git')
if ($LASTEXITCODE -ge 8) { throw 'Host copy failed' }
& robocopy (Join-Path $source '.ai') (Join-Path $legacy '.ai') /E /XJ /R:0 /W:0
if ($LASTEXITCODE -ge 8) { throw 'Legacy snapshot copy failed' }
Assert-SameSnapshot (File-Snapshot (Join-Path $source '.ai')) (File-Snapshot (Join-Path $legacy '.ai'))
Get-ChildItem -LiteralPath (Join-Path $legacy '.ai') -File -Recurse -Force | ForEach-Object {
    $_.IsReadOnly = $true  # New snapshot only; never the original.
}
$hostBefore = File-Snapshot $target
$legacyBefore = File-Snapshot $legacy

# Validate archive names/objects before extraction; no overwrite mode.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
$names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
try {
    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName
        if (!$name.StartsWith('.ai/', [StringComparison]::Ordinal) -or $name.Contains('\') -or $name.Contains(':') -or
            ($name.Split('/') -contains '..') -or ($name.Split('/') -contains '.') -or !$names.Add($name)) {
            throw 'Unsafe/duplicate ZIP entry'
        }
        if ((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'ZIP symlink rejected' }
    }
} finally { $archive.Dispose() }
$stage = Join-Path (Split-Path $target -Parent) ('kb-stage-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
Expand-Archive -LiteralPath $zip -DestinationPath $stage
if (Test-Path -LiteralPath (Join-Path $target '.ai')) { throw 'Occupied .ai; preserve it' }
[IO.Directory]::Move((Join-Path $stage '.ai'), (Join-Path $target '.ai'))
Remove-Item -LiteralPath $stage  # Empty staging directory only.

$cli = Join-Path $target '.ai\tools\kb.py'
foreach ($command in @('version', 'validate', 'check-scaffold')) {
    & $python -B $cli $command --root $target --json
    if ($LASTEXITCODE -ne 0) { throw "$command failed" }
}
& $python -B $cli populate status --root $target --json
if ($LASTEXITCODE -ne 0) { throw 'Status failed' }
foreach ($area in @('knowledge', 'evidence', 'sources', 'generated', 'state')) {
    $unexpected = @(Get-ChildItem -LiteralPath (Join-Path $target ".ai\$area") -File -Recurse -Force |
                    Where-Object Name -ne '.gitkeep')
    if ($unexpected.Count) { throw "Store is not empty: $area" }
}
Assert-SameSnapshot $sourceBefore (File-Snapshot $source)
Assert-SameSnapshot $legacyBefore (File-Snapshot $legacy)
$after = File-Snapshot $target
$hostAfter = @{}
foreach ($key in $after.Keys) { if (!$key.StartsWith('.ai\', [StringComparison]::OrdinalIgnoreCase)) { $hostAfter[$key] = $after[$key] } }
Assert-SameSnapshot $hostBefore $hostAfter
```

Record native OS/Python/NTFS/ACL/path/AV versions, actual commands/exit codes,
file counts/hashes and validator results. Read-only attributes are an accidental-
write guard, not hostile-user isolation. Do not suppress errors or change ACLs to
obtain a pass. Snapshot checks detect observable concurrent changes; they are not
cross-file atomicity or a substitute for a quiescent input tree. Interrupted
copy/extraction leaves only new evaluation/staging roots: preserve them for review,
never restore by overwriting the original. Any later cleanup must be explicitly
limited to your unchanged disposable copies; original and legacy are not rollback
material. No real populate apply is part of these commands.

## Read-only real-IPM reconstruction workflow

Use only the clean evaluation root and the read-only legacy review root. Keep
reports on an explicitly approved local path outside the inspected legacy .ai.
Do not send source text, reports, keys or knowledge to external APIs/LLMs. Run
Python with -B; no project execution, MSBuild evaluation or restore is needed.
Keep TMPDIR/TEMP/TMP on approved private storage outside the source, evaluation
and legacy roots, as above: existing validation helpers use OS temporary staging.
Do not point temporary directories or report redirections inside those roots.

1. **Record baselines and privacy boundaries.** Capture exact local source revision,
   file hashes, legacy paths/manifest/owners and approved documentation locations.
   Verify that copied host files and legacy still match their original baselines.
   Legacy URI bases may refer to the original tree: retain that ambiguity until
   an owner identifies the actual source. Do not rewrite references silently.
2. **Analyze source declarations only:**

   ```powershell
   & $python -B $cli scan --root $target --json
   & $python -B $cli extract --root $target --json
   & $python -B $cli normalize --root $target --json
   & $python -B $cli build --view technical-preview --root $target --json
   & $python -B $cli report --root $target --json
   ```

   Check every exit code and retain stdout privately. No --write-generated is
   necessary. Normalize proposes technical facts with evidence; it does not write
   canonical knowledge. Declared dependencies/conditions are not runtime
   dependencies, business rules or architectural responsibilities. Inherited
   MSBuild values, imports and semantic C# behavior remain unevaluated. Keep
   any additional archived/generated source roots outside the target or explicitly
   excluded using existing --exclude options; do not weaken default exclusions.
3. **Inspect the legacy knowledge without adoption:**

   ```powershell
   & $python -B $cli inspect-compatibility --root $legacy --json
   ```

   Review provisional ownership, unknown/durable generated/state contents,
   graph-builder responsibility, manifest/schema and reference/lifecycle risks.
   Do not call init on legacy. It stays read-only and is not active canonical
   input to the new graph/report. The old Graph Builder is not executed/replaced.
4. **Verify each legacy assertion manually, with owners.** Maintain a local review
   worksheet outside canonical directories: original ID/source/hash and exact
   assertion; source revision; precise code/declaration locations; authoritative
   document/decision and its authority; original evidence/provenance/status; actual
   observation/verification actor/time only when genuinely available; outcome
   supported/contradicted/ambiguous/unverifiable; missing requirements and reviewer
   decision needed. Tool structural checks cannot fill these semantic decisions.
   Code structure alone cannot confirm business rules or architectural intent.
   A meeting-note label, project name or legacy approved flag is not proof of
   authority. Missing sources/timestamps/provenance remain unresolved; preserve
   original and contradictory perspectives, never silently overwrite/retract.
5. **Propose only representable knowledge, do not populate.** Source normalize
   output supplies narrowly formulated technical proposals. The existing
   adapt-compatibility command is usable only for its documented Harbor revision 3
   synthetic or exact v1 formats; it is **not** a corporate schema converter.
   Unknown real-IPM formats require a separately reviewed format/adapter scope,
   not pretending they are Harbor or changing their manifest. If a compatible
   format genuinely applies, safe proposals may be inspected with:

   ```powershell
   & $python -B $cli adapt-compatibility --root $legacy --json
   ```

   For manually authored review proposals, use the existing unmodified validator
   in an isolated temporary v1 staging layout outside both roots (the documented
   normalization validate_records interface is available in tools/). Never copy
   review candidates into the active .ai just to validate them. Missing required
   evidence/provenance/time prevents a valid proposed record. A genuine reviewed
   claim may eventually carry its real event; never invent one. Keep metrics
   and proposed v1 records outside canonical, not as a second synchronized store.
6. **Expose remaining unknowns.** List every unsupported/blocked/unverifiable
   assertion and its specific missing evidence, authority, identity, reference or
   semantic requirement. Preserve graph ownership blockers and canonical vs
   technical-preview trust labels. An empty canonical graph is correct until a
   separately authorized population stage; successful structural validation is
   not insertion approval. Do not run populate prepare/apply for real IPM in this
   deployment task and do not implement a migration-apply mechanism.

## Acceptance evidence and open gates

The separate development regression suite and test_deployment.py exercise package
reproducibility, exclusions, registry-only transformation, fresh validation and
all runtime command families in disposable roots. A six-project .NET host copy
with pre-existing Harbor legacy .ai is preserved separately; a clean evaluation
copy produces seven scan sources, 29 extracted/normalized technical claims, zero
canonical records, separate graphs and zero inherited state. Snapshot hashes of
the original host/legacy, read-only legacy copy and evaluation host match after
all read-only commands. New runtime init remains empty and idempotent.

Native Windows 11/NTFS is **NOT TESTED** here. Remaining gates include executing
the PowerShell procedure with private data only on approved local storage; native
ZIP/path/readonly/ACL/sharing behavior; full development regressions (never count
zero runtime tests); the D.1 lock/hardlink/recovery checklist on disposable
synthetic roots; actual owner-reviewed corporate schema/graph semantics; genuine
authority/evidence for any business/architecture assertions; and separate explicit
authorization before real canonical population or rollout. Current tools do not
supply C# semantic inference, arbitrary legacy conversion or automatic business
verification. No later stage is implemented by this package.
