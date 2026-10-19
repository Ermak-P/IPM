# Stage 2 end-to-end acceptance report

**Decision: PASS — functionally accepted in the tested Linux environment. Native Windows 11 / NTFS: NOT TESTED; acceptance gate OPEN.**

This is acceptance of A–E and D.1, not a new increment. No implementation defect was demonstrated; no product code, Contract v1.0, schemas, validator or canonical records were changed. The only repository change is this report.

## 1. Baseline and environment

- Repository: Ermak-P/IPM; branch `work`; exact HEAD `fca8413702925fd0b88d6d5e5453180d1860c011`.
- Initial `git status --short`: empty (clean). All acceptance checks used this implementation.
- Observation recorded at 2026-10-19T04:35:55.051017+00:00.
- Platform: `Linux-6.18.55-x86_64-with-glibc2.41`; `uname -a`: `Linux d2e45b03a593 6.18.55 #1 SMP Wed Oct 14 19:45:18 UTC 2026 x86_64 GNU/Linux`.
- Python: `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`; executable `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`.
- .NET SDK `10.0.402`, VSTest `18.7.0 (x64)`; Microsoft.NETCore.App and Microsoft.AspNetCore.App `10.0.13`.
- .NET SDK path `/workspace/.ipm-tools/dotnet/dotnet`. Existing Linux test DLLs executed; no build, package restore or project scripts were run by acceptance or the knowledge pipeline.
- Native Windows was unavailable. Linux execution and the existing mocked Windows branches are not native Windows acceptance.

## 2. Executed checks and counts

All commands below were actually executed. Exit 1 for deliberate rejection and exit 71 for injected process termination are expected outcomes, not product failures.

| Command (cwd `/workspace/IPM`) | Exit | Result |
| --- | --- | --- |
| `git rev-parse HEAD` | 0 | exact baseline above |
| `git status --short` | 0 | clean baseline |
| `python --version` | 0 | 3.12.14 |
| `uname -a` | 0 | Linux x86_64 |
| `python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'` | 0 | 209 passed, 0 failed, 0 errors, 0 skipped |
| `dotnet --version` | 0 | 10.0.402 |
| `dotnet --list-runtimes` | 0 | two runtimes, both 10.0.13 |
| `dotnet vstest tests/SyntheticIpm.UnitTests/bin/Debug/net10.0/SyntheticIpm.UnitTests.dll tests/SyntheticIpm.IntegrationTests/bin/Debug/net10.0/SyntheticIpm.IntegrationTests.dll --ResultsDirectory:/tmp/ipm-stage2-acceptance-dotnet` | 0 | 27 passed: 12 unit + 15 integration; 0 failed/skipped |
| `python -B -m unittest discover -v -s .ai/tools/tests -p test_population.py > /tmp/ipm-stage2-recovery-suite.log 2>&1` | 0 | 63 passed; repeat of the transaction subset already counted within 209 |
| `python -B .ai/tools/kb.py validate --json` | 0 | ok=true, no errors |
| `python -B .ai/tools/kb.py check-scaffold --json` | 0 | ok=true, no errors |
| `python -B .ai/tools/kb.py version --json` | 0 | CLI 1.0.0, format 1.0.0 |
| `python -B /tmp/ipm_stage2_acceptance.py > /tmp/ipm-stage2-lifecycle-results.json` | 0 | 39 actual CLI processes; all expected outcomes |
| `python -B /tmp/ipm_stage2_recovery_acceptance.py > /tmp/ipm-stage2-recovery-results.json (corrected harness run)` | 0 | 74 actual CLI/injected-process commands; all expected outcomes |
| `git diff --check` | 0 | no whitespace errors |

`dotnet` denotes the exact SDK path above, with `DOTNET_ROOT=/workspace/.ipm-tools/dotnet`, `DOTNET_CLI_HOME=/workspace/.ipm-tools/cli-home`, `DOTNET_CLI_TELEMETRY_OPTOUT=1`, `TESTINGPLATFORM_TELEMETRY_OPTOUT=1` for test execution. Python unique regression total is 209, not 272; the focused 63-test run is additional execution of existing tests.

An initial recovery harness run exited 1 because it incorrectly expected exit 0 when recovery encountered an unrelated external canonical addition. Actual CLI exit 1 was the documented `concurrent-edits-preserved-manual-review-required-before-recovery` response. Inspection of rollback(), existing preservation tests and population-apply.md confirmed correct protective behavior. The harness expectation was corrected to require exit 1, repeated refusal, retained external bytes and continued read gates. Product code was not changed. The corrected complete run passed.

## 3. Fixture, expected facts and successful lifecycle

The fixture is a disposable copy of the existing tracked IPM host files, not a newly invented substitute: 56 tracked host files copied byte-for-byte, including SyntheticIpm.sln, six .csproj files, C# sources, packages/configuration and lockfiles. `.git`, existing `.ai` state and ignored build/cache outputs were not copied. The actual CLI initialized a fresh `.ai`, then every workflow command used its installed CLI. Initialization and population never targeted the real repository.

Expected project set: SyntheticIpm.Domain, Application, Infrastructure and Api under `src/`; SyntheticIpm.UnitTests and IntegrationTests under `tests/`. All six exact paths, filename labels, solution member names, declared project GUIDs and resolved targets matched. A separate explicit six-GUID expectation was checked against the extracted membership records (exit 0). Literal ProjectReference Includes and package Includes/versions were independently checked using ElementTree in the acceptance harness.

| Supported fact | Expected | Actual |
| --- | ---: | ---: |
| package_reference | 6 | 6 |
| package_version | 6 | 6 |
| project | 6 | 6 |
| project_reference | 5 | 5 |
| solution_membership | 6 | 6 |
| Direct project_property/framework declarations in .csproj | 0 | 0 |
| Total | 29 | 29 |

The common TargetFramework `net10.0` is in Directory.Build.props, not these .csproj files. The existing analyzer does not evaluate imports/inheritance: zero inherited framework candidates is correct, not a missing claimed observation. Directory.Build.props is reported unsupported by discovery; FrameworkReference, test properties and solution build metadata retain unsupported/not-evaluated diagnostics. Direct framework/property declarations are covered by existing extraction/normalization/graph tests and the source-change scenario below.

Executed sequence: scan → extract → normalize → prepare → missing-approval rejection → dry-run → exact-plan-approved apply → validate/check-scaffold/version → canonical build → technical-preview build → report. Preparation and dry-run preserved the canonical snapshot. Applied batch: **29 technical claims + 29 evidence records + 0 canonical relationships**, exactly 58 globally unique IDs and 58 writes. Every claim cites its matching evidence, every such evidence explicitly substantiates that claim. All claims remain NEEDS_HUMAN_CONFIRMATION with last_verified=null. No review event or promotion was generated.

