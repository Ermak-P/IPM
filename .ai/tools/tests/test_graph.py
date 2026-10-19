"""Offline graph/report regression tests; canonical fixtures are disposable only."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb
from knowledge_graph import (GraphBuilder, GraphInputError, canonical_graph,
                             human_report, identity, save_generated)
from population_dotnet import DotNetAnalyzer, canonical_json
from population_normalize import CandidateNormalizer, GROUPS
from population_scan import RepositoryScanner
from population_transaction import PopulationError, PopulationStore

CLI = Path(__file__).resolve().parents[1] / 'kb.py'
PROVENANCE = {'actor': 'fixture-human', 'method': 'fixture-review'}


class Interrupted(BaseException):
    pass


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertEqual(kb.init(self.root / '.ai'), [])
        self.builder = GraphBuilder()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        return target

    def seed(self, claims=(), evidence=(), relationships=()):
        for group, records in [('claims', claims), ('evidence', evidence), ('relationships', relationships)]:
            for record in records:
                self.write('.ai/' + GROUPS[group] + '/' + record['id'] + '.json', canonical_json(record))

    def claim(self, identifier='claim.a', **extra):
        return dict(id=identifier, statement='A literal fixture claim.', type='technical_fact',
                    status='NEEDS_HUMAN_CONFIRMATION', evidence=[], provenance=PROVENANCE,
                    last_verified=None, depends_on=[], conflicts_with=[], **extra)

    def evidence(self, identifier='evidence.a', claims=('claim.a',), **extra):
        value = dict(id=identifier, type='direct-technical', status='active', source='A.csproj',
                     provenance=PROVENANCE, captured_at='2026-01-01T00:00:00Z',
                     description='Fixture evidence reference only.', location={'reference': 'A.csproj#line=1'},
                     substantiates=list(claims))
        value.update(extra)
        return value

    def multi(self):
        self.write('A.csproj', '<Project><PropertyGroup><TargetFrameworks>net9.0;net10.0</TargetFrameworks>'
            '</PropertyGroup><ItemGroup><ProjectReference Include="B.csproj"/>'
            '<PackageReference Include="Example" Version="1.2.3"/></ItemGroup></Project>')
        self.write('B.csproj', '<Project><ItemGroup><ProjectReference Include="C.csproj"/></ItemGroup></Project>')
        self.write('C.csproj', '<Project/>')
        self.write('App.slnx', '<Solution><Project Path="A.csproj"/><Project Path="B.csproj"/>'
                   '<Project Path="C.csproj"/></Solution>')

    def build(self, view='canonical'):
        result = self.builder.build(self.root, view)
        self.assertTrue(result['ok'])
        graph = result['graph']
        self.assertEqual(len({n['id'] for n in graph['nodes']}), len(graph['nodes']))
        self.assertEqual(len({e['id'] for e in graph['edges']}), len(graph['edges']))
        ids = {n['id'] for n in graph['nodes']}
        self.assertTrue(all(e['from'] in ids and e['to'] in ids for e in graph['edges']))
        return graph

    def edges(self, graph, kind):
        return [e for e in graph['edges'] if e['kind'] == kind]

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def normalize(self):
        return CandidateNormalizer().normalize(self.root,
            DotNetAnalyzer().extract(self.root, RepositoryScanner().scan(self.root)))

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(CLI), *args, '--root', str(self.root)],
                              capture_output=True, text=True)

    def test_empty_canonical_and_default_boundary(self):
        graph = self.build()
        self.assertEqual(graph['view'], 'canonical')
        self.assertEqual(graph['authority'], 'validated-canonical-records')
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])
        self.assertFalse(graph['semantic_truth_established'])

    def test_claim_evidence_and_provenance_links(self):
        claim = self.claim(); claim['evidence'] = ['evidence.a']
        self.seed([claim], [self.evidence()])
        graph = self.build()
        self.assertEqual(len(self.edges(graph, 'cites_evidence')), 1)
        self.assertEqual(len(self.edges(graph, 'substantiates')), 1)
        self.assertEqual(len(self.edges(graph, 'has_provenance')), 2)
        self.assertEqual(len(self.edges(graph, 'references_source')), 1)
        node = next(n for n in graph['nodes'] if n['id'] == 'evidence.a')
        self.assertEqual(node['data']['captured_at'], '2026-01-01T00:00:00Z')

    def test_derived_metadata_nodes_cannot_collide_with_valid_canonical_ids(self):
        # Contract IDs may legitimately look like a derived source/provenance hash.
        a = self.claim(identity('source', 'A.csproj'))
        b = self.claim(identity('provenance', PROVENANCE))
        a['evidence'] = ['evidence.a']
        self.seed([a, b], [self.evidence(claims=[a['id']])])
        graph = self.build()
        self.assertEqual({n['id'] for n in graph['nodes'] if n['kind'] == 'claim'}, {a['id'], b['id']})

    def test_explicit_depends_on_arrays_and_relationship_merge(self):
        a, b = self.claim(), self.claim('claim.b')
        a['depends_on'] = [b['id']]
        self.seed([a, b], relationships=[dict(id='relation.a', type='depends_on',
            **{'from': a['id'], 'to': b['id']}, provenance=PROVENANCE)])
        edge, = self.edges(self.build(), 'depends_on')
        self.assertTrue(edge['directed'])
        self.assertEqual(edge['canonical_relationship_ids'], ['relation.a'])
        self.assertEqual(edge['from'], a['id'])

    def test_claim_dependency_without_relationship_file(self):
        a, b = self.claim(), self.claim('claim.b'); a['depends_on'] = ['claim.b']
        self.seed([a, b])
        edge, = self.edges(self.build(), 'depends_on')
        self.assertEqual(edge['canonical_relationship_ids'], [])

    def test_symmetric_conflict_is_one_undirected_edge(self):
        a, b = self.claim(), self.claim('claim.b')
        a['conflicts_with'] = ['claim.b']; b['conflicts_with'] = ['claim.a']
        self.seed([a, b], relationships=[dict(id='relation.conflict', type='conflicts_with',
            **{'from': 'claim.b', 'to': 'claim.a'}, provenance=PROVENANCE)])
        edge, = self.edges(self.build(), 'conflicts_with')
        self.assertFalse(edge['directed'])
        self.assertEqual(edge['canonical_relationship_ids'], ['relation.conflict'])
        self.assertEqual(len(self.builder.report(self.root)['canonical']['explicit_unresolved_conflicts']), 1)

    def test_multiple_evidence_and_retracted_superseded_status(self):
        a = self.claim(); a['evidence'] = ['evidence.a', 'evidence.b', 'evidence.c']
        self.seed([a], [self.evidence(), self.evidence('evidence.b', status='retracted'),
                        self.evidence('evidence.c', status='superseded')])
        self.assertEqual(len(self.edges(self.build(), 'substantiates')), 3)
        report = self.builder.report(self.root)
        self.assertEqual(report['canonical']['evidence']['by_status'], {'active': 1, 'retracted': 1, 'superseded': 1})
        self.assertEqual(report['canonical']['claims_without_sufficient_verification'], ['claim.a'])

    def test_unverified_status_never_promoted(self):
        self.seed([self.claim()])
        node = next(n for n in self.build()['nodes'] if n['kind'] == 'claim')
        self.assertEqual(node['data']['status'], 'NEEDS_HUMAN_CONFIRMATION')
        self.assertIsNone(node['data']['last_verified'])

    def test_confirmed_requires_actual_contract_evidence(self):
        a = self.claim(); a.update(status='CONFIRMED', last_verified='2026-01-01', evidence=['evidence.a'])
        self.seed([a], [self.evidence()])
        self.assertEqual(self.builder.report(self.root)['canonical']['claims_without_sufficient_verification'], [])
        self.write('.ai/evidence/evidence.a.json', canonical_json(self.evidence(status='retracted')))
        with self.assertRaises(GraphInputError):
            self.build()

    def test_invalid_canonical_rejects_all_views_and_report(self):
        self.write('.ai/knowledge/claims/bad.json', '{}')
        before = self.snapshot()
        for action in [lambda: self.build(), lambda: self.build('technical-preview'),
                       lambda: self.builder.report(self.root)]:
            with self.assertRaises(GraphInputError) as error:
                action()
            self.assertTrue(error.exception.details['validation']['errors'])
        self.assertEqual(before, self.snapshot())

    def test_preview_multi_project_membership_and_direct_only(self):
        self.multi()
        graph = self.build('technical-preview')
        self.assertEqual(graph['authority'], 'noncanonical-technical-observation-preview')
        self.assertEqual(sum(n['kind'] == 'observed_project' for n in graph['nodes']), 3)
        self.assertEqual(len(self.edges(graph, 'declared_solution_membership')), 3)
        self.assertEqual(len(self.edges(graph, 'declared_project_reference')), 2)
        self.assertEqual(self.edges(graph, 'depends_on'), [])
        paths = {n['id']: n['data'].get('path') for n in graph['nodes']}
        self.assertEqual({(paths[e['from']], paths[e['to']]) for e in self.edges(graph, 'declared_project_reference')},
                         {('A.csproj', 'B.csproj'), ('B.csproj', 'C.csproj')})
        self.assertEqual(self.build()['nodes'], [])

    def test_sln_and_slnx_empty_solution_discovery(self):
        self.write('Empty.slnx', '<Solution/>')
        self.write('Legacy.sln', 'Microsoft Visual Studio Solution File, Format Version 12.00\n')
        graph = self.build('technical-preview')
        self.assertEqual(sum(n['kind'] == 'observed_solution' for n in graph['nodes']), 2)
        self.assertEqual(len(graph['edges']), 0)

    def test_condition_preserved_not_evaluated(self):
        self.write('A.csproj', '<Project><ItemGroup Condition="false"><ProjectReference Include="B.csproj"/>'
                   '</ItemGroup></Project>')
        self.write('B.csproj', '<Project/>')
        edge, = self.edges(self.build('technical-preview'), 'declared_project_reference')
        self.assertEqual(edge['metadata']['conditions'], ['false'])
        self.assertEqual(edge['metadata']['active_evaluated_dependency'], 'unknown')
        report = self.builder.report(self.root)
        self.assertEqual(report['technical_observations']['conditional_dependencies'], [edge['id']])

    def test_missing_and_unresolved_expression_targets(self):
        self.write('A.csproj', '<Project><ItemGroup><ProjectReference Include="Missing.csproj"/>'
                   '<ProjectReference Include="$(Root)/B.csproj"/></ItemGroup></Project>')
        graph = self.build('technical-preview')
        self.assertEqual(sum(n['kind'] == 'unresolved_project_reference' for n in graph['nodes']), 2)
        self.assertEqual({e['metadata']['resolution'] for e in self.edges(graph, 'declared_project_reference')},
                         {'not-in-inventory', 'unresolved-expression'})
        self.assertEqual(len(self.builder.report(self.root)['technical_observations']['unresolved_dependencies']), 2)

    def test_packages_versions_and_framework_declarations(self):
        self.multi(); graph = self.build('technical-preview')
        self.assertEqual(len(self.edges(graph, 'declared_package_reference')), 1)
        edge, = self.edges(graph, 'declared_package_version')
        self.assertEqual(edge['metadata']['declared_value']['declared'], '1.2.3')
        framework, = [n for n in graph['nodes'] if n['kind'] == 'target_framework_declaration']
        self.assertEqual(framework['data']['declared'], 'net9.0;net10.0')
        self.assertEqual(len(edge['source_references']), 1)
        self.assertTrue(edge['metadata']['proposed_evidence_ids'])
        self.assertEqual(edge['supporting_claim_ids'], [])

    def test_canonical_observation_disagreement_preserves_both(self):
        self.write('A.csproj', '<Project><PropertyGroup><TargetFramework>net9.0</TargetFramework></PropertyGroup></Project>')
        proposal = self.normalize()
        self.seed(**proposal['records'])
        canonical_before = self.build()
        self.write('A.csproj', '<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        report = self.builder.report(self.root)
        self.assertTrue(report['comparison']['classification_counts'].get('potential update'))
        self.assertIn('stale-content-hash', {e['observation'] for e in report['canonical']['source_evidence_observations']})
        self.assertEqual(canonical_before, self.build())
        self.assertIn('net10.0', canonical_json(self.build('technical-preview')))
        self.assertIn('net9.0', canonical_json(canonical_before))

    def test_identical_runs_exact_serialization_without_clock(self):
        self.multi()
        for view in ['canonical', 'technical-preview']:
            self.assertEqual(canonical_json(self.builder.build(self.root, view)), canonical_json(self.builder.build(self.root, view)))
        self.assertEqual(canonical_json(self.builder.report(self.root)), canonical_json(self.builder.report(self.root)))
        self.assertNotIn('captured_at', canonical_json(self.build('technical-preview')))

    def test_canonical_traversal_and_record_array_order_independence(self):
        a, b, c = self.claim(), self.claim('claim.b'), self.claim('claim.c')
        a['depends_on'] = ['claim.c', 'claim.b']
        self.seed([a, b, c]); graph = self.build()
        shutil.move(self.root / '.ai/knowledge/claims/claim.a.json', self.root / '.ai/knowledge/claims/z.json')
        # List order is preserved inside canonical record data (not semantically normalized).
        self.assertEqual(graph, self.build())
        values = {'claims': [a, b, c], 'evidence': [], 'relationships': []}
        self.assertEqual(canonical_graph(values), canonical_graph({**values, 'claims': [c, b, a]}))

    def test_inventory_traversal_order_does_not_change_graph(self):
        self.multi(); baseline = self.build('technical-preview')
        scan = RepositoryScanner.scan
        def reversed_scan(scanner, root, exclusions=()):
            result = scan(scanner, root, exclusions)
            result['sources'].reverse()
            result['skipped'].reverse()
            return result
        with patch.object(RepositoryScanner, 'scan', reversed_scan):
            self.assertEqual(baseline, self.build('technical-preview'))

    def test_formatting_change_keeps_node_and_edge_ids(self):
        self.multi(); before = self.build('technical-preview')
        path = self.root / 'A.csproj'
        path.write_text(path.read_text().replace('><', '>\n  <'), encoding='utf-8')
        after = self.build('technical-preview')
        self.assertEqual([n['id'] for n in before['nodes']], [n['id'] for n in after['nodes']])
        self.assertEqual([e['id'] for e in before['edges']], [e['id'] for e in after['edges']])
        self.assertNotEqual(before, after)  # locations and source hashes genuinely changed

    def test_duplicate_reference_no_duplicate_edges(self):
        self.write('A.csproj', '<Project><ItemGroup><ProjectReference Include="B.csproj"/>'
                   '<ProjectReference Include="B.csproj"/></ItemGroup></Project>')
        self.write('B.csproj', '<Project/>')
        edge, = self.edges(self.build('technical-preview'), 'declared_project_reference')
        self.assertEqual(len(edge['source_references']), 2)

    def test_rebuild_after_removed_source_retains_historical_claims(self):
        self.multi(); proposal = self.normalize(); self.seed(**proposal['records'])
        canonical = self.build()
        (self.root / 'C.csproj').unlink()
        preview = self.build('technical-preview')
        self.assertEqual(sum(n['kind'] == 'observed_project' for n in preview['nodes']), 2)
        self.assertEqual(self.build(), canonical)
        report = self.builder.report(self.root)
        self.assertIn('not-observed-removed-excluded-unsupported-or-external',
                      {e['observation'] for e in report['canonical']['source_evidence_observations']})
        self.assertTrue(report['technical_observations']['unresolved_dependencies'])

    def test_rebuild_after_canonical_changes(self):
        first = self.build(); self.seed([self.claim()]); second = self.build()
        self.assertNotEqual(first, second)
        self.assertEqual(sum(n['kind'] == 'claim' for n in second['nodes']), 1)

    def test_delete_generated_and_regenerate_byte_for_byte(self):
        self.multi(); report = self.builder.report(self.root)
        save_generated(self.root, 'knowledge-report.json', report)
        original = (self.root / '.ai/generated/knowledge-report.json').read_bytes()
        shutil.rmtree(self.root / '.ai/generated')
        save_generated(self.root, 'knowledge-report.json', self.builder.report(self.root))
        self.assertEqual(original, (self.root / '.ai/generated/knowledge-report.json').read_bytes())

    def test_read_only_canonical_and_host_byte_for_byte(self):
        self.multi(); before = self.snapshot()
        self.build(); self.build('technical-preview'); self.builder.report(self.root)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / '.ai/state/population').exists())

    def test_no_network_llm_or_project_execution(self):
        self.multi()
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('execution forbidden')), \
             patch.object(os, 'system', side_effect=AssertionError('execution forbidden')):
            self.build(); self.build('technical-preview'); self.builder.report(self.root)

    def test_recovery_gate_for_api_cli_and_generated_writer(self):
        self.multi(); store = PopulationStore(self.root); plan = store.prepare()['plan']
        def stop(phase, index=None):
            if phase == 'after_install':
                raise Interrupted()
        with patch('population_transaction._checkpoint', side_effect=stop):
            with self.assertRaises(Interrupted):
                store.apply(plan['fingerprint'], plan['fingerprint'])
        for action in [lambda: self.build(), lambda: self.build('technical-preview'),
                       lambda: self.builder.report(self.root),
                       lambda: save_generated(self.root, 'knowledge-report.json', {})]:
            with self.assertRaises(PopulationError):
                action()
        for command in ['build', 'report']:
            result = self.cli(command, '--json')
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ok'])
        store.recover(plan['fingerprint'])
        self.assertEqual(self.build()['nodes'], [])

    def test_concurrent_lock_gate(self):
        store = PopulationStore(self.root)
        store.prepare()
        with store.coordinate():
            for command in ['build', 'report']:
                result = self.cli(command, '--json')
                self.assertEqual(result.returncode, 1)

    def test_report_counts_connectivity_skipped_and_summary(self):
        self.multi(); self.seed([self.claim(), self.claim('claim.b')])
        self.write('obj/Hidden.csproj', '<broken>')
        self.write('notes.txt', 'not an analyzer input')
        report = self.builder.report(self.root)
        self.assertEqual(report['canonical']['claims']['by_status'], {'NEEDS_HUMAN_CONFIRMATION': 2})
        self.assertEqual(report['canonical']['claim_connectivity']['isolated_node_ids'], ['claim.a', 'claim.b'])
        self.assertEqual(report['technical_observations']['solution_count'], 1)
        self.assertEqual(report['technical_observations']['project_count'], 3)
        self.assertTrue(any(e['path'] == 'obj' and e['reason'] == 'excluded' for e in report['technical_observations']['skipped_inputs']))
        text = human_report(report)
        self.assertIn('NONCANONICAL PREVIEW', text)
        self.assertIn('declared, not evaluated', text)

    def test_malformed_and_unsafe_xml_report_diagnostics(self):
        for xml in ['<Project>', '<!DOCTYPE Project [<!ENTITY x SYSTEM "file:///secret">]><Project/>']:
            self.write('A.csproj', xml)
            result = self.cli('report', '--json')
            self.assertEqual(result.returncode, 1)
            error = json.loads(result.stdout)
            self.assertTrue(error['diagnostics'])
            self.assertNotIn('graph', error)
            self.assertFalse(error['ok'])

    def test_source_links_are_skipped_and_canonical_links_rejected(self):
        self.multi()
        try:
            (self.root / 'Linked.csproj').symlink_to(self.root / 'A.csproj')
        except OSError:
            self.skipTest('symlinks unavailable')
        report = self.builder.report(self.root)
        self.assertTrue(any(e['path'] == 'Linked.csproj' and e['reason'] == 'link-not-followed'
                            for e in report['technical_observations']['skipped_inputs']))
        (self.root / '.ai/evidence/link.json').symlink_to(self.root / 'A.csproj')
        with self.assertRaises(PopulationError):
            self.build()

    def test_generated_rejects_escape_link_hardlink_and_unexpected_objects(self):
        with self.assertRaises(PopulationError):
            save_generated(self.root, '../../host.txt', {})
        target = self.write('host.txt', 'preserve')
        artifact = self.root / '.ai/generated/knowledge-report.json'
        try:
            os.link(target, artifact)
        except OSError:
            self.skipTest('hardlinks unavailable')
        with self.assertRaises(PopulationError):
            save_generated(self.root, artifact.name, {})
        self.assertEqual(target.read_text(), 'preserve')
        artifact.unlink(); artifact.mkdir()
        with self.assertRaises(PopulationError):
            save_generated(self.root, artifact.name, {})

    def test_generated_link_directory_and_target_rejected(self):
        outside = self.root / 'host'; outside.mkdir()
        generated = self.root / '.ai/generated'
        shutil.rmtree(generated)
        try:
            generated.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(PopulationError):
            save_generated(self.root, 'knowledge-report.json', {})
        self.assertEqual(list(outside.iterdir()), [])
        generated.unlink(); generated.mkdir()
        (generated / 'knowledge-report.json').symlink_to(self.root / 'missing-host')
        with self.assertRaises(PopulationError):
            save_generated(self.root, 'knowledge-report.json', {})
        self.assertFalse((self.root / 'missing-host').exists())

    def test_canonical_external_source_never_opened(self):
        claim = self.claim(); claim['evidence'] = ['evidence.a']
        self.seed([claim], [self.evidence(source={'reference': 'https://example.invalid/private'})])
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
            report = self.builder.report(self.root)
        self.assertEqual(report['canonical']['source_evidence_observations'][0]['observation'],
                         'not-observed-removed-excluded-unsupported-or-external')

    def test_cli_stdout_and_explicit_generated_output(self):
        self.multi(); before = self.snapshot()
        for command in ['build', 'report']:
            result = self.cli(command, '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])
        self.assertEqual(before, self.snapshot())
        for options, filename in [(['build'], 'canonical-graph.json'),
                (['build', '--view', 'technical-preview'], 'technical-preview-graph.json'),
                (['report'], 'knowledge-report.json')]:
            result = self.cli(*options, '--json', '--write-generated')
            self.assertEqual(result.returncode, 0, result.stdout)
            saved = json.loads((self.root / '.ai/generated' / filename).read_text())
            self.assertEqual(saved, json.loads(result.stdout))
        summary = self.cli('report')
        self.assertEqual(summary.returncode, 0)
        self.assertIn('NONCANONICAL PREVIEW', summary.stdout)

    def test_cli_and_api_invalid_options(self):
        for options in [('report', '--view', 'canonical'), ('extract', '--write-generated'),
                        ('build', '--exclude', 'vendor'), ('build', '--approve', 'sha256:abc')]:
            self.assertEqual(self.cli(*options).returncode, 2)
        with self.assertRaises(PopulationError):
            self.builder.build(self.root, 'both')
        with self.assertRaises(PopulationError):
            self.builder.build(self.root, exclusions=['vendor'])

    def test_additional_exclusions_shared_by_preview_and_report(self):
        self.multi()
        graph = self.builder.build(self.root, 'technical-preview', ['C.csproj'])['graph']
        self.assertEqual(sum(n['kind'] == 'observed_project' for n in graph['nodes']), 2)
        report = self.builder.report(self.root, ['C.csproj'])
        self.assertEqual(report['technical_observations']['project_count'], 2)

    def test_concurrent_external_canonical_edit_is_detected(self):
        original = self.builder._unchanged
        def mutate(data):
            self.seed([self.claim()])
            original(data)
        with patch.object(self.builder, '_unchanged', side_effect=mutate):
            with self.assertRaisesRegex(PopulationError, 'canonical-changed-during-read'):
                self.build()

    def test_concurrent_external_source_edit_is_detected(self):
        self.multi(); original = self.builder._unchanged
        def mutate(data):
            self.write('C.csproj', '<Project><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
            original(data)
        with patch.object(self.builder, '_unchanged', side_effect=mutate):
            with self.assertRaisesRegex(PopulationError, 'sources-changed-during-read'):
                self.build('technical-preview')

    def test_generated_replace_failure_keeps_old_output_and_cleans_temp(self):
        save_generated(self.root, 'knowledge-report.json', {'old': True})
        with patch('knowledge_graph.os.replace', side_effect=PermissionError('sharing denied')):
            with self.assertRaises(PermissionError):
                save_generated(self.root, 'knowledge-report.json', {'new': True})
        directory = self.root / '.ai/generated'
        self.assertEqual(json.loads((directory / 'knowledge-report.json').read_text()), {'old': True})
        self.assertFalse(list(directory.glob('.graph-*')))


if __name__ == '__main__':
    unittest.main()
