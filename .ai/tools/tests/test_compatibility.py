"""Foreign knowledge remains foreign: all tests operate in disposable roots."""
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
import compatibility_inspector as inspector
from compatibility_inspector import CompatibilityInspector, Inventory

CLI = Path(__file__).resolve().parents[1] / 'kb.py'
FIXTURE = CLI.parent / 'examples/existing-knowledge/fixture.json'


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = CompatibilityInspector()

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((json.dumps(value) if not isinstance(value, str) else value).encode())
        return target

    def harbor(self):
        for name, data in json.loads(FIXTURE.read_text())['files'].items():
            self.write(name, data)

    def inspect(self):
        return self.tool.inspect(self.root)

    def codes(self, report):
        return {d['code'] for d in report['diagnostics']}

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and not p.is_symlink()}

    def native(self):
        self.assertEqual(kb.init(self.root / '.ai'), [])

    def claim(self, identifier='claim.a'):
        return dict(id=identifier, statement='Private fixture prose never echoed.', type='technical_fact',
            status='NEEDS_HUMAN_CONFIRMATION', evidence=[], last_verified=None, depends_on=[], conflicts_with=[],
            provenance={'actor': 'fixture', 'method': 'synthetic'})

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(CLI), 'inspect-compatibility',
            '--root', str(self.root), *args], capture_output=True, text=True)

    def test_harbor_complete_foreign_blocked_ownership_and_graph(self):
        self.harbor(); before = self.snapshot(); result = self.inspect()
        self.assertTrue(result['ok'])
        self.assertTrue(result['complete'])
        self.assertFalse(result['integration_approved'])
        self.assertFalse(result['canonical_validation_performed'])
        self.assertEqual(result['manifest']['classification'], 'foreign-json-declaration')
        self.assertFalse(result['manifest']['accepted_as_contract'])
        self.assertEqual(result['suggested_integration_mode'], 'integration-blocked')
        self.assertEqual(len(result['graph_tools']), 1)
        graph = result['graph_tools'][0]
        self.assertEqual(graph['declared_inputs'], ['.ai/knowledge/claims', '.ai/knowledge/domains', '.ai/knowledge/relationships'])
        self.assertEqual(graph['declared_outputs'], ['.ai/generated/architecture.json'])
        self.assertEqual(graph['declared_owner'], 'harbor-architecture-team')
        self.assertEqual(graph['ownership'], 'unknown-provisional')
        self.assertFalse(graph['activated'])
        self.assertIn('graph-builder-ownership-selection-required', self.codes(result))
        self.assertEqual(before, self.snapshot())

    def test_manifest_exact_is_not_acceptance(self):
        self.write('.ai/manifest.yaml', kb.MANIFEST)
        result = self.inspect()
        self.assertEqual(result['manifest']['classification'], 'exact-v1-declaration')
        self.assertFalse(result['manifest']['accepted_as_contract'])
        self.assertFalse(result['integration_approved'])
        self.assertEqual(result['suggested_integration_mode'], 'read-only-source-analysis')

    def test_missing_ai_and_foreign_modes(self):
        self.assertEqual(self.inspect()['suggested_integration_mode'], 'read-only-source-analysis')
        self.write('.ai/manifest.yaml', {'format': 'foreign'})
        self.assertEqual(self.inspect()['suggested_integration_mode'], 'read-only-compatibility-inspection')

    def test_missing_manifest_complete_but_diagnostic(self):
        self.write('.ai/domain.md', 'Owner prose')
        result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertIn('missing-or-unsupported-manifest', self.codes(result))
        self.assertIn('unknown-content-not-interpreted', self.codes(result))

    def test_occupied_paths_do_not_imply_framework_ownership(self):
        self.write('.ai/tools/kb.py', 'raise AssertionError("NEVER RUN")')
        result = self.inspect()
        entry = next(e for e in result['inventory'] if e['path'] == '.ai/tools/kb.py')
        self.assertTrue(entry['occupied_framework_path'])
        self.assertEqual(entry['ownership'], 'unknown-provisional')
        self.assertFalse(result['provisional_ownership']['framework_ownership_inferred'])

    def test_builders_same_and_different_paths_no_import(self):
        for path in ['.ai/tools/knowledge_graph.py', '.ai/tools/other_build_graph.ps1']:
            self.write(path, 'raise RuntimeError("discovered scripts never execute")')
        result = self.inspect()
        self.assertEqual(len(result['graph_tools']), 2)
        self.assertTrue(all(t['ownership'] == 'unknown-provisional' for t in result['graph_tools']))

    def test_manifest_declared_unconventionally_named_builder(self):
        self.write('.ai/manifest.yaml', {'graph_builder': 'tools/custom.py'})
        self.write('.ai/tools/custom.py', 'raise AssertionError()')
        graph, = self.inspect()['graph_tools']
        self.assertEqual(graph['entrypoint'], '.ai/tools/custom.py')
        self.assertEqual(graph['discovery'], ['manifest-declaration'])

    def test_declared_missing_builder_and_unsafe_reference_not_followed(self):
        self.write('.ai/tools/graph-contract.json', {'entrypoint': 'tools/missing.py',
            'inputs': ['../outside'], 'output': 'https://private.invalid/a'})
        result = self.inspect()
        self.assertIn('unsafe-or-ambiguous-declared-path', self.codes(result))
        self.assertIn('declared-graph-tool-not-observed', self.codes(result))
        self.assertEqual(result['graph_tools'][0]['declared_inputs'], [])

    def test_harbor_invalid_ids_statuses_provenance_and_relationships(self):
        self.harbor(); codes = self.codes(self.inspect())
        for code in ['id-incompatible-with-v1', 'unrecognized-v1-lifecycle-status',
                     'missing-or-invalid-provenance', 'missing-v1-required-fields',
                     'unsupported-component-relationship-not-claim-dependency']:
            self.assertIn(code, codes)

    def test_unknown_foreign_record_not_guessed(self):
        self.write('.ai/knowledge/claims/item.json', {'id': 'mystery', 'meaning': 'private'})
        self.assertIn('unsupported-record-shape', self.codes(self.inspect()))

    def test_duplicate_ids_across_groups_and_ambiguous_refs(self):
        claim = self.claim(); claim['evidence'] = ['claim.a']
        self.write('.ai/knowledge/claims/a.json', claim)
        self.write('.ai/evidence/a.json', {'id': 'claim.a', 'type': 'supporting', 'substantiates': ['missing']})
        codes = self.codes(self.inspect())
        self.assertIn('duplicate-record-id', codes)
        self.assertIn('missing-ambiguous-or-wrong-kind-reference', codes)

    def test_dangling_harbor_references(self):
        self.harbor()
        (self.root / '.ai/evidence/source.json').unlink()
        result = self.inspect()
        self.assertIn('missing-ambiguous-or-wrong-kind-reference', self.codes(result))

    def test_provenance_and_verification_missing_not_fabricated(self):
        claim = self.claim(); claim['status'] = 'CONFIRMED'; claim['provenance'] = {}
        self.write('.ai/knowledge/claims/a.json', claim)
        before = self.snapshot(); result = self.inspect()
        self.assertIn('missing-genuine-verification-field', self.codes(result))
        self.assertIn('missing-or-invalid-provenance', self.codes(result))
        self.assertEqual(before, self.snapshot())

    def test_generated_and_state_always_protected_not_disposable(self):
        self.write('.ai/generated/only-copy.md', 'unique data')
        self.write('.ai/state/decision.md', 'durable')
        result = self.inspect()
        entries = [e for e in result['inventory'] if e['type'] == 'file']
        self.assertTrue(all(not e['disposable'] for e in entries))
        self.assertEqual(result['provisional_ownership']['disposable_paths'], [])
        self.assertIn('potentially-durable-content-preserve', self.codes(result))

    def test_foreign_recovery_state_inspectable_without_lock_or_protocol(self):
        self.write('.ai/state/population/coordination.lock', 'FOREIGN NOT A LOCK')
        self.write('.ai/state/population/journal.json', '{}')
        before = self.snapshot(); result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertEqual(result['suggested_integration_mode'], 'integration-blocked')
        self.assertIn('transaction-or-recovery-state-owner-review-required', self.codes(result))
        self.assertEqual(before, self.snapshot())
        command = self.cli('--json')
        self.assertEqual(command.returncode, 0)

    def test_formats_duplicate_json_keys_and_nonfinite_rejected_without_echo(self):
        for text in ['{oops secret}', '{"id":"x","id":"y"}', '{"score":NaN}', '{"score":1e9999}', '[]']:
            self.write('.ai/knowledge/claims/a.json', text)
            result = self.inspect()
            self.assertIn('invalid-or-over-limit-json', self.codes(result))
            self.assertNotIn('oops secret', json.dumps(result))
        self.write('.ai/knowledge/claims/a.yaml', '!!python/object/apply:os.system ["bad"]')
        self.assertIn('unsupported-format', self.codes(self.inspect()))

    def test_no_prose_source_script_or_arbitrary_field_copy(self):
        self.harbor()
        secrets = ['PRIVATE-PROSE-123', 'SOURCE-CODE-456', 'UNKNOWN-FIELD-789']
        self.write('.ai/knowledge/domains/private.md', secrets[0])
        self.write('.ai/tools/script.py', secrets[1])
        claim = self.claim(); claim[secrets[2]] = secrets[0]
        self.write('.ai/knowledge/claims/native.json', claim)
        report = json.dumps(self.inspect())
        for secret in secrets + ['Private fixture prose never echoed.']:
            self.assertNotIn(secret, report)

    def test_symlink_outside_skipped_no_target_read(self):
        outside = self.write('secret.txt', 'DO NOT READ')
        (self.root / '.ai').mkdir()
        try:
            (self.root / '.ai/link.json').symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable')
        result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertIn('unsafe-link', self.codes(result))
        self.assertNotIn('DO NOT READ', json.dumps(result))
        self.assertIsNone(next(e for e in result['inventory'] if e['path'].endswith('link.json'))['content_fingerprint'])

    def test_linked_ai_root_and_repository_root_rejected(self):
        external = self.root / 'external'; external.mkdir()
        link = self.root / '.ai'
        try:
            link.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        self.assertFalse(self.inspect()['complete'])
        link.unlink()
        (self.root / 'linked').symlink_to(external, target_is_directory=True)
        self.assertFalse(self.tool.inspect(self.root / 'linked')['complete'])

    def test_ai_file_and_nonexistent_root_rejected(self):
        self.write('.ai', 'not directory')
        self.assertFalse(self.inspect()['complete'])
        self.assertFalse(self.tool.inspect(self.root / 'absent')['complete'])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO requires Unix')
    def test_fifo_not_opened(self):
        (self.root / '.ai').mkdir(); os.mkfifo(self.root / '.ai/fifo')
        result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertIn('unsafe-object', self.codes(result))

    def test_hardlink_not_hashed(self):
        path = self.write('private.txt', 'private')
        (self.root / '.ai').mkdir()
        try:
            os.link(path, self.root / '.ai/hardlink')
        except OSError:
            self.skipTest('hardlinks unavailable')
        result = self.inspect()
        self.assertIn('unsafe-hardlink', self.codes(result))
        self.assertFalse(result['complete'])

    def test_sensitive_names_excluded_and_coverage_explicit(self):
        self.write('.ai/.env', 'PASSWORD=secret')
        self.write('.ai/secrets/hidden.json', 'secret')
        result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertNotIn('PASSWORD', json.dumps(result))
        self.assertFalse(any(e['path'].endswith('hidden.json') for e in result['inventory']))
        self.assertIn('excluded-sensitive-or-cache-content', self.codes(result))

    def test_file_total_entry_depth_and_json_limits(self):
        self.write('.ai/a.json', 'x' * 200)
        with patch.object(inspector, 'MAX_FILE_BYTES', 100):
            self.assertFalse(self.inspect()['complete'])
        with patch.object(inspector, 'MAX_TOTAL_BYTES', 100):
            self.assertFalse(self.inspect()['complete'])
        self.write('.ai/b.txt', 'b')
        with patch.object(inspector, 'MAX_ENTRIES', 2):
            result = self.inspect()
            self.assertFalse(result['complete'])
            self.assertLessEqual(len(result['inventory']), 2)
        self.write('.ai/deep/a/b.txt', 'b')
        with patch.object(inspector, 'MAX_DEPTH', 1):
            self.assertFalse(self.inspect()['complete'])
        self.write('.ai/schema/deep.json', '{"a":{"b":{}}}')
        with patch.object(inspector, 'MAX_JSON_DEPTH', 1):
            self.assertIn('invalid-or-over-limit-json', self.codes(self.inspect()))

    def test_observable_content_changes(self):
        path = self.write('.ai/README.md', 'before')
        with patch('compatibility_inspector._checkpoint', side_effect=lambda: path.write_text('after')):
            result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertNotEqual(result['repository_snapshot_fingerprint'], result['final_snapshot_fingerprint'])
        self.assertIn('inputs-changed-during-inspection', self.codes(result))

    def test_added_removed_and_metadata_only_changes(self):
        path = self.write('.ai/a.md', 'same')
        for mutation in [lambda: self.write('.ai/b.md', 'new'), lambda: path.unlink(),
                         lambda: os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1000000))]:
            if not path.exists(): self.write('.ai/a.md', 'same')
            with patch('compatibility_inspector._checkpoint', side_effect=mutation):
                self.assertFalse(self.inspect()['complete'])

    def test_replacement_during_open_rejected(self):
        self.write('.ai/file.md', 'initial')
        real_open = os.open
        def replace(path, flags, *args, **kwargs):
            if Path(path).name == 'file.md':
                Path(path).unlink(); Path(path).write_text('replacement')
            return real_open(path, flags, *args, **kwargs)
        with patch('compatibility_inspector.os.open', side_effect=replace):
            result = self.inspect()
        self.assertFalse(result['complete'])

    def test_unreadable_input_is_incomplete(self):
        self.write('.ai/file.md', 'data')
        with patch.object(Inventory, 'read', side_effect=PermissionError('secret absolute path')):
            result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertNotIn('secret absolute path', json.dumps(result))

    def test_deterministic_reports_and_ordering(self):
        self.harbor()
        first = self.inspect(); second = self.inspect()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual([e['path'] for e in first['inventory']], sorted(e['path'] for e in first['inventory']))
        self.assertNotIn('captured_at', first)  # no current clock envelope

    def test_content_snapshot_changes_without_canonical_rewrite(self):
        path = self.write('.ai/knowledge/claims/a.json', self.claim())
        first = self.inspect(); before = path.read_bytes()
        self.write('.ai/domain.md', 'new owner doc')
        second = self.inspect()
        self.assertNotEqual(first['repository_snapshot_fingerprint'], second['repository_snapshot_fingerprint'])
        self.assertEqual(before, path.read_bytes())

    def test_no_network_subprocess_import_or_filesystem_writes(self):
        self.harbor(); before = self.snapshot()
        existing_graph_module = sys.modules.get('knowledge_graph')
        real_open = os.open
        def read_only(path, flags, *args, **kwargs):
            self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            return real_open(path, flags, *args, **kwargs)
        with patch.object(socket, 'socket', side_effect=AssertionError('network')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('execution')), \
             patch.object(os, 'system', side_effect=AssertionError('execution')), \
             patch.object(os, 'open', side_effect=read_only), \
             patch.object(Path, 'write_text', side_effect=AssertionError('write')), \
             patch.object(Path, 'write_bytes', side_effect=AssertionError('write')):
            self.assertTrue(self.inspect()['complete'])
        self.assertEqual(before, self.snapshot())
        self.assertIs(sys.modules.get('knowledge_graph'), existing_graph_module)

    def test_pinned_schema_declarations_not_remote_schemas(self):
        self.write('.ai/schema/claim.schema.json', kb.read_json(kb.SOURCE / 'schema/claim.schema.json'))
        self.write('.ai/schema/other.json', {'$schema': 'https://forbidden.invalid/SCHEMA_PRIVATE'})
        result = self.inspect()
        known = next(d for d in result['schema_declarations'] if d['path'].endswith('claim.schema.json'))
        self.assertEqual(known['matches_pinned_v1'], ['claims'])
        self.assertNotIn('SCHEMA_PRIVATE', json.dumps(result))
        self.assertIn('schema-incompatible-or-unsupported', self.codes(result))

    def test_path_aliases_on_case_sensitive_host(self):
        self.write('.ai/Case.md', 'one'); self.write('.ai/case.md', 'two')
        if len(list((self.root / '.ai').glob('*'))) < 2:
            self.skipTest('case-insensitive filesystem')
        self.assertIn('case-or-unicode-path-alias', self.codes(self.inspect()))

    def test_cli_json_summary_exit_semantics_and_no_install(self):
        self.harbor(); before = self.snapshot()
        command = self.cli('--json')
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout), self.inspect())
        self.assertEqual(self.snapshot(), before)
        summary = self.cli()
        self.assertEqual(summary.returncode, 0)
        self.assertIn('integration approved=False', summary.stdout)
        for options in [('--write-generated',), ('--exclude', 'x'), ('--view', 'canonical'),
                        ('--approve', 'hash'), ('--plan', 'hash'), ('--dry-run',)]:
            self.assertEqual(self.cli(*options).returncode, 2)

    def test_conflicting_graph_owner_declarations_not_selected(self):
        self.write('.ai/manifest.yaml', {'graph_builder': 'tools/g.py', 'knowledge_owner': 'owner-a'})
        self.write('.ai/tools/graph-contract.json', {'entrypoint': 'tools/g.py', 'owner': 'owner-b'})
        result = self.inspect()
        tool, = result['graph_tools']
        self.assertIsNone(tool['declared_owner'])
        self.assertEqual(tool['declared_owners'], ['owner-a', 'owner-b'])
        self.assertIn('conflicting-graph-owner-declarations', self.codes(result))
        self.assertFalse(result['integration_approved'])

    def test_native_confirmed_insufficient_support_not_treated_valid(self):
        claim = self.claim(); claim.update(status='CONFIRMED', last_verified='2026-01-01')
        self.write('.ai/knowledge/claims/a.json', claim)
        self.assertIn('confirmed-support-not-structurally-sufficient', self.codes(self.inspect()))
        claim['evidence'] = ['evidence.a']
        self.write('.ai/knowledge/claims/a.json', claim)
        self.write('.ai/evidence/a.json', dict(id='evidence.a', type='direct-technical', status='retracted',
            source='source.csproj', provenance={'actor':'fixture', 'method':'capture'},
            captured_at='2026-01-01T00:00:00Z', description='private', location='line 1', substantiates=['claim.a']))
        self.assertIn('confirmed-support-not-structurally-sufficient', self.codes(self.inspect()))

    def test_native_claim_reference_invariants(self):
        a, b = self.claim(), self.claim('claim.b')
        a['depends_on'] = ['claim.b']; b['depends_on'] = ['claim.a']
        a['conflicts_with'] = ['claim.b']
        self.write('.ai/knowledge/claims/a.json', a); self.write('.ai/knowledge/claims/b.json', b)
        for name in ['r1', 'r2']:
            self.write('.ai/knowledge/relationships/' + name + '.json', dict(id=name, type='conflicts_with',
                **{'from': 'claim.b', 'to': 'claim.a'}, provenance={'actor':'fixture','method':'declared'}))
        codes = self.codes(self.inspect())
        self.assertIn('asymmetric-claim-conflict', codes)
        self.assertIn('claim-dependency-cycle', codes)
        self.assertIn('relationship-not-matching-claim-arrays', codes)
        self.assertIn('duplicate-explicit-relationship', codes)

    def test_long_declared_metadata_is_not_echoed(self):
        private = 'a' * 10000
        self.write('.ai/manifest.yaml', {'graph_builder': private})
        report = json.dumps(self.inspect())
        self.assertNotIn(private, report)
        self.assertIn('unsafe-or-ambiguous-declared-path', report)

    def test_junction_detection_branch_without_traversal(self):
        self.write('.ai/junction/private.json', '{"private":"not read"}')
        original = Path.is_junction
        with patch.object(Path, 'is_junction', lambda path: path.name == 'junction' or original(path)):
            result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertIn('unsafe-link', self.codes(result))
        self.assertFalse(any(e['path'].endswith('private.json') for e in result['inventory']))

    def test_same_content_in_different_roots_same_report(self):
        import shutil
        self.harbor(); first = self.inspect()
        with tempfile.TemporaryDirectory() as other:
            shutil.copytree(self.root / '.ai', Path(other) / '.ai')
            second = self.tool.inspect(Path(other))
        self.assertEqual(first, second)

    def test_directory_enumeration_order_does_not_change_report(self):
        self.harbor(); first = self.inspect(); original = os.scandir
        class ReversedEntries:
            def __init__(self, path):
                self.directory = original(path)
            def __enter__(self):
                return iter(reversed(list(self.directory)))
            def __exit__(self, *args):
                self.directory.close()
        with patch('compatibility_inspector.os.scandir', ReversedEntries):
            second = self.inspect()
        self.assertEqual(first, second)

    def test_cli_incomplete_exit_one(self):
        self.write('.ai/.env', 'secret')
        command = self.cli('--json')
        self.assertEqual(command.returncode, 1)
        self.assertFalse(json.loads(command.stdout)['complete'])

    def test_installed_cli_remains_available(self):
        self.native()
        installed = self.root / '.ai/tools/kb.py'
        run = subprocess.run([sys.executable, '-B', str(installed), 'inspect-compatibility',
            '--root', str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertTrue(result['complete'])
        self.assertEqual(result['manifest']['classification'], 'exact-v1-declaration')
        self.assertFalse(result['integration_approved'])


if __name__ == '__main__':
    unittest.main()