Repeated exact-plan apply returned writes=0, with canonical hashes unchanged. Fresh normalization classified all 58 records unchanged. All 56 copied host-file hashes remained identical throughout the unmodified-input lifecycle.

## 4. Graph/report integrity and regeneration

- Canonical graph: **68 nodes, 145 edges**; only retained claims/evidence and explicit provenance/source/citation/substantiation links. No canonical depends_on or conflicts_with was invented from project edges.
- Technical preview: **10 nodes, 23 edges**, including exactly five declared direct ProjectReferences. Authority/view fields differ from canonical; every project edge says declared-not-evaluated and active_evaluated_dependency=unknown. No runtime dependence or transitive closure is asserted.
- Canonical graph, technical preview and report were generated twice; complete JSON results were equal. Outputs were explicitly written, generated/ deleted, and all three artifacts rebuilt byte-for-byte: canonical-graph.json, technical-preview-graph.json, knowledge-report.json.
- Current real-repository build canonical, build technical-preview and report stdout were also compared twice without writes; all were byte-identical. All four checked-in graph_demo examples (canonical, technical-preview, report, summary) were regenerated to captured stdout and compared byte-for-byte with existing artifacts.

| Disposable fixture result (serialized captured response) | SHA-256; unchanged run | After source declaration changes |
| --- | --- | --- |
| canonical graph | `5c83f25605b5f27100e604e02b41ce5bf3ee3fc090e3d2fe90a587dd453bdea6` | `5c83f25605b5f27100e604e02b41ce5bf3ee3fc090e3d2fe90a587dd453bdea6` |
| technical preview | `8e6c20830290f73bb1b72766579ee5d5a417d938f21ab81bec05bafd4f9a784b` | `98c01e4576d5571eae1829244613dff9b6c9d49bfca7622a7d79518561ca9db4` |
| knowledge report | `dee0c0a354fa7b7fd4cc331eae50c1e2f6280415b50a1ee7f6d641b2b3650fea` | `5f76f9b28e5f7830b6c17219b9fc344e184460d4146804129179a7cc3725f562` |

Canonical equality after source changes is intentional: rebuilding historical knowledge does not rewrite it. Source observation hashes and graph/report serialization hashes are different concepts; neither is semantic proof.

## 5. Source-change lifecycle

Only the disposable UnitTests .csproj was first reformatted (leading whitespace on PackageReference lines). All 29 claim IDs and all 29 evidence IDs remained stable. Change set: **50 unchanged, 8 potential update** (source evidence refresh). No canonical record was written. Preparing a refresh plan produced blocked operations; approved add-only apply returned exit 1 and preserved canonical bytes.

Then the fixture changed NUnit 4.5.1 → 4.6.0, removed NUnit3TestAdapter and its version plus the UnitTests→Domain ProjectReference, added a literal TargetFramework net9.0, and added a conditional `$(Unknown)/Missing.csproj` reference. The latter remains unresolved and unevaluated even with Condition=false; no condition execution occurs. Results:

- 25 old claim IDs unchanged; 3 newly proposed claim IDs; 4 previous declarations no longer proposed but retained canonically.
- Combined change set: **46 unchanged, 6 potential update, 10 unresolved, 2 add**. These are record classifications across claims/evidence and include historical retained records, not a count of semantic facts or review decisions.
- Prepared plan: **16 blocked operations**; exact-plan approved apply rejected (exit 1). All 29 historical claims and 29 evidence records remained byte-identical and continued to pass validation.
- Canonical graph stayed identical. Preview and report changed, showing new declarations, stale source hashes, conditional/unresolved reference IDs and comparison diagnostics. The old project reference was not silently removed from historical claims.
- Subsequently the disposable Domain .csproj was removed. Normalization/report detected missing source evidence (`missing_from_current_inventory=true`) and unresolved current references; canonical bytes remained untouched.

Future handling requires explicit lifecycle management: review changed/removed declaration proposals against source locations, preserve stable evidence identity for formatting refresh, record actual observation/verification events, and deliberately decide whether old facts remain historical, need refreshed evidence, retraction or supersession. Any conflict resolution must be a separately reviewed, validated operation preserving provenance and human knowledge. No replacement, deletion, evidence retraction, inferred runtime dependency or status promotion was implemented here. Unresolved MSBuild/conditions remain unknown until supported analysis or human review supplies evidence.

## 6. Real process interruption and recovery

Each scenario used its own disposable copy of the IPM fixture and a fresh exact plan. An injected test-only _checkpoint called os._exit(71); no product fault-injection CLI or feature was added. The guard remained active. Nonterminal interruptions blocked actual validate, both build views and report (exit 1), even when all record files happened to be structurally complete before COMMITTED.

| Stop point | Observed journal | Recovery and retry evidence |
| --- | --- | --- |
| after_stage (index=0) | STAGING | Two recovery calls restore/retain exact empty canonical baseline; approved retry writes=58; next retry writes=0; validate exit 0. |
| after_install (index=0) | INSTALLING | Two recovery calls restore/retain exact empty canonical baseline; approved retry writes=58; next retry writes=0; validate exit 0. |
| before_commit (index=None) | INSTALLING | Two recovery calls restore/retain exact empty canonical baseline; approved retry writes=58; next retry writes=0; validate exit 0. |
| before_journal_replace (index=COMMITTED) | INSTALLING | Two recovery calls restore/retain exact empty canonical baseline; approved retry writes=58; next retry writes=0; validate exit 0. |
| after_commit (index=None) | COMMITTED | COMMITTED receipt removed: two recover calls refused without deleting committed bytes. Restore exact captured receipt; two recover calls retain all bytes. Retry writes=0. |
| External addition at before_commit | INSTALLING → RECOVERY_REQUIRED | Recovery twice returns exit 1; removes only its own batch, preserves exact external record bytes; validate/build/retry remain gated. |

External edit test expectation is baseline **plus the external record**, not a forced return to the old snapshot that would delete human data. The external fixture is deliberately left gated pending explicit manual reconciliation. This is an intentional safety boundary, not successful automatic reconciliation. The existing 63-test transaction suite separately exercises explicit synthetic manual reconciliation, concurrent destination edits, edited transaction-owned files, rollback interruption, sharing-denial simulation, real two-process locks and the legacy ambiguous recovery marker. All 63 passed on this run. Tests with mocks remain simulation results, not native Windows results.

