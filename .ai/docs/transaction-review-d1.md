# Increment D.1 transaction and Windows portability review

Baseline: 27f9aa69004ce769f19e6cdc58f697db9cb36515.
Scope: local Windows 11/NTFS, CPython 3.12+, and portable transaction regressions.
Execution environment for this review: Linux, CPython 3.12.14. Native Windows
results are NOT available. Mocks are identified as mocks, not NTFS verification.
Use the separate [native Windows checklist](windows11-ntfs-checklist.md).

## Reproduced findings and fixes

| ID | Severity | Baseline failure | Minimal fix |
|---|---|---|---|
| D1-01 | High | If COMMITTED was persisted but its journal was subsequently lost before staged-link cleanup, the first recover created RECOVERY_REQUIRED. A second recover treated that marker as an ordinary uncommitted transaction and deleted committed records. | Rollback with existing targets requires recorded STAGING history. Ambiguous orphans remain blocked without demoting their state. Legacy RECOVERY_REQUIRED markers without initial STAGING proof are also blocked. |
| D1-02 | Medium | Control JSON was checked using read_bytes, then reopened using kb.read_json. Replacement between reads made the parser consume unchecked bytes. | Parse the checked byte snapshot once; retain duplicate-key and nonfinite-number rejection. The canonical validator is unchanged. |
| D1-03 | Medium | An error from msvcrt.locking(...LK_UNLCK...) skipped os.close, leaking the coordinator descriptor and potentially retaining locks in a long-lived process. | Close the descriptor in an inner finally, including acquire/unlock/body failure paths. |
| D1-04 | Medium | Canonical hashes were checked before the final source observation. A canonical edit during that observation could be followed by COMMITTED without detecting the changed baseline. | Recheck installed ownership/hashes and the original canonical snapshot after the final source observation, immediately before committing. |

Five new targeted regression cases failed against the baseline: repeated recovery,
legacy ambiguous marker, checked-JSON replacement, mocked Windows unlock failure,
and a canonical edit during final observation. All pass after the fixes.
Further tests cover strict control JSON, mocked byte-zero locking and acquisition
failure, closed write handles before link/replace, and a persistent simulated
Windows sharing denial that remains recoverable after the denial is released.
No approval, ID, hash, link-count, lifecycle or validation check was relaxed.

## API and protocol audit

The CPython 3.12.14 backend sources were inspected:

- [PC/msvcrtmodule.c](https://github.com/python/cpython/blob/v3.12.14/PC/msvcrtmodule.c):
  locking calls the CRT _locking function. Its documented region starts at the
  descriptor position, may extend beyond EOF, and raises OSError on failure.
  The product explicitly seeks to byte zero for acquire/unlock, uses one byte,
  LK_NBLCK for nonblocking acquisition and LK_UNLCK for release. The persistent
  coordinator is intentionally not renamed or unlinked while open. These call
  conventions are covered by portable mocks; actual CRT locking still needs the
  two-process native test.
- [Modules/posixmodule.c](https://github.com/python/cpython/blob/v3.12.14/Modules/posixmodule.c):
  Windows os.link uses CreateHardLinkW and os.replace uses MoveFileExW with
  MOVEFILE_REPLACE_EXISTING. The Windows link backend does not use the
  follow_symlinks argument as the POSIX backend does. The product must therefore
  rely on rejecting links/junctions and using a stable, trusted directory tree;
  that argument is not an additional Windows race-safety guarantee.
- Hardlink creation is used only for absent canonical destinations. Replacement
  is used only for the internal journal. Source/write handles are closed before
  either call. NTFS delete-sharing denials from other software can still cause
  PermissionError: the product does not force deletion or weaken checks.
- Staged ownership requires samefile plus exactly two links and matching content.
  Cleanup should leave one canonical link. Existing unexpected hardlinks remain
  rejected. Portable tests exercise these with real local hardlinks; native
  st_dev/st_ino/st_nlink behavior must be measured on NTFS.
- Temporary validation directories are separate from transaction staging. Their
  files are closed by context managers; cleanup failures are not ignored.
  Transaction staging is under .ai on the same volume as its canonical targets.

## Race and recovery boundaries

Cooperating D operations and ordinary CLI readers hold the coordinator lock.
Direct library readers, applications that ignore the lock, and commands begun
before first coordination are outside that serialization.

Control JSON now uses one verified byte snapshot. Plan hashes still bind exact
approval; journal checksums detect accidental corruption, not an authenticated
or monotonic history. Arbitrary external journal replacement or restoring an old
receipt cannot be automatically interpreted as safe rollback authorization.
Lost or ambiguous commit proof requires manual review; do not invent a replacement
history or repeatedly retry expecting the tool to discard committed knowledge.

The final canonical recheck closes the reproduced observation window, but no
portable check-then-unlink/replace sequence can prevent every hostile concurrent
path replacement. In particular, concurrent ancestor junction/reparse-point
replacement or replacing a file after ownership verification is not protected
by directory handles on Windows. Do not run with uncoordinated/hostile writers.
This review does not claim adversarial same-privilege filesystem isolation.

NTFS sharing/ACL/read-only failures, antivirus activity, cloud/reparse providers,
long-path configuration, and process termination during cleanup remain native
verification requirements. Do not use OneDrive, SMB, ReFS, FAT/exFAT or WSL as
evidence for local native NTFS behavior.

No cross-file atomicity or arbitrary power-loss durability is claimed. Windows
has no directory fsync in this implementation; per-file fsync and journal
replacement are not a tested power-failure guarantee. Recovery tests establish
process-interruption behavior, not storage-controller or OS-crash behavior.

Canonical knowledge, Contract v1.0, schemas and the core validator are unchanged.
No real-repository population or Increment E work is part of this review.
