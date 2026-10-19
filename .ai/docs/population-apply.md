# Stage 2 Increment D: approved, recoverable add-only population

This extension preserves Contract v1.0, the schemas, core validator and A–C
implementations. It stores validated proposals, not semantic truth. New technical
claims remain NEEDS_HUMAN_CONFIRMATION with last_verified=null. Evidence retains
the exact provenance and actual observation timestamp of the approved plan.
No human-review event is generated. Graph building and reporting are separate read-only Increment E extensions; see
[graph semantics](graphs-and-reports.md).

## Existing canonical contract

Canonical JSON records are recursive under knowledge/claims,
knowledge/relationships and evidence. IDs are globally unique across all three
groups; filenames are not IDs in v1. Unknown formats, duplicate IDs, dangling
references, invalid status/evidence rules and dependency cycles are rejected by
the existing validator. Claims/evidence have mutual references and must be
installed as a batch, not treated as independent successful writes.

New files use population-SHA256(record ID).json in the appropriate canonical
directory. This avoids Windows filename restrictions and never gives record IDs
authority over paths. Occupied filenames and existing IDs are not replaced.
Human Markdown, canonical source metadata, manifest and schemas are included
in the canonical preparation fingerprint but are never written by population.

## CLI and approval

~~~text
python -B .ai/tools/kb.py populate prepare --json
python -B .ai/tools/kb.py populate status --json
python -B .ai/tools/kb.py populate apply --plan sha256:FULL_HASH --dry-run --json
python -B .ai/tools/kb.py populate apply --plan sha256:FULL_HASH --approve sha256:FULL_HASH --json
python -B .ai/tools/kb.py populate recover --plan sha256:FULL_HASH --json
~~~

populate with no action means prepare. Prepare makes no canonical changes. It
saves a write-once, content-addressed plan under state/population/plans and
returns its exact JSON for review. apply without --approve refuses canonical
mutation. --dry-run performs all preflight checks and validates the complete
result without starting a transaction. Generic --yes is not supported.
Plan options take fingerprints, not arbitrary filesystem paths.
Runtime plans, locks and journals are machine-local and ignored by .ai/.gitignore;
explicit examples under generated/ remain reviewable. Do not switch checkouts or
edit canonical records while a transaction requires recovery.

Review the exact saved plan, including all records and timestamps. Approval is
the explicit --approve value equal to that plan's SHA-256 fingerprint. A new
prepare performs a new observation and generally has a different timestamp and
fingerprint. Old approval cannot authorize it. The fingerprint is deterministic
for the exact plan payload, independent of JSON key ordering; it excludes only
its own fingerprint field. It is integrity binding, not user authentication or a
cryptographic signature. There is no external approval service.

The plan contains exact proposed records, classifications, eligible/blocked
operations, canonical byte/tree fingerprint, source inventory and source-byte
fingerprints, operation hashes, record dependencies and a binding to the resolved
repository root. Relocation requires a new plan. Source fingerprints cover all
supported files, including empty solutions without extracted membership.
Selected metadata only is stored; no complete project/source files are copied.

Only add is eligible. unchanged records are retained without writes. potential
update, conflict and unresolved classifications block the entire plan, even if
some other additions are eligible. There is no automatic replacement, deletion,
reactivation, retraction, supersession, conflict resolution or status promotion.
There is no cherry-picking: an approved plan is applied in its entirety or not
applied. Resolve blockers outside this workflow and prepare a new plan.

## Preflight before mutation

Under an exclusive OS lock, apply verifies the saved fingerprint and approval,
canonical byte snapshot, current sources and fresh A/B/C output. Fresh normalized
records must exactly match the approved payload, preserving prepared timestamps.
It reuses kb.validate in isolated staging for the complete resulting dataset.
Lifecycle restrictions, classifications, operation hashes, destination paths,
global ID collisions and references are checked before canonical writes.
Inputs are rechecked after staging and before commit.

The existing core validator is not replaced. Canonical status promotion is not
made valid merely by structural validation. Unsupported or stale inputs fail
with diagnostics requiring reconciliation or a new preparation.

## Recoverable protocol and explicit states

All coordination and journal data is under state/population. Locking uses
fcntl.flock on POSIX or msvcrt.locking on Windows. The lock file is persistent;
locks are released by the OS when a process exits. No PID-age guessing or
automatic breaking of live locks is used. Concurrent application attempts fail
as busy. A failed initial state-directory creation can be retried with prepare.