The ambiguous receipt test restores only the original exact trusted COMMITTED journal to finish verification/cleanup; it never fabricates STAGING history or substitutes an older journal. Each recovery fixture retained all host bytes. No cross-file atomicity or power-loss durability is claimed.

## 7. Offline/security and real-repository integrity

The lifecycle ran 39 guarded Python children; recovery ran 74. A sitecustomize guard was activated in every such child, rejecting socket creation/connections, subprocess.Popen, os.system and os exec/spawn functions. **Zero forbidden calls** were logged. Thus all actual CLI extraction/population/build/report scenarios completed without those network/process APIs. Existing regression tests also prohibit network/LLM/project execution and test XML DTD/entity rejection, exclusions, escaped symlinks, unsafe objects and canonical-write boundaries. The guard is evidence for the exercised Python paths, not an OS network sandbox or proof against arbitrary hostile Python. .NET test execution was a separate regression command, outside the knowledge pipeline; no restore was run.

SHA-256 snapshots before/after acceptance cover **1148 real host files** (including existing ignored build artifacts) and **11 canonical/schema/source-metadata/manifest files**. All unchanged; no host paths added/removed. Real claims/evidence/relationships remain empty. Real populate status shows no transactions and no recovery required; the pre-existing ignored prepared plan remains untouched. Only this Markdown report was added to the checkout. Contract/schema/validator and A–E/D.1 implementation bytes are unchanged.

## 8. Native Windows 11 / NTFS acceptance — OPEN

Existing windows11-ntfs-checklist.md was inspected in full. The following are **NOT TESTED here** and remain required; Linux passes or mocks do not close any item:

1. Run on native Windows 11 python.exe on a local NTFS volume (not WSL/Wine/SMB/cloud-sync); record OS build, Python version/architecture, filesystem, ACLs, path/AV settings and .NET versions.
2. Run the entire Python regression suite natively and record each failure/skip. Unix FIFO skips and unprivileged symlink skips are not passes; distinguish mocked tests even on Windows. Run the existing .NET tests with native test binaries and record results separately.
3. Repeat the copied-IPM actual CLI lifecycle: scan, extract, normalize, prepare, missing-approval rejection, dry-run, exact-plan apply, validate, both graph views, JSON/human report; verify all expected IDs, evidence, statuses, hashes and counts.
4. Repeat formatting/substantive/removed-source scenarios, blocked-plan refusal and graph/report discrepancy checks with canonical bytes retained.
5. Repeat real process death after_stage, after_install, before_commit, before_journal_replace(COMMITTED), after_commit; verify native lock release, read gates, expected recovery and zero-write retry.
6. Remove the COMMITTED journal in a disposable after_commit fixture: repeated recovery must refuse deletion. Test the legacy ambiguous marker; restore only an exact trusted receipt for cleanup.
7. Observe native msvcrt one-byte offset-zero acquisition/release, persistent lock size, handle closure on errors and two-process exclusion for apply/readers; verify OS releases a dead process lock without deleting coordination.lock.
8. Observe actual NTFS os.link/CreateHardLinkW identity via samefile/st_dev/st_ino/st_nlink: two links while staged+installed, one after cleanup. Verify existing destinations are not replaced and unexpected third links are rejected.
9. Hold native Windows handles without FILE_SHARE_DELETE during journal os.replace/MoveFileExW; verify actual sharing errors, no false commit, safe recovery after release and old output preservation for generated-file replacement.
10. Hold staged/canonical handles during cleanup; test read-only attributes, restrictive ACLs and antivirus interference. Require safe error/recovery without forced permission changes or data loss.
11. Check all write handles are closed before linking/replacing, no leaked lock/temporary handles, and TemporaryDirectory cleanup succeeds after readers/processes release their handles.
12. Repeat external concurrent edit preservation, occupied destination and modified owned-file cases with repeated recovery; no unreviewed overwrite/deletion.
13. Repeat graph/report deterministic stdout and explicit generated-output write/delete/rebuild with native filesystem semantics, including interrupted-recovery gates.
14. Run in paths with spaces/non-ASCII; test long paths only if already enabled, recording actual machine configuration. Do not change security/integrity checks to obtain passes.
15. Finish with native validate/check-scaffold/version, complete source/canonical hash comparisons and recorded command exit codes/journal states. Close handles/processes before removing disposable roots. Power-loss/storage-failure durability remains outside this process-interruption acceptance.

## 9. Explicit acceptance matrix

| Criterion | Status | Executed evidence |
| --- | --- | --- |
| Exact baseline/environment/status | PASS | Section 1; clean initial tree and exact commit/version commands |
| All Stage 1/A–E/D.1 Python regressions | PASS | 209/209, no failures/errors/skips |
| Existing .NET regressions | PASS | 27/27 (12 unit, 15 integration), no restore/build |
| Actual full CLI lifecycle on existing copied fixture | PASS | 39 commands in lifecycle transcript; successful ten-stage workflow |
| All supported fixture facts extracted | PASS | 29 expected=actual; independent XML Include/version checks and exact six project/member paths/names |
| Prepare/dry-run do not mutate canonical records | PASS | Canonical hash equality before/after; missing approval rejected |
| Exact approval, record/evidence integrity, no duplicates | PASS | 58 unique applied IDs; 29 claims each bidirectionally linked to evidence; validate exit 0 |
| Claims retain NEEDS_HUMAN_CONFIRMATION/null verification | PASS | All 29 actual installed claims inspected |
| Canonical and preview trust boundaries | PASS | Distinct view/authority fields; no observed canonical depends_on; five declared/unknown project edges |
| Repeated application is idempotent | PASS | Normal and recovered fixture retries writes=0; unchanged canonical hashes |
| Deterministic graph/report serialization | PASS | Repeated whole-result equality and real stdout equality; Section 4 hashes |
| Complete generated deletion/regeneration | PASS | All three fixture artifacts reconstructed byte-identically; four example stdout outputs match |
| Stable IDs and no duplicates after formatting | PASS | 29 claim + 29 evidence IDs stable; no canonical writes; 8 evidence updates proposed |
| Substantive changes/removals explicitly proposed | PASS | 25 retained IDs, 3 new proposed, 4 removed declarations retained; stale/missing evidence diagnostics |
| No automatic replacement/deletion/promotion/retraction | PASS | Canonical snapshot identical after every analysis and refused apply |
| Add-only refuses blocked/unresolved plans | PASS | Formatting and substantive plans refused with exact approval; 16 substantive blocked operations |
| Discrepancies exposed without altering history | PASS | Canonical graph same, preview/report different; stale hashes and unresolved dependency IDs |
| Process interruption detected; incomplete reads blocked | PASS | Four nonterminal real os._exit scenarios; validate/build/report exit 1 |
| Safe recovery restores unmodified baseline | PASS | Repeated recovery after four nonterminal stops; exact preapply canonical hashes and validation |
| Ambiguous/committed repeated recovery non-destructive | PASS | Two missing-receipt refusals; two trusted-receipt cleanup retries; legacy case in focused suite |
| External concurrent edits preserved | PASS | Exact external bytes retained twice, own batch removed, RECOVERY_REQUIRED and reads/apply gated; no automatic reconciliation claimed |
| Concurrent locking/collision safety | PASS | Existing real two-process lock and collision/owned-file tests rerun in 63-test suite on Linux |
| No host modifications during unmodified-input workflow/recovery | PASS | 56 copied host paths per fixture compared; deliberate source edits confined to change fixture |
| Real host/canonical/Contract integrity | PASS | 1148 host + 11 canonical/contract/source files unchanged; real transaction list empty |
| No required network/LLM/restore/project execution | PASS | 113 guarded CLI/injection children, zero forbidden calls; offline tests and implementation inspection |
| validate/check-scaffold/version/diff checks | PASS | Actual exit 0; CLI/schema format unchanged |
| No new architecture capability | PASS | Only acceptance report added; implementation unchanged |
| Native Windows 11/NTFS lifecycle, locking/sharing/cleanup | NOT TESTED | No native Windows environment; all 15 requirements in Section 8 remain open |
| Power loss/storage failure durability | NOT TESTED | Process termination tests are not power-loss durability tests; no such guarantee claimed |

