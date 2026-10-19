# Native Windows 11 / NTFS verification checklist

Status: NOT EXECUTED in the Linux D.1 review. This is a separate native run.
Record Windows build, Python executable/version/architecture, volume filesystem,
ACLs, path length, antivirus configuration and every test's actual outcome.
Use native python.exe on local NTFS, not WSL, Wine, SMB or a cloud-synced folder.
Python 3.12+ is required. Do not populate the real repository.

## 1. Setup and suite

From the checkout containing the reviewed implementation, in PowerShell:

~~~powershell
$repoRoot = (Get-Location).Path
$cli = Join-Path $repoRoot '.ai\tools\kb.py'
$pythonExe = (Get-Command python.exe).Source
& $pythonExe --version
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber
& $pythonExe -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Regression suite failed' }
~~~

- Record passed/failed/skipped counts. FIFO tests are Unix-only; symlink tests
  may skip without Developer Mode/privileges. A skip is not a native pass.
- The suite includes a real child-process os._exit interruption, recovery,
  concurrent process locking, retry, and portable mocked Windows API tests.
  Identify mocked tests separately even when running on Windows.
- Record any TemporaryDirectory cleanup/sharing failure, traceback or leaked
  process/handle. Do not enable ignore_cleanup_errors or disable integrity checks.

## 2. Disposable synthetic fixture and immutable plan