Transaction states are STAGING, INSTALLING, COMMITTED, ROLLING_BACK, ROLLED_BACK
and RECOVERY_REQUIRED. A directory without a completed initial journal is
ORPHANED and recoverable. Every journal update uses an fsynced temporary file,
atomic replacement of internal journal metadata, and a content checksum.
An orphan with existing destination files cannot be a normal initial-creation
interruption; recovery preserves those files for manual journal review.
Repeated recovery must not reinterpret that ambiguity as rollback authorization;
legacy markers without initial STAGING history remain blocked as well.

1. Persist STAGING and write/fsync all proposed addition files in the transaction
   staging directory. Staging never alters canonical records.
2. Recheck inputs and persist INSTALLING.
3. Install each staged file with os.link, which atomically creates a destination
   without replacing an existing object. Fsync canonical directories on POSIX.
   No non-atomic copy or overwrite fallback is provided.
4. Check installed hashes and staging inode ownership, preserve the original
   canonical snapshot excluding only owned additions, validate the full canonical
   dataset, and recheck sources.
5. Persist COMMITTED, then unlink redundant internal staging links. Canonical
   files remain with the exact approved bytes. Successful apply records no
   semantic verification.

Filesystem hardlinks on the same volume are required. Unsupported filesystems
fail safely and roll back. Symlinks, junctions, special files, unexpected existing
hardlinks, unsafe paths and unsupported record formats are rejected. Known
staging-to-canonical hardlink pairs are the sole temporary link exception.

This is NOT multi-file atomic publication. An uncoordinated reader can see
intermediate files during installation. Once population coordination exists,
ordinary kb.py CLI operations hold the same lock throughout their execution and
refuse to proceed while population is busy or interrupted, reporting
status/recovery instructions. Commands started before the first prepare, direct
library users and external readers must coordinate or run only when the store is
quiescent. No lock/state is created by read-only A–C commands.

Caught failures roll back owned uncommitted additions. On process interruption,
the journal remains and further prepare/apply operations are blocked until
recover. Recovery uses the immutable plan and actual staged/canonical inode
identity plus hashes, not only the installed count, so a crash between linking
and updating progress is recoverable.

Recovery rolls back uncommitted transactions, including a complete batch whose
COMMITTED marker was not persisted. It never forwards an uncommitted plan.
Rollback removes only unchanged, transaction-owned additions and checks the
original canonical fingerprint and validator before recording ROLLED_BACK.
Rollback is itself interruptible and retryable. Removing uncommitted owned files
is rollback, not a supported deletion operation on existing knowledge.

Existing or concurrent edits are never overwritten or silently removed. If an
installed file was modified, replaced, additionally linked, or a pre-existing
canonical file changed, recovery preserves it and records RECOVERY_REQUIRED.
Reconcile/back up those edits explicitly, restore the preparation snapshot or
remove the conflicting uncommitted artifact yourself, then retry recover. The
tool cannot safely guess how to merge arbitrary concurrent human edits.
Reserved internal staging/journal files contain only disposable operational
data and must not be used for human-authored knowledge.

Once COMMITTED, recover only verifies the receipt and finishes internal cleanup;
it never deletes committed records. Repeated approved apply is an idempotent
no-op after verifying installed bytes and full validation. A missing/edited
committed target is an error, not permission to recreate or replace it.
An interrupted rollback can be retried; a fresh approved retry after ROLLED_BACK
is allowed only if the original plan remains current.

The guarantees assume cooperating writers, a stable input tree and reliable
local filesystem locking/linking. Atomic single-file operations and POSIX fsync
are used; cross-file atomicity, malicious same-privilege filesystem replacement,
network filesystem lock semantics, or arbitrary power-loss durability on every
platform are not claimed. Windows directory fsync is unavailable through this
implementation; native Windows execution must be reported separately from
portable path/guard tests.

## Verification

~~~text
python -B -m unittest discover -s .ai/tools/tests -p 'test_*.py'
python -B .ai/tools/kb.py validate --json
~~~

Tests use disposable synthetic repositories for actual apply/recovery, including
stage failures, partial installation, journal/commit interruption, rollback
interruption, concurrent apply and preservation of human edits. They exercise
real no-replace links and OS locks, not only a simulated transaction model.
The host repository's canonical records are not populated by these tests.

See the [D.1 review and fixes](transaction-review-d1.md) and the separate
[native Windows 11/NTFS checklist](windows11-ntfs-checklist.md). Native Windows
results must be distinguished from portable tests and mocked API checks.