## 10. Limitations and defects

No product defect found, so no implementation fixes/refactors were made. The harness expectation correction is documented in Section 2. Retained limitations: declaration-only .NET analysis, no imports/evaluation/runtime semantics; arbitrary human prose is not semantically compared; source exclusions/unsupported inputs may prevent freshness judgments; stable trusted trees are required and portable checks do not isolate hostile same-user path swaps; concurrent external changes can require explicit manual reconciliation; generated graphs are disposable snapshots; process tests do not establish cross-file atomicity/power-loss guarantees. Native Windows remains separately pending. No Increment F, RAG, embeddings, MCP, orchestration, graph editor or relationship types were added.

## 11. Exact CLI transcript

The following records every CLI and injected-process invocation in the successful acceptance runs, including expected rejections. K means the **installed** command `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -B <fixture>/.ai/tools/kb.py <args> --root <fixture> --json`. Init uses `/workspace/IPM/.ai/tools/kb.py` instead because no installed CLI exists yet. Plan aliases below map to the exact observed fingerprints; they do not authorize another plan. Crash commands are K-independent `python -B -c` scripts below, taking installed tools path, fixture root and exact plan fingerprint.

Fixture roots:

- Lifecycle: `/tmp/ipm-stage2-acceptance-gq9yr2ky/lifecycle`.
- Recovery: `/tmp/ipm-stage2-acceptance-gmnmym_2/<fixture-name>` from the table.

| Alias | Exact plan fingerprint |
| --- | --- |
| P1 | `sha256:41c228e1e2f55cdb753a8b5ee060961e771294abd4769d3b58fbdeca55c7e01b` |
| P2 | `sha256:ede438c1a125269108807a39165ad049105fd3bf4ec5f275953ec869f51a82ce` |
| P3 | `sha256:09c5b58fcb20efd154f5fef4f5a1470f9955ee45558e3259a734f4bf21fcff33` |
| P4 | `sha256:92b59c89a95a97f7b147ea8be21b0051a840fc28f29d4cd86009ee0669dae75d` |
| P5 | `sha256:cfd45cd6636f9b3a0d30bc8221649aa25c3a188c5c6358273df2a0441b156486` |
| P6 | `sha256:e5a45f2764816d1ebce9af91ff9db718d0b3845541aaee4ca792af3523bc818c` |
| P7 | `sha256:b72128a6e983a39f1340d32f43dfcebd9dbb44113ef07ab881a3670dfc82890b` |
| P8 | `sha256:2f565c365ae4ad22277efbb5a9a064d729b6ceb4ab5c97999ab8081926a64278` |
| P9 | `sha256:6e1a55162c9a4660b801d97c63584ef038d579c994cbf3c6a686a248b0f6eccc` |

