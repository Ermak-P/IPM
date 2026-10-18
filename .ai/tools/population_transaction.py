"""Add-only, approved, recoverable population. No multi-file atomicity claim."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import kb
from population_dotnet import DotNetAnalyzer, canonical_json, read_source
from population_normalize import (CandidateNormalizer, GROUPS, load_canonical,
                                  utc_now, validate_records)
from population_scan import RepositoryScanner

FINGERPRINT = re.compile(r'^sha256:[a-f0-9]{64}$')
TERMINAL = {'COMMITTED', 'ROLLED_BACK'}
STATES = {'STAGING', 'INSTALLING', 'ROLLING_BACK', 'RECOVERY_REQUIRED', *TERMINAL}
LIMIT = 64 * 1024 * 1024


class PopulationError(ValueError):
    """Stable actionable error code, never a source-content or OS-path dump."""


def require(condition, code):
    if not condition:
        raise PopulationError(code)


def encoded(value):
    return (canonical_json(value) + '\n').encode('utf-8')


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return sha(canonical_json(value).encode('utf-8'))


def seal(value):
    result = deepcopy(value)
    result.pop('fingerprint', None)
    result['fingerprint'] = fingerprint(result)
    return result


def verify_seal(value, expected=None):
    require(isinstance(value, dict), 'invalid-sealed-document')
    identifier = value.get('fingerprint')
    require(isinstance(identifier, str) and FINGERPRINT.fullmatch(identifier),
            'invalid-fingerprint')
    require(seal(value) == value and (expected is None or identifier == expected),
            'fingerprint-mismatch')
    return value


def _checkpoint(phase, index=None):
    """Tests inject process interruption here. No CLI fault-injection option."""


def regular(path, single_link=False):
    require(not path.is_symlink() and not path.is_junction(), 'links-not-allowed')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), 'unexpected-filesystem-object')
    require(not single_link or info.st_nlink == 1, 'unexpected-hardlink')
    return info


def read_bytes(path, single_link=True):
    info = regular(path, single_link)
    require(info.st_size <= LIMIT, 'control-file-too-large')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and
                (opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino),
                'file-changed-during-open')
        value = stream.read(LIMIT + 1)
    require(len(value) <= LIMIT, 'control-file-too-large')
    return value


def read_json(path):
    # Reuse core duplicate-key/NaN rejection after checking the object type.
    read_bytes(path)
    return kb.read_json(path)


def sync_directory(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_new(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


class PopulationStore:
    def __init__(self, root):
        self.root = Path(root)
        require(not self.root.is_symlink() and not self.root.is_junction() and self.root.is_dir(),
                'root-must-be-a-real-directory')
        self.root = self.root.resolve()
        self.base = self.root / '.ai'
        self.state = self.base / 'state/population'
        self.plans = self.state / 'plans'
        self.transactions = self.state / 'transactions'
        self.safe_tree()

    def safe_tree(self):
        require(self.base.is_dir() and not self.base.is_symlink() and not self.base.is_junction(),
                'initialized-real-ai-store-required')
        pending = [self.base]
        while pending:
            directory = pending.pop()
            require(not directory.is_symlink() and not directory.is_junction(), 'links-not-allowed')
            for entry in sorted(directory.iterdir()):
                require(not entry.is_symlink() and not entry.is_junction(), 'links-not-allowed')
                mode = entry.lstat().st_mode
                if stat.S_ISDIR(mode):
                    pending.append(entry)
                else:
                    require(stat.S_ISREG(mode), 'unexpected-filesystem-object')

    def directories(self):
        for path in [self.base / 'state', self.state, self.plans, self.transactions]:
            if not path.exists():
                path.mkdir()
                sync_directory(path.parent)
            require(path.is_dir() and not path.is_symlink() and not path.is_junction(),
                    'unsafe-state-directory')

    @contextmanager
    def coordinate(self, create=False):
        self.safe_tree()
        if create:
            self.directories()
        path = self.state / 'coordination.lock'
        if not path.exists() and not create:
            require(not self.state.exists(), 'incomplete-coordination-state')
            yield
            return
        if path.exists():
            regular(path, True)
        flags = os.O_RDWR | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        if create:
            flags |= os.O_CREAT
        fd = os.open(path, flags, 0o600)
        locked = False
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 1,
                    'unsafe-coordination-file')
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                raise PopulationError('population-busy-retry-after-current-operation') from None
            if create and info.st_size == 0:
                os.write(fd, b'0')
                os.fsync(fd)
                sync_directory(path.parent)
            yield
        finally:
            if locked:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def canonical_snapshot(self, ignore=()):
        self.safe_tree()
        ignored = set(ignore)
        entries = {}
        for name in ['knowledge', 'evidence', 'sources', 'schema', 'manifest.yaml']:
            start = self.base / name
            require(start.exists(), 'canonical-layout-incomplete')
            for path in [start, *sorted(start.rglob('*'))] if start.is_dir() else [start]:
                relative = path.relative_to(self.base).as_posix()
                if path.is_dir():
                    entries[relative] = {'kind': 'directory'}
                elif relative not in ignored:
                    entries[relative] = {'kind': 'file', 'hash': sha(read_bytes(path))}
        return {'fingerprint': fingerprint(entries), 'entries': entries}

    def observe(self, exclusions=()):
        inventory = RepositoryScanner().scan(self.root, exclusions)
        require(inventory['ok'], 'scan-incomplete')
        extraction = DotNetAnalyzer().extract(self.root, inventory)
        require(extraction['ok'], 'extraction-incomplete')
        files = [{'path': entry['path'],
                  'hash': sha(read_source(self.root, entry['path'], inventory['exclusions']))}
                 for entry in inventory['sources']]
        source = {'exclusions': inventory['exclusions'], 'files': files,
                  'inventory_fingerprint': fingerprint(inventory),
                  'extraction_fingerprint': fingerprint(extraction)}
        source['fingerprint'] = fingerprint(source)
        return extraction, source

    def target(self, group, identifier):
        require(group in GROUPS and isinstance(identifier, str), 'invalid-operation')
        # Filenames are independent of record ID spelling and Windows path syntax.
        return GROUPS[group] + '/population-' + hashlib.sha256(identifier.encode()).hexdigest() + '.json'

    def assemble(self, report, source, canonical):
        require(report['ok'], 'normalization-or-validation-failed')
        records = report['records']
        classifications = report['change_set']
        changes = {entry['id']: entry for entry in classifications}
        blocked = [deepcopy(e) for e in classifications
                   if e['classification'] not in ['add', 'unchanged']]
        eligible = []
        for group in GROUPS:
            for record in records[group]:
                change = changes[record['id']]
                if change['classification'] != 'add':
                    continue
                target = self.target(group, record['id'])
                if (self.base / target).exists():
                    blocked.append({'id': record['id'], 'record_type': group,
                                    'classification': 'conflict', 'reasons': ['target-path-occupied']})
                    continue
                requires = (record['evidence'] + record['depends_on'] + record['conflicts_with']
                            if group == 'claims' else record['substantiates']
                            if group == 'evidence' else [record['from'], record['to']])
                eligible.append({'id': record['id'], 'record_type': group, 'action': 'add',
                                 'path': target, 'hash': sha(encoded(record)),
                                 'requires': sorted(set(requires))})
        return seal({'format': 'population-plan-v1', 'policy': 'add-only-entire-plan',
                     'repository_binding': sha(str(self.root).encode('utf-8')),
                     'observation': deepcopy(report['observation']),
                     'canonical': canonical, 'sources': source,
                     'records': deepcopy(records), 'classifications': deepcopy(classifications),
                     'eligible': sorted(eligible, key=lambda op: (op['record_type'], op['id'])),
                     'blocked': sorted(blocked, key=canonical_json),
                     'applicable': not blocked})

    def plan_path(self, identifier):
        require(isinstance(identifier, str) and FINGERPRINT.fullmatch(identifier), 'invalid-plan-fingerprint')
        return self.plans / (identifier[7:] + '.json')

    def load_plan(self, identifier):
        plan = verify_seal(read_json(self.plan_path(identifier)), identifier)
        require(plan.get('format') == 'population-plan-v1', 'unsupported-plan-format')
        return plan

    def transaction_path(self, identifier):
        self.plan_path(identifier)  # Validate, never interpret a user path.
        return self.transactions / identifier[7:]

    def journal(self, identifier):
        directory = self.transaction_path(identifier)
        if not directory.exists():
            return None
        require(directory.is_dir(), 'unexpected-transaction-object')
        path = directory / 'journal.json'
        if not path.exists():
            return {'state': 'ORPHANED', 'plan': identifier}
        journal = verify_seal(read_json(path))
        require(journal.get('plan') == identifier and journal.get('state') in STATES,
                'invalid-transaction-journal')
        return journal

    def all_transactions(self):
        if not self.transactions.exists():
            return []
        result = []
        for directory in sorted(self.transactions.iterdir()):
            require(directory.is_dir() and re.fullmatch('[a-f0-9]{64}', directory.name),
                    'unexpected-transaction-object')
            result.append(self.journal('sha256:' + directory.name))
        return result

    def no_pending(self):
        require(all(journal['state'] in TERMINAL for journal in self.all_transactions()),
                'recovery-required-run-populate-recover-before-continuing')

    def prepare(self, exclusions=()):
        with self.coordinate(create=True):
            self.no_pending()
            canonical = self.canonical_snapshot()
            extraction, sources = self.observe(exclusions)
            report = CandidateNormalizer().normalize(self.root, extraction)
            require(report['ok'], 'normalization-or-validation-failed')
            require(self.canonical_snapshot() == canonical, 'canonical-changed-during-prepare')
            require(self.observe(exclusions)[1] == sources, 'sources-changed-during-prepare')
            plan = self.assemble(report, sources, canonical)
            path = self.plan_path(plan['fingerprint'])
            try:
                write_new(path, encoded(plan))
            except FileExistsError:
                require(read_json(path) == plan, 'immutable-plan-collision')
            return {'ok': True, 'dry_run': True, 'plan': plan,
                    'fingerprint': plan['fingerprint'], 'path': path.relative_to(self.base).as_posix()}

    def check_plan(self, plan):
        require(plan.get('policy') == 'add-only-entire-plan', 'only-add-is-supported')
        require(plan.get('applicable') is True and not plan.get('blocked'),
                'blocked-plan-resolve-conflicts-unresolved-or-updates-and-prepare-again')
        require(all(e['classification'] in ['add', 'unchanged'] for e in plan['classifications']),
                'unsupported-classification-add-only')
        require(validate_records(self.base, plan['records'])['ok'], 'invalid-proposed-dataset')
        records = {r['id']: (group, r) for group in GROUPS for r in plan['records'][group]}
        require(len(records) == sum(map(len, plan['records'].values())), 'duplicate-proposed-ids')
        for record in plan['records']['claims']:
            require(record['type'] == 'technical_fact' and record['status'] == 'NEEDS_HUMAN_CONFIRMATION'
                    and record['last_verified'] is None, 'lifecycle-promotion-or-review-event-not-supported')
        for op in plan['eligible']:
            require(op['action'] == 'add' and op['id'] in records, 'only-add-is-supported')
            group, record = records[op['id']]
            require(group == op['record_type'] and op['path'] == self.target(group, record['id'])
                    and op['hash'] == sha(encoded(record)), 'operation-record-or-path-mismatch')

    def preflight_apply(self, plan):
        require(self.canonical_snapshot() == plan['canonical'], 'stale-canonical-state-prepare-again')
        extraction, sources = self.observe(plan['sources']['exclusions'])
        require(sources == plan['sources'], 'stale-source-inputs-prepare-again')
        self.check_plan(plan)
        report = CandidateNormalizer().normalize(self.root, extraction)
        require(report['ok'], 'normalization-or-validation-failed')
        # Re-observation verifies facts, not a license to change approved observation times.
        report['observation']['captured_at'] = plan['observation']['captured_at']
        additions = {e['id'] for e in report['change_set'] if e['classification'] == 'add'}
        for evidence in report['records']['evidence']:
            if evidence['id'] in additions:
                evidence['captured_at'] = plan['observation']['captured_at']
        require(self.assemble(report, sources, plan['canonical']) == plan,
                'plan-does-not-match-fresh-normalization-prepare-again')
        existing = load_canonical(self.base)
        identifiers = {r['id'] for group in GROUPS for r in existing[group]}
        for op in plan['eligible']:
            require(op['id'] not in identifiers, 'existing-id-collision-no-replacement')
            require(not (self.base / op['path']).exists(), 'target-path-occupied-no-replacement')
        additions = self.operation_records(plan)
        combined = {group: existing[group] + additions[group] for group in GROUPS}
        validation = validate_records(self.base, combined)
        require(validation['ok'], 'invalid-complete-resulting-dataset')
        return validation

    @staticmethod
    def operation_records(plan):
        ids = {op['id'] for op in plan['eligible']}
        return {group: [r for r in plan['records'][group] if r['id'] in ids] for group in GROUPS}

    def transition(self, identifier, state, installed=0, attempt=None):
        directory = self.transaction_path(identifier)
        old = self.journal(identifier)
        history = list(old.get('history', [])) if old else []
        history.append({'state': state, 'at': utc_now()})
        journal = seal({'plan': identifier, 'state': state, 'installed': installed,
                        'attempt': attempt if attempt is not None else old.get('attempt', 1),
                        'history': history})
        temporary = directory / 'journal.next'
        if temporary.exists():
            regular(temporary, True)
            temporary.unlink()  # Reserved incomplete journal write, never canonical data.
        write_new(temporary, encoded(journal))
        _checkpoint('before_journal_replace', state)
        os.replace(temporary, directory / 'journal.json')  # Internal metadata only.
        sync_directory(directory)
        return journal

    def stage_path(self, identifier, index):
        return self.transaction_path(identifier) / 'staged' / f'{index:06}.json'

    def owns(self, plan, index):
        op = plan['eligible'][index]
        target, staged = self.base / op['path'], self.stage_path(plan['fingerprint'], index)
        if not target.exists() or not staged.exists():
            return False
        regular(target)
        regular(staged)
        return (target.stat().st_nlink == 2 and os.path.samefile(target, staged)
                and sha(read_bytes(target, False)) == op['hash'])

    def check_installed(self, plan, require_owned=False):
        for index, op in enumerate(plan['eligible']):
            target = self.base / op['path']
            require(target.exists() and sha(read_bytes(target, False)) == op['hash'],
                    'installed-record-changed-preserve-and-review')
            if require_owned or target.stat().st_nlink != 1:
                require(self.owns(plan, index), 'installed-record-ownership-changed-preserve-and-review')

    def clear_stage(self, plan, committed=False):
        directory = self.transaction_path(plan['fingerprint']) / 'staged'
        if not directory.exists():
            return
        expected = {f'{index:06}.json': index for index in range(len(plan['eligible']))}
        for path in sorted(directory.iterdir()):
            require(path.name in expected, 'unexpected-staging-artifact-preserve-and-review')
            index = expected[path.name]
            regular(path)
            if committed and path.stat().st_nlink > 1:
                require(self.owns(plan, index), 'staging-ownership-changed-preserve-and-review')
            else:
                require(path.stat().st_nlink == 1, 'unexpected-staging-hardlink')
            path.unlink()
        sync_directory(directory)

    def rollback(self, plan):
        identifier = plan['fingerprint']
        self.transition(identifier, 'ROLLING_BACK')
        conflicts = []
        for index, op in reversed(list(enumerate(plan['eligible']))):
            target = self.base / op['path']
            if target.exists():
                if self.owns(plan, index):
                    target.unlink()
                    sync_directory(target.parent)
                    _checkpoint('after_rollback_remove', index)
                else:
                    conflicts.append(op['path'])
        if conflicts or self.canonical_snapshot() != plan['canonical']:
            self.transition(identifier, 'RECOVERY_REQUIRED')
            raise PopulationError('concurrent-edits-preserved-manual-review-required-before-recovery')
        errors, _ = kb.validate(self.base)
        require(not errors, 'rollback-validation-failed-manual-review-required')
        self.clear_stage(plan)
        self.transition(identifier, 'ROLLED_BACK')
        return {'ok': True, 'state': 'ROLLED_BACK', 'fingerprint': identifier,
                'canonical_validation': {'ok': True, 'errors': []}}

    def apply(self, identifier, approve=None, dry_run=False):
        with self.coordinate():
            plan = self.load_plan(identifier)
            require(approve is None or approve == identifier, 'approval-fingerprint-mismatch')
            require(dry_run or approve == identifier, 'exact-plan-approval-required-use-approve-fingerprint')
            self.no_pending()
            previous = self.journal(identifier)
            if previous and previous['state'] == 'COMMITTED':
                # Retry is a no-op, never a source re-extraction or a timestamp rewrite.
                self.check_installed(plan)
                if not dry_run:
                    self.clear_stage(plan, committed=True)
                errors, _ = kb.validate(self.base)
                require(not errors, 'committed-dataset-no-longer-valid-review-required')
                return {'ok': True, 'state': 'COMMITTED', 'already_applied': True,
                        'fingerprint': identifier, 'writes': 0}
            validation = self.preflight_apply(plan)
            if dry_run:
                return {'ok': True, 'dry_run': True, 'fingerprint': identifier,
                        'operations': plan['eligible'], 'validation': validation}
            directory = self.transaction_path(identifier)
            if not directory.exists():
                directory.mkdir()
                sync_directory(directory.parent)
            staged = directory / 'staged'
            if not staged.exists():
                staged.mkdir()
                sync_directory(directory)
            self.clear_stage(plan)
            attempt = previous.get('attempt', 0) + 1 if previous else 1
            try:
                self.transition(identifier, 'STAGING', attempt=attempt)
                _checkpoint('after_journal')
                records = {r['id']: r for group in GROUPS for r in plan['records'][group]}
                for index, op in enumerate(plan['eligible']):
                    write_new(self.stage_path(identifier, index), encoded(records[op['id']]))
                    _checkpoint('after_stage', index)
                _checkpoint('after_staging')
                require(self.canonical_snapshot() == plan['canonical'], 'canonical-changed-before-install')
                require(self.observe(plan['sources']['exclusions'])[1] == plan['sources'],
                        'sources-changed-before-install')
                self.transition(identifier, 'INSTALLING')
                for index, op in enumerate(plan['eligible']):
                    self.safe_tree()
                    staged_file = self.stage_path(identifier, index)
                    require(sha(read_bytes(staged_file)) == op['hash'], 'staged-record-changed')
                    os.link(staged_file, self.base / op['path'], follow_symlinks=False)
                    sync_directory((self.base / op['path']).parent)
                    _checkpoint('after_install', index)
                    self.transition(identifier, 'INSTALLING', installed=index + 1)
                _checkpoint('before_commit')
                self.check_installed(plan, require_owned=True)
                require(self.canonical_snapshot(op['path'] for op in plan['eligible']) == plan['canonical'],
                        'concurrent-canonical-edit-before-commit')
                errors, warnings = kb.validate(self.base)
                require(not errors, 'installed-dataset-validation-failed')
                require(self.observe(plan['sources']['exclusions'])[1] == plan['sources'],
                        'source-changed-before-commit')
                self.transition(identifier, 'COMMITTED', installed=len(plan['eligible']))
                _checkpoint('after_commit')
                self.clear_stage(plan, committed=True)
                return {'ok': True, 'state': 'COMMITTED', 'fingerprint': identifier,
                        'writes': len(plan['eligible']),
                        'canonical_validation': {'ok': True, 'errors': errors, 'warnings': warnings},
                        'meaning': 'Records stored; no semantic confirmation or human review implied.'}
            except Exception as error:
                current = self.journal(identifier)
                if current and current['state'] == 'COMMITTED':
                    raise PopulationError('committed-cleanup-pending-retry-apply-or-recover') from None
                self.rollback(plan)
                detail = (str(error) if isinstance(error, PopulationError) else
                          'io-error-check-permissions-or-hardlink-support' if isinstance(error, OSError)
                          else 'retry-same-plan-if-still-fresh')
                raise PopulationError('application-failed-rolled-back:' + detail) from None

    def status(self, identifier=None):
        with self.coordinate():
            if identifier:
                self.load_plan(identifier)
            journals = self.all_transactions()
            pending = [j['plan'] for j in journals if j['state'] not in TERMINAL]
            if identifier:
                journals = [j for j in journals if j['plan'] == identifier]
            prepared = []
            if self.plans.exists():
                for path in sorted(self.plans.iterdir()):
                    require(re.fullmatch('[a-f0-9]{64}\\.json', path.name), 'unexpected-plan-object')
                    self.load_plan('sha256:' + path.stem)
                    prepared.append('sha256:' + path.stem)
            return {'ok': True, 'transactions': journals,
                    'recovery_required': bool(pending), 'pending_plans': pending,
                    'prepared': prepared}

    def recover(self, identifier):
        with self.coordinate():
            plan = self.load_plan(identifier)
            journal = self.journal(identifier)
            require(journal is not None, 'no-transaction-to-recover')
            if journal['state'] == 'ORPHANED' and any(
                    (self.base / op['path']).exists() for op in plan['eligible']):
                self.transition(identifier, 'RECOVERY_REQUIRED')
                raise PopulationError('missing-journal-with-existing-targets-preserve-and-review')
            if journal['state'] == 'COMMITTED':
                self.check_installed(plan)
                self.clear_stage(plan, committed=True)
                errors, _ = kb.validate(self.base)
                require(not errors, 'committed-dataset-no-longer-valid-review-required')
                return {'ok': True, 'state': 'COMMITTED', 'fingerprint': identifier, 'writes': 0}
            if journal['state'] == 'ROLLED_BACK':
                return {'ok': True, 'state': 'ROLLED_BACK', 'fingerprint': identifier, 'writes': 0}
            return self.rollback(plan)


@contextmanager
def normal_operation(root):
    """Hold the existing coordinator throughout a CLI read; never create state."""
    state = Path(root) / '.ai/state/population'
    if state.exists() or state.is_symlink():
        store = PopulationStore(root)
        with store.coordinate():
            store.no_pending()
            yield
    else:
        yield


def guard_normal_operation(root):
    """Diagnostic gate for callers that do not need a scoped reader lock."""
    with normal_operation(root):
        pass