~~~powershell
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('kb-d1-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
Get-Volume -DriveLetter ((Get-Item $fixtureRoot).PSDrive.Name) |
    Select-Object DriveLetter, FileSystem
& $pythonExe -B $cli init --root $fixtureRoot --json
if ($LASTEXITCODE -ne 0) { throw 'Fixture init failed' }
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'A.csproj'),
  '<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include="B.csproj"/></ItemGroup></Project>')
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'B.csproj'), '<Project/>')
$sourceBefore = Get-ChildItem $fixtureRoot -Filter '*.csproj' | Get-FileHash -Algorithm SHA256
$prepared = (& $pythonExe -B $cli populate prepare --root $fixtureRoot --json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Prepare failed' }
$planId = $prepared.fingerprint
~~~

- Verify the volume says NTFS. Keep this root until all recovery steps finish.
- Inspect the exact plan: no blocked operations, only add, related claim/evidence
  IDs, fixed observation timestamps, source and canonical fingerprints.
- Record canonical baseline bytes/hashes before mutation. Prepare must not change
  them. Control state under .ai/state/population is expected.
- Do not regenerate the plan between approval and apply: a new observation is a
  new fingerprint. Moving/copying the fixture requires a new bound plan.
- Missing approval must fail; dry run must validate without a transaction:

~~~powershell
& $pythonExe -B $cli populate apply --root $fixtureRoot --plan $planId --json
if ($LASTEXITCODE -eq 0) { throw 'Missing approval was accepted' }
& $pythonExe -B $cli populate apply --root $fixtureRoot --plan $planId --dry-run --json
if ($LASTEXITCODE -ne 0) { throw 'Dry run failed' }
~~~

## 3. Native interrupted application and recovery

Terminate a real Python process immediately after its first canonical link:

~~~powershell
$crashScript = @'
import os, sys
sys.path.insert(0, sys.argv[1])
import population_transaction as tx
def stop(phase, index=None):
    if phase == 'after_install' and index == 0:
        os._exit(71)
tx._checkpoint = stop
tx.PopulationStore(sys.argv[2]).apply(sys.argv[3], sys.argv[3])
'@
& $pythonExe -B -c $crashScript (Split-Path $cli) $fixtureRoot $planId
if ($LASTEXITCODE -ne 71) { throw 'Expected interruption point was not reached' }
& $pythonExe -B $cli populate status --root $fixtureRoot --plan $planId --json
& $pythonExe -B $cli validate --root $fixtureRoot --json
if ($LASTEXITCODE -eq 0) { throw 'Ordinary CLI was not gated during interruption' }
& $pythonExe -B $cli populate recover --root $fixtureRoot --plan $planId --json
if ($LASTEXITCODE -ne 0) { throw 'Recovery failed' }
& $pythonExe -B $cli validate --root $fixtureRoot --json
if ($LASTEXITCODE -ne 0) { throw 'Recovered baseline is invalid' }
~~~

- Verify lock release after process death, INSTALLING/recovery-required status,
  exact baseline restoration, ROLLED_BACK, and no unexpected canonical deletions.
- In separate fresh fixtures repeat interruption at after_stage, before_commit,
  before_journal_replace with index COMMITTED, and after_commit.
- After after_commit, recovery must only verify/clean internal links and retain
  all committed bytes. Repeat recovery twice.
- Separately delete the committed journal in an after_commit fixture, preserving
  it outside .ai first. Two recover calls must BOTH refuse to remove any record.
  Restore only the exact trusted COMMITTED receipt for subsequent cleanup.
  Do not fabricate STAGING history or restore an older INSTALLING receipt.

## 4. Successful application, link counts and retry

~~~powershell
& $pythonExe -B $cli populate apply --root $fixtureRoot --plan $planId --approve $planId --json
if ($LASTEXITCODE -ne 0) { throw 'Approved apply failed' }
& $pythonExe -B $cli populate apply --root $fixtureRoot --plan $planId --approve $planId --json
if ($LASTEXITCODE -ne 0) { throw 'Idempotent retry failed' }
& $pythonExe -B $cli validate --root $fixtureRoot --json
if ($LASTEXITCODE -ne 0) { throw 'Final canonical validation failed' }
& $pythonExe -B $cli check-scaffold --root $fixtureRoot --json
Get-ChildItem $fixtureRoot -Filter '*.csproj' | Get-FileHash -Algorithm SHA256
~~~

- Compare source hashes with sourceBefore and existing human-record baseline.
- First apply must store exactly the eligible batch; retry must report writes=0.
- Compare installed JSON with the approved payload, including captured_at.
  Claims must remain NEEDS_HUMAN_CONFIRMATION; last_verified must remain null.
- In an interrupted fixture before cleanup, use native Python os.stat and
  os.path.samefile to record staged/canonical st_dev, st_ino and st_nlink:
  same file, matching bytes, two links. After cleanup, one canonical link.
- fsutil hardlink list on a chosen record can independently inspect NTFS names.
  Release all diagnostic handles before recovery.
- A pre-existing destination must not be overwritten by CreateHardLinkW.
  Unexpected third hardlinks must be rejected, not silently cleaned.

## 5. Native two-process locking and Windows sharing

- Hold PopulationStore(fixtureRoot).coordinate() in process A. In process B,
  approved apply and ordinary validate must fail as busy, with no canonical edits.
- Release process A and retry successfully. Repeat by terminating process A;
  the OS must release the lock. Do not delete or rename coordination.lock.
- Verify the persistent lock has one byte; acquire/unlock must use offset zero.
  The portable mocks establish call order, not native CRT behavior.
- On a fresh fixture, use a diagnostic Windows CreateFile handle to open
  journal.json without FILE_SHARE_DELETE while apply attempts a progress replace.
  Record the sharing violation. It must not produce a false successful commit.
  Release the external handle, then recover and validate the original baseline.
- Similarly test a held staged/canonical handle during cleanup, read-only
  attributes and restrictive ACLs. Expect a safe error/pending cleanup or recovery,
  not permission changes, forced overwrite or silent loss of human edits.
- Repeat normal success/cleanup with antivirus enabled and a path containing
  spaces/non-ASCII. Test long paths separately only if already enabled; record
  the actual configuration rather than changing machine policy for a pass.

## 6. Acceptance record and cleanup

Record each scenario's command, exit code, journal state, canonical/source hash
comparison, lock/handle observations and final validator result. Preserve logs
outside the fixture; never report a checklist item as passed without execution.
Linux results and mocked Windows paths cannot establish native NTFS durability.
Process-exit tests do not prove survival of power loss or storage failure.

Remove disposable roots only after all handles/processes are closed and any
recovery is finished. A sharing-denied cleanup is a finding, not a reason to
weaken tests. The real repository must still have no canonical additions.