| Run/id | Fixture | K args or injected-process stop | Exit | Expected |
| --- | --- | --- | ---: | ---: |
| L01 | lifecycle | `init` | 0 | 0 |
| L02 | lifecycle | `scan` | 0 | 0 |
| L03 | lifecycle | `extract` | 0 | 0 |
| L04 | lifecycle | `normalize` | 0 | 0 |
| L05 | lifecycle | `populate prepare` | 0 | 0 |
| L06 | lifecycle | `populate apply --plan P1` | 1 | 1 |
| L07 | lifecycle | `populate apply --plan P1 --dry-run` | 0 | 0 |
| L08 | lifecycle | `populate apply --plan P1 --approve P1` | 0 | 0 |
| L09 | lifecycle | `validate` | 0 | 0 |
| L10 | lifecycle | `check-scaffold` | 0 | 0 |
| L11 | lifecycle | `version` | 0 | 0 |
| L12 | lifecycle | `build --view canonical` | 0 | 0 |
| L13 | lifecycle | `build --view technical-preview` | 0 | 0 |
| L14 | lifecycle | `report` | 0 | 0 |
| L15 | lifecycle | `populate apply --plan P1 --approve P1` | 0 | 0 |
| L16 | lifecycle | `build --view canonical` | 0 | 0 |
| L17 | lifecycle | `build --view technical-preview` | 0 | 0 |
| L18 | lifecycle | `report` | 0 | 0 |
| L19 | lifecycle | `build --view canonical --write-generated` | 0 | 0 |
| L20 | lifecycle | `build --view technical-preview --write-generated` | 0 | 0 |
| L21 | lifecycle | `report --write-generated` | 0 | 0 |
| L22 | lifecycle | `build --view canonical --write-generated` | 0 | 0 |
| L23 | lifecycle | `build --view technical-preview --write-generated` | 0 | 0 |
| L24 | lifecycle | `report --write-generated` | 0 | 0 |
| L25 | lifecycle | `normalize` | 0 | 0 |
| L26 | lifecycle | `normalize` | 0 | 0 |
| L27 | lifecycle | `populate prepare` | 0 | 0 |
| L28 | lifecycle | `populate apply --plan P2 --approve P2` | 1 | 1 |
| L29 | lifecycle | `scan` | 0 | 0 |
| L30 | lifecycle | `extract` | 0 | 0 |
| L31 | lifecycle | `normalize` | 0 | 0 |
| L32 | lifecycle | `populate prepare` | 0 | 0 |
| L33 | lifecycle | `populate apply --plan P3 --approve P3` | 1 | 1 |
| L34 | lifecycle | `build --view canonical` | 0 | 0 |
| L35 | lifecycle | `build --view technical-preview` | 0 | 0 |
| L36 | lifecycle | `report` | 0 | 0 |
| L37 | lifecycle | `validate` | 0 | 0 |
| L38 | lifecycle | `normalize` | 0 | 0 |
| L39 | lifecycle | `report` | 0 | 0 |
| R01 | crash-after_stage | `init` | 0 | 0 |
| R02 | crash-after_stage | `populate prepare` | 0 | 0 |
| R03 | crash-after_stage | `'python -B -c fault injection' after_stage 0` | 71 | 71 |
| R04 | crash-after_stage | `populate status --plan P4` | 0 | 0 |
| R05 | crash-after_stage | `validate` | 1 | 1 |
| R06 | crash-after_stage | `build --view canonical` | 1 | 1 |
| R07 | crash-after_stage | `build --view technical-preview` | 1 | 1 |
| R08 | crash-after_stage | `report` | 1 | 1 |
| R09 | crash-after_stage | `populate recover --plan P4` | 0 | 0 |
| R10 | crash-after_stage | `validate` | 0 | 0 |
| R11 | crash-after_stage | `populate recover --plan P4` | 0 | 0 |
| R12 | crash-after_stage | `populate apply --plan P4 --approve P4` | 0 | 0 |
| R13 | crash-after_stage | `populate apply --plan P4 --approve P4` | 0 | 0 |
| R14 | crash-after_stage | `validate` | 0 | 0 |
| R15 | crash-after_install | `init` | 0 | 0 |
| R16 | crash-after_install | `populate prepare` | 0 | 0 |
| R17 | crash-after_install | `'python -B -c fault injection' after_install 0` | 71 | 71 |
| R18 | crash-after_install | `populate status --plan P5` | 0 | 0 |
| R19 | crash-after_install | `validate` | 1 | 1 |
| R20 | crash-after_install | `build --view canonical` | 1 | 1 |
| R21 | crash-after_install | `build --view technical-preview` | 1 | 1 |
| R22 | crash-after_install | `report` | 1 | 1 |
| R23 | crash-after_install | `populate recover --plan P5` | 0 | 0 |
| R24 | crash-after_install | `validate` | 0 | 0 |
| R25 | crash-after_install | `populate recover --plan P5` | 0 | 0 |
| R26 | crash-after_install | `populate apply --plan P5 --approve P5` | 0 | 0 |
| R27 | crash-after_install | `populate apply --plan P5 --approve P5` | 0 | 0 |
| R28 | crash-after_install | `validate` | 0 | 0 |
| R29 | crash-before_commit | `init` | 0 | 0 |
| R30 | crash-before_commit | `populate prepare` | 0 | 0 |
| R31 | crash-before_commit | `'python -B -c fault injection' before_commit None` | 71 | 71 |
| R32 | crash-before_commit | `populate status --plan P6` | 0 | 0 |
| R33 | crash-before_commit | `validate` | 1 | 1 |
| R34 | crash-before_commit | `build --view canonical` | 1 | 1 |
| R35 | crash-before_commit | `build --view technical-preview` | 1 | 1 |
| R36 | crash-before_commit | `report` | 1 | 1 |
| R37 | crash-before_commit | `populate recover --plan P6` | 0 | 0 |
| R38 | crash-before_commit | `validate` | 0 | 0 |
| R39 | crash-before_commit | `populate recover --plan P6` | 0 | 0 |
| R40 | crash-before_commit | `populate apply --plan P6 --approve P6` | 0 | 0 |
| R41 | crash-before_commit | `populate apply --plan P6 --approve P6` | 0 | 0 |
| R42 | crash-before_commit | `validate` | 0 | 0 |
| R43 | crash-before_journal_replace | `init` | 0 | 0 |
| R44 | crash-before_journal_replace | `populate prepare` | 0 | 0 |
| R45 | crash-before_journal_replace | `'python -B -c fault injection' before_journal_replace COMMITTED` | 71 | 71 |
| R46 | crash-before_journal_replace | `populate status --plan P7` | 0 | 0 |
| R47 | crash-before_journal_replace | `validate` | 1 | 1 |
| R48 | crash-before_journal_replace | `build --view canonical` | 1 | 1 |
| R49 | crash-before_journal_replace | `build --view technical-preview` | 1 | 1 |
| R50 | crash-before_journal_replace | `report` | 1 | 1 |
| R51 | crash-before_journal_replace | `populate recover --plan P7` | 0 | 0 |
| R52 | crash-before_journal_replace | `validate` | 0 | 0 |
| R53 | crash-before_journal_replace | `populate recover --plan P7` | 0 | 0 |
| R54 | crash-before_journal_replace | `populate apply --plan P7 --approve P7` | 0 | 0 |
| R55 | crash-before_journal_replace | `populate apply --plan P7 --approve P7` | 0 | 0 |
| R56 | crash-before_journal_replace | `validate` | 0 | 0 |
| R57 | crash-after_commit | `init` | 0 | 0 |
| R58 | crash-after_commit | `populate prepare` | 0 | 0 |
| R59 | crash-after_commit | `'python -B -c fault injection' after_commit None` | 71 | 71 |
| R60 | crash-after_commit | `populate status --plan P8` | 0 | 0 |
| R61 | crash-after_commit | `populate recover --plan P8` | 1 | 1 |
| R62 | crash-after_commit | `populate recover --plan P8` | 1 | 1 |
| R63 | crash-after_commit | `populate recover --plan P8` | 0 | 0 |
| R64 | crash-after_commit | `populate recover --plan P8` | 0 | 0 |
| R65 | crash-after_commit | `populate apply --plan P8 --approve P8` | 0 | 0 |
| R66 | crash-after_commit | `validate` | 0 | 0 |
| R67 | external-edit | `init` | 0 | 0 |
| R68 | external-edit | `populate prepare` | 0 | 0 |
| R69 | external-edit | `'python -B -c fault injection' external-before-commit` | 71 | 71 |
| R70 | external-edit | `populate recover --plan P9` | 1 | 1 |
| R71 | external-edit | `populate recover --plan P9` | 1 | 1 |
| R72 | external-edit | `validate` | 1 | 1 |
| R73 | external-edit | `build --view canonical` | 1 | 1 |
| R74 | external-edit | `populate apply --plan P9 --approve P9` | 1 | 1 |

