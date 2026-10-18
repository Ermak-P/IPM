from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb
from population_normalize import load_canonical
from population_transaction import (PopulationError, PopulationStore, encoded, seal,
                                    sha, write_new, guard_normal_operation, normal_operation)

CLI = Path(__file__).resolve().parents[1] / 'kb.py'


class Interrupted(BaseException):
    pass


class PopulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertEqual(kb.init(self.root / '.ai'), [])
        self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net10.0'
                   '</TargetFramework></PropertyGroup></Project>')
        self.write('host.txt', 'unchanged host bytes\r\n')
        self.store = PopulationStore(self.root)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
        return path

    def canonical(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for folder in ['knowledge', 'evidence', 'sources', 'schema']
                for p in (self.root / '.ai' / folder).rglob('*') if p.is_file()}

    def host(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()
                and p.relative_to(self.root).parts[0] != '.ai'}

    def prepare(self):
        return self.store.prepare()['plan']

    def apply(self, plan):
        return self.store.apply(plan['fingerprint'], plan['fingerprint'])

    def saved_mutation(self, plan, edit):
        changed = deepcopy(plan)
        edit(changed)
        changed = seal(changed)
        write_new(self.store.plan_path(changed['fingerprint']), encoded(changed))
        return changed

    def interrupt(self, plan, phase, index=None):
        def checkpoint(name, current=None):
            if name == phase and (index is None or current == index):
                raise Interrupted()
        with patch('population_transaction._checkpoint', side_effect=checkpoint):
            with self.assertRaises(Interrupted):
                self.apply(plan)

    def test_prepare_is_immutable_and_has_no_canonical_or_host_mutation(self):
        canonical, host = self.canonical(), self.host()
        plan = self.prepare()
        self.assertEqual(canonical, self.canonical())
        self.assertEqual(host, self.host())
        self.assertTrue(plan['applicable'])
        self.assertFalse(plan['blocked'])
        self.assertEqual(self.store.load_plan(plan['fingerprint']), plan)
        self.assertTrue(plan['sources']['files'])
        self.assertTrue(plan['canonical']['fingerprint'])
        self.assertTrue(all(op['action'] == 'add' and op['requires'] for op in plan['eligible']))
        self.assertTrue(all(op['hash'] for op in plan['eligible']))
        with self.assertRaises(FileExistsError):
            write_new(self.store.plan_path(plan['fingerprint']), b'overwrite')
        self.assertEqual(self.store.load_plan(plan['fingerprint']), plan)

    def test_exact_plan_approval_success_and_preserved_payload(self):
        plan = self.prepare()
        result = self.apply(plan)
        self.assertEqual(result['state'], 'COMMITTED')
        self.assertEqual(result['writes'], len(plan['eligible']))
        self.assertFalse(kb.validate(self.root / '.ai')[0])
        records = {r['id']: r for group in plan['records'].values() for r in group}
        for op in plan['eligible']:
            self.assertEqual(kb.read_json(self.root / '.ai' / op['path']), records[op['id']])
        self.assertFalse(self.store.status()['recovery_required'])

    def test_missing_and_wrong_approval_rejected(self):
        plan = self.prepare()
        before = self.canonical()
        with self.assertRaisesRegex(PopulationError, 'exact-plan-approval-required'):
            self.store.apply(plan['fingerprint'])
        with self.assertRaisesRegex(PopulationError, 'approval-fingerprint-mismatch'):
            self.store.apply(plan['fingerprint'], 'sha256:' + '0' * 64)
        self.assertEqual(before, self.canonical())
        self.assertIsNone(self.store.journal(plan['fingerprint']))

    def test_dry_run_validates_complete_dataset_without_transaction(self):
        plan = self.prepare()
        before = self.canonical()
        result = self.store.apply(plan['fingerprint'], dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertTrue(result['validation']['ok'])
        self.assertEqual(before, self.canonical())
        self.assertIsNone(self.store.journal(plan['fingerprint']))

    def test_altered_saved_plan_cannot_reuse_approval(self):
        plan = self.prepare()
        before = self.canonical()
        path = self.store.plan_path(plan['fingerprint'])
        changed = deepcopy(plan)
        changed['records']['claims'][0]['statement'] = 'tampered'
        path.write_bytes(encoded(changed))
        with self.assertRaisesRegex(PopulationError, 'fingerprint-mismatch'):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_new_plan_never_inherits_old_approval(self):
        one, two = self.prepare(), self.prepare()
        self.assertNotEqual(one['fingerprint'], two['fingerprint'])
        with self.assertRaisesRegex(PopulationError, 'approval-fingerprint-mismatch'):
            self.store.apply(two['fingerprint'], one['fingerprint'])

    def test_fingerprint_deterministic_for_exact_payload(self):
        plan = self.prepare()
        self.assertEqual(seal(plan), plan)
        self.assertEqual(seal(dict(reversed(list(plan.items())))), plan)

    def test_stale_source_formatting_edit_and_removed_source(self):
        plan = self.prepare()
        before = self.canonical()
        source = self.root / 'App.csproj'
        source.write_text('<Project>\n</Project>', encoding='utf-8')
        with self.assertRaisesRegex(PopulationError, 'stale-source-inputs'):
            self.apply(plan)
        source.unlink()
        with self.assertRaises(PopulationError):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_empty_solution_bytes_are_fingerprinted_even_without_membership(self):
        source = self.write('Empty.sln', 'Microsoft Visual Studio Solution File, Format Version 12.00\n')
        plan = self.prepare()
        source.write_text(source.read_text() + '# formatting change\n', encoding='utf-8')
        with self.assertRaisesRegex(PopulationError, 'stale-source-inputs'):
            self.apply(plan)

    def test_stale_canonical_bytes_even_formatting_are_rejected(self):
        plan = self.prepare()
        self.write('.ai/knowledge/decisions/human.md', 'Human note.')
        before = self.canonical()
        with self.assertRaisesRegex(PopulationError, 'stale-canonical'):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_conflicting_existing_id_is_not_replaced(self):
        initial = self.prepare()
        claim, evidence = initial['records']['claims'][0], initial['records']['evidence'][0]
        claim.update(status='CONFIRMED', last_verified='2000-01-01')
        claim['provenance'] = {'actor': 'human', 'method': 'manual inspection'}
        self.write('.ai/knowledge/claims/human.json', json.dumps(claim))
        self.write('.ai/evidence/human.json', json.dumps(evidence))
        before = self.canonical()
        plan = self.prepare()
        self.assertFalse(plan['applicable'])
        with self.assertRaisesRegex(PopulationError, 'blocked-plan'):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_destination_occupied_by_another_record_is_blocked(self):
        first = self.prepare()
        op = first['eligible'][0]
        other = {'id': 'human.other', 'statement': 'Unrelated.', 'type': 'technical_fact',
                 'status': 'UNKNOWN', 'evidence': [], 'depends_on': [], 'conflicts_with': [],
                 'last_verified': None, 'provenance': {'actor': 'human', 'method': 'manual'}}
        self.write('.ai/' + op['path'], json.dumps(other))
        plan = self.prepare()
        self.assertIn('target-path-occupied', str(plan['blocked']))
        before = self.canonical()
        with self.assertRaises(PopulationError):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_unsupported_updates_deletions_and_status_promotion_rejected(self):
        plan = self.prepare()
        for action in ['update', 'delete', 'replace']:
            with self.subTest(action=action):
                changed = self.saved_mutation(plan, lambda p: p['eligible'][0].update(action=action))
                with self.assertRaises(PopulationError):
                    self.apply(changed)
        changed = self.saved_mutation(plan, lambda p: p['records']['claims'][0].update(
            status='CONFIRMED', last_verified='2000-01-01'))
        with self.assertRaisesRegex(PopulationError, 'lifecycle'):
            self.apply(changed)
        self.assertFalse(load_canonical(self.root / '.ai')['claims'])

    def test_cannot_approve_cherry_picked_claim_without_evidence(self):
        plan = self.prepare()
        changed = self.saved_mutation(plan, lambda p: p.update(
            eligible=[op for op in p['eligible'] if op['record_type'] == 'claims']))
        before = self.canonical()
        with self.assertRaisesRegex(PopulationError, 'fresh-normalization'):
            self.apply(changed)
        self.assertEqual(before, self.canonical())

    def test_related_claims_and_evidence_all_applied_with_no_dangling_references(self):
        plan = self.prepare()
        self.apply(plan)
        records = load_canonical(self.root / '.ai')
        ids = {r['id'] for values in records.values() for r in values}
        for op in plan['eligible']:
            self.assertTrue(set(op['requires']).issubset(ids))
        self.assertEqual(len(records['claims']), len(records['evidence']))
        self.assertFalse(kb.validate(self.root / '.ai')[0])

    def test_dangling_and_malformed_records_rejected_before_mutation(self):
        plan = self.prepare()
        for edit in [lambda p: p['records']['claims'][0].update(evidence=['missing.evidence']),
                     lambda p: p['records']['evidence'][0].update(captured_at='bad-date'),
                     lambda p: p['records']['claims'][0].pop('statement')]:
            with self.subTest(edit=edit):
                changed = self.saved_mutation(plan, edit)
                before = self.canonical()
                with self.assertRaises(PopulationError):
                    self.apply(changed)
                self.assertEqual(before, self.canonical())

    def test_existing_human_knowledge_and_observation_timestamps_untouched(self):
        claim = {'id': 'human.rule', 'statement': 'Human-approved rule.', 'type': 'business_rule',
                 'status': 'CONFIRMED', 'evidence': ['human.evidence'], 'depends_on': [],
                 'conflicts_with': [], 'last_verified': '2000-01-01',
                 'provenance': {'actor': 'human', 'method': 'approval'}}
        evidence = {'id': 'human.evidence', 'type': 'direct-authoritative', 'status': 'active',
                    'source': 'requirements://approval', 'description': 'Approved synthetic rule.',
                    'location': 'rule 1', 'substantiates': ['human.rule'],
                    'captured_at': '2000-01-01T00:00:00Z',
                    'provenance': {'actor': 'human', 'method': 'approval'}}
        self.write('.ai/knowledge/claims/human.json', json.dumps(claim, indent=3))
        self.write('.ai/evidence/human.json', json.dumps(evidence, indent=3))
        before = self.canonical()
        plan = self.prepare()
        self.apply(plan)
        after = self.canonical()
        self.assertTrue(all(after[path] == value for path, value in before.items()))
        for new in plan['records']['claims']:
            self.assertEqual(new['status'], 'NEEDS_HUMAN_CONFIRMATION')
            self.assertIsNone(new['last_verified'])
        for op in plan['eligible']:
            actual = kb.read_json(self.root / '.ai' / op['path'])
            if op['record_type'] == 'evidence':
                self.assertEqual(actual['captured_at'], plan['observation']['captured_at'])

    def test_blocked_unresolved_plan_cannot_apply_other_eligible_operations(self):
        self.write('App.csproj', '<Project><ItemGroup><ProjectReference Include="$(Root)/Missing.csproj"/>'
                   '</ItemGroup></Project>')
        plan = self.prepare()
        self.assertTrue(plan['eligible'])
        self.assertTrue(plan['blocked'])
        before = self.canonical()
        with self.assertRaisesRegex(PopulationError, 'blocked-plan'):
            self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_normal_exception_during_staging_rolls_back_automatically(self):
        plan = self.prepare()
        before = self.canonical()
        def fail(phase, index=None):
            if phase == 'after_stage' and index == 0:
                raise OSError('simulated disk error')
        with patch('population_transaction._checkpoint', side_effect=fail):
            with self.assertRaisesRegex(PopulationError, 'failed-rolled-back'):
                self.apply(plan)
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'ROLLED_BACK')
        self.assertEqual(self.apply(plan)['state'], 'COMMITTED')

    def test_interruption_during_staging_recovery_and_retry(self):
        plan = self.prepare()
        before = self.canonical()
        self.interrupt(plan, 'after_stage', 0)
        self.assertTrue(self.store.status()['recovery_required'])
        self.assertEqual(self.store.recover(plan['fingerprint'])['state'], 'ROLLED_BACK')
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.apply(plan)['state'], 'COMMITTED')

    def test_recovery_after_partial_install_before_progress_journal(self):
        plan = self.prepare()
        before = self.canonical()
        self.interrupt(plan, 'after_install', 0)
        self.assertTrue(self.store.status()['recovery_required'])
        self.assertNotEqual(before, self.canonical())
        with self.assertRaisesRegex(PopulationError, 'recovery-required'):
            self.store.prepare()
        with self.assertRaisesRegex(PopulationError, 'recovery-required'):
            self.apply(plan)
        with self.assertRaises(PopulationError):
            guard_normal_operation(self.root)
        self.assertEqual(self.store.recover(plan['fingerprint'])['state'], 'ROLLED_BACK')
        self.assertEqual(before, self.canonical())
        self.assertFalse(kb.validate(self.root / '.ai')[0])
        self.assertEqual(self.apply(plan)['state'], 'COMMITTED')

    def test_interruption_before_final_commit_rolls_back_entire_batch(self):
        plan = self.prepare()
        before = self.canonical()
        self.interrupt(plan, 'before_commit')
        self.assertFalse(kb.validate(self.root / '.ai')[0])  # Complete but uncommitted.
        self.assertTrue(self.store.status()['recovery_required'])
        self.store.recover(plan['fingerprint'])
        self.assertEqual(before, self.canonical())

    def test_interrupted_commit_journal_replace_is_recovered_as_uncommitted(self):
        plan = self.prepare()
        before = self.canonical()
        self.interrupt(plan, 'before_journal_replace', 'COMMITTED')
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'INSTALLING')
        self.store.recover(plan['fingerprint'])
        self.assertEqual(before, self.canonical())

    def test_interruption_after_commit_cleanup_is_idempotent(self):
        plan = self.prepare()
        self.interrupt(plan, 'after_commit')
        before = self.canonical()
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'COMMITTED')
        result = self.apply(plan)
        self.assertTrue(result['already_applied'])
        self.assertEqual(result['writes'], 0)
        self.assertEqual(before, self.canonical())
        for op in plan['eligible']:
            self.assertEqual((self.root / '.ai' / op['path']).stat().st_nlink, 1)

    def test_idempotent_retry_never_rewrites_evidence_timestamps(self):
        plan = self.prepare()
        self.apply(plan)
        before = self.canonical()
        self.assertTrue(self.apply(plan)['already_applied'])
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.store.recover(plan['fingerprint'])['state'], 'COMMITTED')
        self.assertEqual(before, self.canonical())

    def test_exclusive_lock_prevents_concurrent_apply_in_another_process(self):
        plan = self.prepare()
        before = self.canonical()
        with self.store.coordinate():
            run = subprocess.run([sys.executable, '-B', str(CLI), 'populate', 'apply',
                                  '--root', str(self.root), '--plan', plan['fingerprint'],
                                  '--approve', plan['fingerprint'], '--json'],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            self.assertIn('population-busy', run.stdout)
        self.assertEqual(before, self.canonical())
        self.apply(plan)

    def test_concurrent_canonical_edit_is_preserved_and_own_writes_rolled_back(self):
        plan = self.prepare()
        note = self.write('.ai/knowledge/decisions/note.md', 'original')
        plan = self.prepare()  # Fingerprint includes the original human note.
        def edit(phase, index=None):
            if phase == 'before_commit':
                note.write_text('concurrent human edit', encoding='utf-8')
        with patch('population_transaction._checkpoint', side_effect=edit):
            with self.assertRaises(PopulationError):
                self.apply(plan)
        self.assertEqual(note.read_text(), 'concurrent human edit')
        self.assertFalse(load_canonical(self.root / '.ai')['claims'])
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'RECOVERY_REQUIRED')
        note.write_text('original', encoding='utf-8')  # Explicit synthetic manual reconciliation.
        self.store.recover(plan['fingerprint'])

    def test_concurrent_destination_creation_is_never_overwritten_or_deleted(self):
        plan = self.prepare()
        target = self.root / '.ai' / plan['eligible'][0]['path']
        def create(phase, index=None):
            if phase == 'before_journal_replace' and index == 'INSTALLING' and not target.exists():
                target.write_text('concurrent bytes', encoding='utf-8')
        with patch('population_transaction._checkpoint', side_effect=create):
            with self.assertRaises(PopulationError):
                self.apply(plan)
        self.assertEqual(target.read_text(), 'concurrent bytes')
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'RECOVERY_REQUIRED')

    def test_edited_transaction_owned_record_is_not_deleted_by_recovery(self):
        plan = self.prepare()
        self.interrupt(plan, 'after_install', 0)
        target = self.root / '.ai' / plan['eligible'][0]['path']
        target.write_text('human edited transaction file', encoding='utf-8')
        with self.assertRaisesRegex(PopulationError, 'manual-review'):
            self.store.recover(plan['fingerprint'])
        self.assertEqual(target.read_text(), 'human edited transaction file')

    def test_committed_missing_target_does_not_destroy_last_staged_copy(self):
        plan = self.prepare()
        self.interrupt(plan, 'after_commit')
        target = self.root / '.ai' / plan['eligible'][0]['path']
        target.unlink()  # Simulated external deletion, not a tool operation.
        staged = self.store.stage_path(plan['fingerprint'], 0)
        before = staged.read_bytes()
        with self.assertRaises(PopulationError):
            self.store.recover(plan['fingerprint'])
        self.assertEqual(staged.read_bytes(), before)

    def test_interrupted_rollback_is_itself_recoverable(self):
        plan = self.prepare()
        before = self.canonical()
        self.interrupt(plan, 'before_commit')
        def stop(phase, index=None):
            if phase == 'after_rollback_remove':
                raise Interrupted()
        with patch('population_transaction._checkpoint', side_effect=stop):
            with self.assertRaises(Interrupted):
                self.store.recover(plan['fingerprint'])
        self.assertEqual(self.store.recover(plan['fingerprint'])['state'], 'ROLLED_BACK')
        self.assertEqual(before, self.canonical())

    def test_orphaned_transaction_before_initial_journal_is_recoverable(self):
        plan = self.prepare()
        self.interrupt(plan, 'before_journal_replace', 'STAGING')
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'ORPHANED')
        self.assertEqual(self.store.recover(plan['fingerprint'])['state'], 'ROLLED_BACK')

    def test_no_network_llm_restore_project_execution_or_host_writes(self):
        self.write('App.csproj', '<Project><Target Name="Build"><Exec Command="DO_NOT_RUN"/>'
                   '</Target><PropertyGroup><Password>SECRET_CONTENT</Password></PropertyGroup></Project>')
        host = self.host()
        def denied(*args, **kwargs):
            raise AssertionError('network or execution attempted')
        with patch.object(socket, 'socket', denied), patch.object(socket, 'getaddrinfo', denied), \
                patch.object(subprocess, 'Popen', denied), patch.object(os, 'system', denied):
            plan = self.prepare()
            self.apply(plan)
            self.store.status()
        self.assertEqual(host, self.host())
        records = load_canonical(self.root / '.ai')
        self.assertNotIn('SECRET_CONTENT', json.dumps(records))
        self.assertNotIn('DO_NOT_RUN', json.dumps(records))

    def test_unsafe_plan_fingerprints_and_destination_paths_rejected(self):
        plan = self.prepare()
        for value in ['../outside', '/tmp/plan.json', 'sha256:wrong']:
            with self.subTest(value=value):
                with self.assertRaises(PopulationError):
                    self.store.apply(value, value)
        changed = self.saved_mutation(plan, lambda p: p['eligible'][0].update(path='../host.txt'))
        before = self.host()
        with self.assertRaises(PopulationError):
            self.apply(changed)
        self.assertEqual(before, self.host())

    def test_links_and_unexpected_objects_rejected(self):
        plan = self.prepare()
        target = self.root / '.ai' / plan['eligible'][0]['path']
        try:
            target.symlink_to(self.root / 'host.txt')
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation not permitted')
        with self.assertRaisesRegex(PopulationError, 'links'):
            PopulationStore(self.root)
        self.assertEqual((self.root / 'host.txt').read_bytes(), b'unchanged host bytes\r\n')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO is Unix-only')
    def test_fifo_rejected_without_opening(self):
        os.mkfifo(self.root / '.ai/evidence/pipe.json')
        with self.assertRaisesRegex(PopulationError, 'filesystem-object'):
            PopulationStore(self.root)

    def test_hardlinked_existing_canonical_file_rejected(self):
        target = self.root / '.ai/knowledge/decisions/link.md'
        try:
            os.link(self.root / 'host.txt', target)
        except OSError:
            self.skipTest('filesystem lacks hardlink support')
        with self.assertRaisesRegex(PopulationError, 'hardlink'):
            self.prepare()

    def test_duplicate_json_plan_keys_rejected(self):
        plan = self.prepare()
        path = self.store.plan_path(plan['fingerprint'])
        path.write_text('{"fingerprint":"one","fingerprint":"two"}', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.apply(plan)

    def test_cli_default_prepare_and_exact_approval_and_guard(self):
        def cli(*args, expected=0):
            result = subprocess.run([sys.executable, '-B', str(CLI), *args,
                                     '--root', str(self.root), '--json'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            return json.loads(result.stdout)
        plan = cli('populate')['plan']
        fp = plan['fingerprint']
        cli('populate', 'apply', '--plan', fp, expected=1)
        self.interrupt(plan, 'after_install', 0)
        self.assertFalse(cli('validate', expected=1)['ok'])
        self.assertTrue(cli('populate', 'status')['recovery_required'])
        cli('populate', 'recover', '--plan', fp)
        result = cli('populate', 'apply', '--plan', fp, '--approve', fp)
        self.assertEqual(result['state'], 'COMMITTED')
        self.assertTrue(cli('validate')['ok'])

    def test_cli_generic_yes_is_not_approval(self):
        plan = self.prepare()
        run = subprocess.run([sys.executable, '-B', str(CLI), 'populate', 'apply',
                              '--root', str(self.root), '--plan', plan['fingerprint'], '--yes'],
                             capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(load_canonical(self.root / '.ai')['claims'])

    def test_real_process_exit_releases_lock_and_leaves_recoverable_journal(self):
        plan = self.prepare()
        before = self.canonical()
        script = """
import os, sys
sys.path.insert(0, sys.argv[1])
import population_transaction as tx
def stop(phase, index=None):
    if phase == 'after_install' and index == 0:
        os._exit(71)
tx._checkpoint = stop
tx.PopulationStore(sys.argv[2]).apply(sys.argv[3], sys.argv[3])
"""
        run = subprocess.run([sys.executable, '-B', '-c', script, str(CLI.parent),
                              str(self.root), plan['fingerprint']], capture_output=True,
                             text=True, timeout=15)
        self.assertEqual(run.returncode, 71, run.stdout + run.stderr)
        self.assertTrue(self.store.status()['recovery_required'])
        self.store.recover(plan['fingerprint'])
        self.assertEqual(before, self.canonical())

    def test_normal_reader_holds_coordination_for_its_entire_scope(self):
        plan = self.prepare()
        with normal_operation(self.root):
            with self.assertRaisesRegex(PopulationError, 'population-busy'):
                self.apply(plan)
        self.assertEqual(self.apply(plan)['state'], 'COMMITTED')

    def test_normal_failure_after_partial_install_restores_full_baseline(self):
        plan = self.prepare()
        before = self.canonical()
        def fail(phase, index=None):
            if phase == 'after_install' and index == 0:
                raise OSError('disk error')
        with patch('population_transaction._checkpoint', side_effect=fail):
            with self.assertRaisesRegex(PopulationError, 'failed-rolled-back'):
                self.apply(plan)
        self.assertEqual(before, self.canonical())
        self.assertFalse(kb.validate(self.root / '.ai')[0])

    def test_partial_stage_file_write_is_cleaned_without_canonical_effect(self):
        plan = self.prepare()
        before = self.canonical()
        original = write_new
        def partial(path, data):
            if path.parent.name == 'staged':
                original(path, data[:10])
                raise OSError('disk full')
            return original(path, data)
        with patch('population_transaction.write_new', side_effect=partial):
            with self.assertRaisesRegex(PopulationError, 'failed-rolled-back'):
                self.apply(plan)
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'ROLLED_BACK')

    def test_unsupported_hardlinks_fail_without_partial_knowledge(self):
        plan = self.prepare()
        before = self.canonical()
        with patch('population_transaction.os.link', side_effect=OSError('unsupported')):
            with self.assertRaisesRegex(PopulationError, 'hardlink-support'):
                self.apply(plan)
        self.assertEqual(before, self.canonical())

    def test_source_change_during_install_rolls_back_and_requires_new_plan(self):
        plan = self.prepare()
        before = self.canonical()
        def change(phase, index=None):
            if phase == 'before_commit':
                (self.root / 'App.csproj').write_text('<Project/>', encoding='utf-8')
        with patch('population_transaction._checkpoint', side_effect=change):
            with self.assertRaisesRegex(PopulationError, 'failed-rolled-back'):
                self.apply(plan)
        self.assertEqual(before, self.canonical())
        with self.assertRaisesRegex(PopulationError, 'stale-source'):
            self.apply(plan)

    def test_plan_bound_to_repository_root_not_only_identical_record_contents(self):
        plan = self.prepare()
        with tempfile.TemporaryDirectory() as other:
            root = Path(other)
            self.assertEqual(kb.init(root / '.ai'), [])
            (root / 'App.csproj').write_bytes((self.root / 'App.csproj').read_bytes())
            (root / 'host.txt').write_bytes((self.root / 'host.txt').read_bytes())
            store = PopulationStore(root)
            with store.coordinate(create=True):
                write_new(store.plan_path(plan['fingerprint']), encoded(plan))
            with self.assertRaisesRegex(PopulationError, 'fresh-normalization'):
                store.apply(plan['fingerprint'], plan['fingerprint'])
            self.assertFalse(load_canonical(root / '.ai')['claims'])

    def test_committed_dry_run_does_not_clean_internal_staging(self):
        plan = self.prepare()
        self.interrupt(plan, 'after_commit')
        staged = self.store.stage_path(plan['fingerprint'], 0)
        before = staged.read_bytes()
        self.store.apply(plan['fingerprint'], dry_run=True)
        self.assertEqual(staged.read_bytes(), before)

    def test_missing_committed_journal_cannot_authorize_record_deletion(self):
        plan = self.prepare()
        self.interrupt(plan, 'after_commit')
        before = self.canonical()
        (self.store.transaction_path(plan['fingerprint']) / 'journal.json').unlink()
        with self.assertRaisesRegex(PopulationError, 'missing-journal'):
            self.store.recover(plan['fingerprint'])
        self.assertEqual(before, self.canonical())

    def test_one_failed_progress_journal_write_is_safely_rolled_back(self):
        plan = self.prepare()
        before = self.canonical()
        original = write_new
        failed = False
        def fail_once(path, data):
            nonlocal failed
            if (path.name == 'journal.next' and not failed and
                    b'"state":"INSTALLING"' in data and b'"installed":1' in data):
                failed = True
                original(path, data[:20])
                raise OSError('journal write failure')
            return original(path, data)
        with patch('population_transaction.write_new', side_effect=fail_once):
            with self.assertRaisesRegex(PopulationError, 'failed-rolled-back'):
                self.apply(plan)
        self.assertTrue(failed)
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.store.journal(plan['fingerprint'])['state'], 'ROLLED_BACK')

    def test_apply_never_promotes_evidence_or_fabricates_new_observation(self):
        plan = self.prepare()
        def mutate(p):
            p['records']['evidence'][0]['captured_at'] = '2000-01-01T00:00:00Z'
            for op in p['eligible']:
                if op['id'] == p['records']['evidence'][0]['id']:
                    op['hash'] = sha(encoded(p['records']['evidence'][0]))
        changed = self.saved_mutation(plan, mutate)
        before = self.canonical()
        with self.assertRaisesRegex(PopulationError, 'fresh-normalization'):
            self.apply(changed)
        self.assertEqual(before, self.canonical())

    def test_no_state_created_by_read_only_status_or_ordinary_reader(self):
        before = self.canonical()
        self.assertFalse(self.store.state.exists())
        self.assertFalse(self.store.status()['recovery_required'])
        with normal_operation(self.root):
            self.assertFalse(kb.validate(self.root / '.ai')[0])
        self.assertFalse(self.store.state.exists())
        self.assertEqual(before, self.canonical())

    def test_installed_cli_population_is_portable(self):
        installed = self.root / '.ai/tools/kb.py'
        def cli(*args):
            run = subprocess.run([sys.executable, '-B', str(installed), 'populate', *args,
                                  '--root', str(self.root), '--json'],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            return json.loads(run.stdout)
        plan = cli('prepare')['plan']
        result = cli('apply', '--plan', plan['fingerprint'], '--approve', plan['fingerprint'])
        self.assertEqual(result['state'], 'COMMITTED')
        self.assertFalse(kb.validate(self.root / '.ai')[0])


if __name__ == '__main__':
    unittest.main()