Additional actually executed regeneration commands, all exit 0: each of `python -B .ai/tools/kb.py build --view canonical --json`, `... build --view technical-preview --json`, `... report --json` was run twice and complete stdout compared. Each `python -B .ai/tools/examples/graph_demo.py MODE` (MODE canonical, technical-preview, report, summary) was captured and compared to its checked-in artifact. Supplementary exact project/member path assertions and real repository SHA-256/added-removed-path assertions exited 0. Final status/diff and CLI validation checks were repeated after writing this report.

## 12. Reproduction harnesses used for this acceptance

These are the exact disposable acceptance scripts after correcting the external-edit expectation. They are evidence/test harnesses, not installed production capabilities. Save the first as /tmp/ipm_stage2_acceptance.py and the second as /tmp/ipm_stage2_recovery_acceptance.py; run from the baseline checkout at /workspace/IPM with the documented Python. They create unique temporary roots and never populate the real root. They intentionally keep disposable roots/logs for inspection, including the external-edit fixture awaiting manual reconciliation. Harness-created paths are ephemeral; the decisions, counts, commands and fingerprints above are self-contained in this report.

<details><summary>ipm_stage2_acceptance.py</summary>

```python
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,xml.etree.ElementTree as ET
from collections import Counter
REPO=pathlib.Path('/workspace/IPM')
WORK=pathlib.Path(tempfile.mkdtemp(prefix='ipm-stage2-acceptance-'))
GUARD=WORK/'guard';GUARD.mkdir()
(GUARD/'sitecustomize.py').write_text('''import os,socket,subprocess,sys
with open(os.environ['KB_GUARD_LOG'],'a') as log: log.write('guard-active\\n')
def forbidden(*args,**kwargs):
    with open(os.environ['KB_GUARD_LOG'],'a') as log: log.write('FORBIDDEN\\n')
    raise RuntimeError('Acceptance forbids network and child/project execution')
socket.socket=forbidden
socket.create_connection=forbidden
subprocess.Popen=forbidden
os.system=forbidden
for name in dir(os):
    if name.startswith(('exec','spawn','posix_spawn')): setattr(os,name,forbidden)
''')
ENV=dict(os.environ,PYTHONPATH=str(GUARD),KB_GUARD_LOG=str(WORK/'guard.log'),PYTHONDONTWRITEBYTECODE='1')
LOG=[];RESULT={'workspace':str(WORK),'commands':LOG}

def canonical(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for group in ['knowledge','evidence','sources','schema']
            for p in (root/'.ai'/group).rglob('*') if p.is_file()}

def host(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.relative_to(root).parts[0]!='.ai'}

def cli(root,*args,expected=0):
    command=[sys.executable,'-B',str(root/'.ai/tools/kb.py'),*args,'--root',str(root),'--json']
    run=subprocess.run(command,capture_output=True,text=True,env=ENV)
    output=json.loads(run.stdout)
    index=len(LOG)+1
    (WORK/f'{index:03}.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    LOG.append({'id':index,'fixture':root.name,'args':list(args),'exit_code':run.returncode,'expected_exit_code':expected})
    assert run.returncode==expected,(command,run.stdout,run.stderr)
    return output

def fixture(name):
    root=WORK/name; root.mkdir()
    tracked=subprocess.run(['git','ls-files','-z'],cwd=REPO,capture_output=True,check=True).stdout.decode().split('\0')
    for name in tracked:
        if not name or name.startswith('.ai/'): continue
        source=REPO/name
        destination=root/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
    # Initializer itself is the real CLI; all subsequent calls use its installed copy.
    command=[sys.executable,'-B',str(REPO/'.ai/tools/kb.py'),'init','--root',str(root),'--json']
    run=subprocess.run(command,capture_output=True,text=True,env=ENV)
    LOG.append({'id':len(LOG)+1,'fixture':root.name,'args':['init'],'exit_code':run.returncode,'expected_exit_code':0})
    assert run.returncode==0,run.stdout
    return root

def ids(report,group):return {r['id'] for r in report['records'][group]}

def main():
    root=fixture('lifecycle'); before_host=host(root);before_canonical=canonical(root)
    scan=cli(root,'scan'); extraction=cli(root,'extract'); normalized=cli(root,'normalize')
    expected=Counter(project=6,solution_membership=6,project_reference=5,package_reference=6,package_version=6)
    actual=Counter(c['kind'] for c in extraction['candidates'])
    assert actual==expected,(actual,expected)
    # Independent literal XML checks, not deriving expected values from the analyzer.
    for source in root.rglob('*.csproj'):
        tree=ET.parse(source).getroot();relative=source.relative_to(root).as_posix()
        candidates=[c for c in extraction['candidates'] if c['source']==relative]
        assert any(c['kind']=='project' for c in candidates)
        for tag,kind in [('ProjectReference','project_reference'),('PackageReference','package_reference')]:
            declared=sorted(e.attrib['Include'] for e in tree.iter(tag))
            observed=sorted(c['value']['include'] for c in candidates if c['kind']==kind)
            assert observed==declared,(relative,tag)
        versions=sorted((e.attrib['Include'],e.attrib['Version']) for e in tree.iter('PackageReference'))
        observed=sorted((c['value']['include'],c['value']['declared']) for c in candidates if c['kind']=='package_version')
        assert versions==observed
    assert len(scan['sources'])==7 and normalized['counts']=={'claims':29,'evidence':29,'relationships':0}
    prepared=cli(root,'populate','prepare'); plan=prepared['plan']; fingerprint=plan['fingerprint']
    assert plan['applicable'] and len(plan['eligible'])==58 and not plan['blocked']
    assert before_canonical==canonical(root)
    cli(root,'populate','apply','--plan',fingerprint,expected=1)
    cli(root,'populate','apply','--plan',fingerprint,'--dry-run')
    assert before_canonical==canonical(root)
    applied=cli(root,'populate','apply','--plan',fingerprint,'--approve',fingerprint)
    assert applied['writes']==58 and applied['state']=='COMMITTED'
    cli(root,'validate');cli(root,'check-scaffold');cli(root,'version')
    canonical_graph=cli(root,'build','--view','canonical')
    preview=cli(root,'build','--view','technical-preview');report=cli(root,'report')
    installed=canonical(root)
    again=cli(root,'populate','apply','--plan',fingerprint,'--approve',fingerprint)
    assert again['writes']==0 and canonical(root)==installed
    canonical_files=list((root/'.ai/knowledge/claims').glob('*.json'))
    evidence_files=list((root/'.ai/evidence').glob('*.json'))
    claims=[json.loads(p.read_text()) for p in canonical_files]
    evidence=[json.loads(p.read_text()) for p in evidence_files]
    assert len(claims)==len(evidence)==29
    assert len({r['id'] for r in claims+evidence})==58
    evidence_index={e['id']:e for e in evidence}
    assert all(c['status']=='NEEDS_HUMAN_CONFIRMATION' and c['last_verified'] is None and
               c['evidence'] and all(c['id'] in evidence_index[e]['substantiates'] for e in c['evidence']) for c in claims)
    assert all(not c['depends_on'] and not c['conflicts_with'] for c in claims)
    assert canonical_graph==cli(root,'build','--view','canonical')
    assert preview==cli(root,'build','--view','technical-preview')
    assert report==cli(root,'report')
    for command in [('build','--view','canonical'),('build','--view','technical-preview'),('report',)]:
        cli(root,*command,'--write-generated')
    saved={p.name:p.read_bytes() for p in (root/'.ai/generated').glob('*.json')}
    shutil.rmtree(root/'.ai/generated')
    for command in [('build','--view','canonical'),('build','--view','technical-preview'),('report',)]:
        cli(root,*command,'--write-generated')
    assert saved=={p.name:p.read_bytes() for p in (root/'.ai/generated').glob('*.json')}
    assert canonical_graph['graph']['view']=='canonical' and preview['graph']['view']=='technical-preview'
    assert canonical_graph['graph']['authority']!=preview['graph']['authority']
    assert not any(e['kind']=='depends_on' for e in preview['graph']['edges'])
    dependencies=[e for e in preview['graph']['edges'] if e['kind']=='declared_project_reference']
    assert len(dependencies)==5 and all(e['metadata']['interpretation']=='declared-not-evaluated' and
        e['metadata']['active_evaluated_dependency']=='unknown' for e in dependencies)
    unchanged=cli(root,'normalize')
    assert Counter(e['classification'] for e in unchanged['change_set'])=={'unchanged':58}
    assert host(root)==before_host and canonical(root)==installed
    RESULT['lifecycle']={'expected_candidate_kinds':dict(expected),'actual_candidate_kinds':dict(actual),
        'host_files_compared':len(before_host),'canonical_counts':{'claims':29,'evidence':29,'relationships':0},
        'initial_writes':58,'retry_writes':again['writes'],'canonical_graph_counts':{k:len(canonical_graph['graph'][k]) for k in ['nodes','edges']},
        'preview_graph_counts':{k:len(preview['graph'][k]) for k in ['nodes','edges']},'generated_files_regenerated':sorted(saved),
        'unchanged_classifications':{'unchanged':58},'source_inherited_frameworks':'not evaluated; zero framework candidates expected and observed'}
    unit=root/'tests/SyntheticIpm.UnitTests/SyntheticIpm.UnitTests.csproj'
    source_original=unit.read_text();unit.write_text(source_original.replace('<PackageReference','  <PackageReference'))
    formatting=cli(root,'normalize')
    assert ids(normalized,'claims')==ids(formatting,'claims') and ids(normalized,'evidence')==ids(formatting,'evidence')
    assert canonical(root)==installed
    formatting_plan=cli(root,'populate','prepare')['plan']
    assert formatting_plan['blocked'] and not formatting_plan['applicable']
    cli(root,'populate','apply','--plan',formatting_plan['fingerprint'],'--approve',formatting_plan['fingerprint'],expected=1)
    format_counts=dict(Counter(e['classification'] for e in formatting['change_set']))
    # Explicit edits are limited to the disposable fixture.
    changed=source_original.replace('NUnit" Version="4.5.1"','NUnit" Version="4.6.0"')
    changed='\n'.join(line for line in changed.splitlines() if 'NUnit3TestAdapter' not in line and 'ProjectReference' not in line)
    changed=changed.replace('</Project>','<PropertyGroup><TargetFramework>net9.0</TargetFramework></PropertyGroup>'
        '<ItemGroup><ProjectReference Include="$(Unknown)/Missing.csproj" Condition="false"/></ItemGroup></Project>')
    unit.write_text(changed)
    cli(root,'scan');changed_extraction=cli(root,'extract');changed_normalized=cli(root,'normalize')
    changed_plan=cli(root,'populate','prepare')['plan']
    assert changed_plan['blocked'] and not changed_plan['applicable']
    cli(root,'populate','apply','--plan',changed_plan['fingerprint'],'--approve',changed_plan['fingerprint'],expected=1)
    assert canonical(root)==installed
    changed_canonical=cli(root,'build','--view','canonical');changed_preview=cli(root,'build','--view','technical-preview')
    changed_report=cli(root,'report');cli(root,'validate')
    assert canonical_graph==changed_canonical and preview!=changed_preview
    assert changed_report['comparison']['classification_counts'].get('potential update')
    assert any(e['observation']=='stale-content-hash' for e in changed_report['canonical']['source_evidence_observations'])
    assert any('declaration-no-longer-proposed' in reason for e in changed_normalized['change_set'] for reason in e['reasons'])
    assert changed_report['technical_observations']['unresolved_dependencies']
    assert changed_report['technical_observations']['conditional_dependencies']
    stable=ids(normalized,'claims')&ids(changed_normalized,'claims')
    added=ids(changed_normalized,'claims')-ids(normalized,'claims')
    removed=ids(normalized,'claims')-ids(changed_normalized,'claims')
    assert added and removed and stable
    before_removed=canonical(root)
    (root/'src/SyntheticIpm.Domain/SyntheticIpm.Domain.csproj').unlink()
    removed_analysis=cli(root,'normalize'); removed_report=cli(root,'report')
    assert any(e['missing_from_current_inventory'] for e in removed_report['canonical']['source_evidence_observations'])
    assert canonical(root)==before_removed
    RESULT['changes']={'formatting_claim_ids_preserved':len(ids(formatting,'claims')),'formatting_evidence_ids_preserved':len(ids(formatting,'evidence')),
        'formatting_classifications':format_counts,'stable_claim_ids_after_substantive_edits':len(stable),'added_claim_proposals':len(added),
        'removed_declarations_retained_canonically':len(removed),'substantive_classifications':dict(Counter(e['classification'] for e in changed_normalized['change_set'])),
        'blocked_operations':len(changed_plan['blocked']),'canonical_byte_hashes_unchanged':True,
        'missing_source_evidence_detected':True,'canonical_graph_unchanged':True,'technical_preview_changed':True}
    RESULT['guard']={'active_child_processes':(WORK/'guard.log').read_text().count('guard-active'),
                     'forbidden_calls':(WORK/'guard.log').read_text().count('FORBIDDEN')}
    assert RESULT['guard']['forbidden_calls']==0
    (WORK/'results.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    print(json.dumps(RESULT,indent=2,sort_keys=True))

if __name__=='__main__':
    try: main()
    finally:
        (WORK/'partial-results.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
        print('EVIDENCE_DIRECTORY='+str(WORK),file=sys.stderr)
```

</details>

<details><summary>ipm_stage2_recovery_acceptance.py</summary>

```python
import importlib.util,json,subprocess,sys
spec=importlib.util.spec_from_file_location('accept','/tmp/ipm_stage2_acceptance.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
results=[]
for phase,index in [('after_stage',0),('after_install',0),('before_commit',None),('before_journal_replace','COMMITTED'),('after_commit',None)]:
    root=a.fixture('crash-'+phase); baseline=a.canonical(root); host=a.host(root)
    plan=a.cli(root,'populate','prepare')['plan'];fp=plan['fingerprint']
    code='''import os,sys
sys.path.insert(0,sys.argv[1])
import population_transaction as tx
def stop(phase,index=None):
    if phase == %r and index == %r: os._exit(71)
tx._checkpoint=stop
tx.PopulationStore(sys.argv[2]).apply(sys.argv[3],sys.argv[3])
'''%(phase,index)
    command=[sys.executable,'-B','-c',code,str(root/'.ai/tools'),str(root),fp]
    crash=subprocess.run(command,capture_output=True,text=True,env=a.ENV)
    assert crash.returncode==71,(phase,crash.stderr)
    a.LOG.append({'id':len(a.LOG)+1,'fixture':root.name,'args':['python -B -c fault injection',phase,index],
                  'exit_code':crash.returncode,'expected_exit_code':71})
    status=a.cli(root,'populate','status','--plan',fp)
    after=a.canonical(root)
    if phase!='after_commit':
        assert status['recovery_required']
        for command in [('validate',),('build','--view','canonical'),('build','--view','technical-preview'),('report',)]:
            a.cli(root,*command,expected=1)
        first=a.cli(root,'populate','recover','--plan',fp)
        assert first['state']=='ROLLED_BACK' and a.canonical(root)==baseline
        a.cli(root,'validate')
        second=a.cli(root,'populate','recover','--plan',fp)
        assert second['state']=='ROLLED_BACK' and a.canonical(root)==baseline
        applied=a.cli(root,'populate','apply','--plan',fp,'--approve',fp)
        assert applied['writes']==58
    else:
        receipt=root/'.ai/state/population/transactions'/fp.split(':')[1]/'journal.json'
        original=receipt.read_bytes();receipt.unlink()
        for _ in range(2):a.cli(root,'populate','recover','--plan',fp,expected=1)
        assert a.canonical(root)==after
        # Restore only the exact trusted COMMITTED receipt from this attempt.
        receipt.write_bytes(original)
        for _ in range(2):
            recovered=a.cli(root,'populate','recover','--plan',fp)
            assert recovered['state']=='COMMITTED' and a.canonical(root)==after
    committed=a.canonical(root)
    again=a.cli(root,'populate','apply','--plan',fp,'--approve',fp)
    assert again['writes']==0 and a.canonical(root)==committed
    a.cli(root,'validate')
    assert a.host(root)==host
    results.append({'phase':phase,'index':index,'process_exit':71,'first_status':status,
                    'repeated_recovery_safe':True,'idempotent_retry_writes':0,'host_preserved':True,
                    'ambiguous_commit_repeated_refusal_tested':phase=='after_commit'})
# External edit while a real process owns the transaction; rollback removes only its batch.
root=a.fixture('external-edit');baseline=a.canonical(root);host=a.host(root)
plan=a.cli(root,'populate','prepare')['plan'];fp=plan['fingerprint']
human={'id':'human.external','statement':'External concurrent fixture edit retained.',
       'type':'technical_fact','status':'NEEDS_HUMAN_CONFIRMATION','evidence':[],
       'last_verified':None,'depends_on':[],'conflicts_with':[],
       'provenance':{'actor':'external-fixture-author','method':'concurrent-fixture-edit'}}
code='''import json,os,pathlib,sys
sys.path.insert(0,sys.argv[1])
import population_transaction as tx
def stop(phase,index=None):
    if phase=='before_commit':
        (pathlib.Path(sys.argv[2])/'.ai/knowledge/claims/human.json').write_text(json.dumps(%r))
        os._exit(71)
tx._checkpoint=stop
tx.PopulationStore(sys.argv[2]).apply(sys.argv[3],sys.argv[3])
'''%human
crash=subprocess.run([sys.executable,'-B','-c',code,str(root/'.ai/tools'),str(root),fp],env=a.ENV,capture_output=True,text=True)
assert crash.returncode==71,crash.stderr
a.LOG.append({'id':len(a.LOG)+1,'fixture':root.name,'args':['python -B -c fault injection','external-before-commit'],'exit_code':71,'expected_exit_code':71})
external_file=root/'.ai/knowledge/claims/human.json';external_bytes=external_file.read_bytes()
for _ in range(2):a.cli(root,'populate','recover','--plan',fp,expected=1)
expected=dict(baseline);expected['.ai/knowledge/claims/human.json']=a.hashlib.sha256(external_bytes).hexdigest()
assert a.canonical(root)==expected and external_file.read_bytes()==external_bytes
a.cli(root,'validate',expected=1)
a.cli(root,'build','--view','canonical',expected=1)
a.cli(root,'populate','apply','--plan',fp,'--approve',fp,expected=1)
assert a.canonical(root)==expected and a.host(root)==host
results.append({'phase':'external-edit-before-commit','external_bytes_preserved':True,
                'own_batch_rolled_back':True,'recovery_required_until_explicit_manual_reconciliation':True,'ordinary_reads_and_retry_remain_gated':True})
result={'workspace':str(a.WORK),'scenarios':results,'commands':a.LOG,
        'guard':{'active_child_processes':(a.WORK/'guard.log').read_text().count('guard-active'),
                 'forbidden_calls':(a.WORK/'guard.log').read_text().count('FORBIDDEN')}}
assert result['guard']['forbidden_calls']==0
(a.WORK/'recovery-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True,indent=2))
```

</details>
