from copy import deepcopy
from datetime import datetime, timezone
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
from population_dotnet import DotNetAnalyzer
from population_normalize import CandidateNormalizer, GROUPS, validate_records
from population_scan import RepositoryScanner

CLI = Path(__file__).resolve().parents[1] / 'kb.py'
HEADER = 'Microsoft Visual Studio Solution File, Format Version 12.00\n'
GUID = '{5751E520-961D-4769-AF60-D7BB815D412A}'
TYPE = '{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}'


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertEqual(kb.init(self.root / '.ai'), [])

    def write(self, name, text='<Project/>'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def extraction(self, exclusions=()):
        return DotNetAnalyzer().extract(self.root, RepositoryScanner().scan(self.root, exclusions))

    def normalize(self, extraction=None):
        return CandidateNormalizer().normalize(
            self.root, self.extraction() if extraction is None else extraction)

    def seed(self, report):
        # Explicit fixture construction in a disposable synthetic repository only.
        for group, directory in GROUPS.items():
            for index, record in enumerate(report['records'][group]):
                self.write('.ai/' + directory + f'/fixture-{index}.json', json.dumps(record))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def codes(self, report):
        return {d['code'] for d in report['diagnostics']}

    def entry(self, report, identifier):
        return next(e for e in report['change_set'] if e['id'] == identifier)

    def context(self, report, kind):
        return next(c for c in report['contexts'] if c['kind'] == kind)

    def assert_valid(self, report):
        self.assertTrue(report['ok'], json.dumps(report, indent=2))
        for view in ['existing', 'proposed', 'combined_preserving_existing']:
            self.assertTrue(report['validation'][view]['ok'])

    def test_every_b_kind_and_complete_schema_compatibility(self):
        self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework>'
                   '</PropertyGroup><ItemGroup><ProjectReference Include="Other.csproj"/>'
                   '<PackageReference Include="NUnit" Version="4.5.1"/></ItemGroup></Project>')
        self.write('Other.csproj')
        self.write('App.sln', HEADER + f'Project("{TYPE}") = "App", "App.csproj", "{GUID}"\n')
        report = self.normalize()
        self.assert_valid(report)
        self.assertEqual({c['kind'] for c in report['contexts']},
                         {'project', 'project_property', 'project_reference', 'package_reference',
                          'package_version', 'solution_membership'})
        self.assertEqual(len(report['records']['claims']), len(report['records']['evidence']))
        for group, kind in [('claims', 'claim'), ('evidence', 'evidence'), ('relationships', 'relationship')]:
            schema = kb.read_json(self.root / '.ai/schema' / (kind + '.schema.json'))
            for record in report['records'][group]:
                self.assertFalse(kb.schema_errors(record, schema))
        self.assertEqual(report['validation']['proposed']['record_counts'], report['counts'])

    def test_real_observation_time_no_invented_verification(self):
        self.write('App.csproj')
        start = datetime.now(timezone.utc)
        report = self.normalize()
        end = datetime.now(timezone.utc)
        observed = datetime.fromisoformat(report['observation']['captured_at'].replace('Z', '+00:00'))
        self.assertLessEqual(start, observed)
        self.assertLessEqual(observed, end)
        for evidence in report['records']['evidence']:
            self.assertEqual(evidence['captured_at'], report['observation']['captured_at'])
        self.assertTrue(all(c['last_verified'] is None and c['status'] == 'NEEDS_HUMAN_CONFIRMATION'
                            for c in report['records']['claims']))

    def test_stable_ids_and_changeset_across_live_runs(self):
        self.write('App.csproj')
        first, second = self.normalize(), self.normalize()
        self.assertEqual(first['change_set'], second['change_set'])
        self.assertEqual([c['id'] for c in first['records']['claims']],
                         [c['id'] for c in second['records']['claims']])
        self.assertEqual([e['id'] for e in first['records']['evidence']],
                         [e['id'] for e in second['records']['evidence']])

    def test_entire_report_deterministic_for_same_observation_clock(self):
        self.write('App.csproj')
        with patch('population_normalize.utc_now', return_value='2000-01-01T00:00:00Z'):
            self.assertEqual(self.normalize(), self.normalize())

    def test_formatting_only_change_refreshes_same_evidence_id(self):
        path = self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net10.0'
                          '</TargetFramework></PropertyGroup></Project>')
        first = self.normalize()
        self.seed(first)
        path.write_text('<Project>\n<PropertyGroup>\n<TargetFramework> net10.0 </TargetFramework>'
                        '</PropertyGroup></Project>', encoding='utf-8')
        before = self.snapshot()
        second = self.normalize()
        self.assert_valid(second)
        self.assertEqual({c['id'] for c in first['records']['claims']},
                         {c['id'] for c in second['records']['claims']})
        self.assertEqual({e['id'] for e in first['records']['evidence']},
                         {e['id'] for e in second['records']['evidence']})
        self.assertTrue(all(self.entry(second, e['id'])['classification'] == 'potential update'
                            for e in second['records']['evidence']))
        self.assertEqual(before, self.snapshot())

    def test_substantive_change_potential_update_and_old_records_retained(self):
        path = self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net9.0'
                          '</TargetFramework></PropertyGroup></Project>')
        first = self.normalize()
        self.seed(first)
        old = self.context(first, 'project_property')
        path.write_text('<Project><PropertyGroup><TargetFramework>net10.0'
                        '</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
        before = self.snapshot()
        second = self.normalize()
        new = self.context(second, 'project_property')
        self.assertNotEqual(old['claim_id'], new['claim_id'])
        self.assertEqual(self.entry(second, new['claim_id'])['classification'], 'potential update')
        self.assertEqual(self.entry(second, old['claim_id'])['classification'], 'unresolved')
        self.assert_valid(second)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_declarations_deduplicate_records_preserve_locations(self):
        self.write('App.csproj', '<Project><ItemGroup><ProjectReference Include="Other.csproj"/>'
                   '<ProjectReference Include="Other.csproj"/></ItemGroup></Project>')
        self.write('Other.csproj')
        report = self.normalize()
        matches = [c for c in report['contexts'] if c['kind'] == 'project_reference']
        self.assertEqual(len(matches), 1)
        evidence = next(e for e in report['records']['evidence'] if e['id'] == matches[0]['evidence_id'])
        locations = json.loads(evidence['location']['reference'].split('#locations=')[1])
        self.assertEqual(len(locations), 2)
        self.assert_valid(report)

    def test_conditional_reference_is_declaration_not_active_dependency(self):
        self.write('App.csproj', '''<Project><ItemGroup Condition="'$(Configuration)' == 'Debug'">
<ProjectReference Include="Other.csproj" Condition="Exists('Other.csproj')"/>
</ItemGroup></Project>''')
        self.write('Other.csproj')
        report = self.normalize()
        context = self.context(report, 'project_reference')
        claim = next(c for c in report['records']['claims'] if c['id'] == context['claim_id'])
        self.assertEqual(context['conditions'],
                         ["'$(Configuration)' == 'Debug'", "Exists('Other.csproj')"])
        self.assertEqual(context['active_evaluated_dependency'], 'unknown')
        self.assertIn("Exists('Other.csproj')", claim['statement'])
        self.assertIn('not evaluated', claim['statement'])
        self.assertEqual(self.entry(report, claim['id'])['classification'], 'unresolved')
        self.assertFalse(claim['depends_on'])
        self.assert_valid(report)

    def test_existence_independent_of_project_evaluation_condition(self):
        self.write('App.csproj', '<Project Condition="false"/>')
        report = self.normalize()
        context = self.context(report, 'project')
        self.assertEqual(context['file_existence'], 'observed-source-file')
        self.assertEqual(context['conditions'], [])
        self.assertEqual(context['declared_xml_conditions'], ['false'])

    def test_missing_reference_does_not_prove_target_existence(self):
        self.write('App.csproj', '<Project><ItemGroup><ProjectReference Include="Absent.csproj"/>'
                   '</ItemGroup></Project>')
        report = self.normalize()
        reference = self.context(report, 'project_reference')
        self.assertEqual(reference['resolution'], 'not-in-inventory')
        self.assertEqual(self.entry(report, reference['claim_id'])['classification'], 'unresolved')
        self.assertEqual([c['source'] for c in report['contexts'] if c['kind'] == 'project'], ['App.csproj'])
        self.assert_valid(report)

    def test_unresolved_expressions_preserved_in_claim_and_context(self):
        self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>$(Framework)'
                   '</TargetFramework></PropertyGroup><ItemGroup>'
                   '<ProjectReference Include="$(Root)/Other.csproj"/></ItemGroup></Project>')
        report = self.normalize()
        self.assertIn('$(Framework)', json.dumps(report['records']))
        self.assertIn('$(Root)', json.dumps(report['records']))
        for context in report['contexts']:
            if context['kind'] != 'project':
                self.assertEqual(self.entry(report, context['claim_id'])['classification'], 'unresolved')
        self.assert_valid(report)

    def test_exact_substantiation_and_complete_provenance(self):
        self.write('App.csproj')
        report = self.normalize()
        for claim in report['records']['claims']:
            evidence = next(e for e in report['records']['evidence'] if e['id'] in claim['evidence'])
            self.assertEqual(evidence['substantiates'], [claim['id']])
            self.assertEqual(evidence['type'], 'direct-technical')
            self.assertEqual(evidence['status'], 'active')
            self.assertEqual(evidence['source'], 'App.csproj')
            self.assertTrue(evidence['description'])
            self.assertIn('static-xml-declaration-v1', evidence['provenance']['method'])
            self.assertIn('static-dotnet-normalization-v1', evidence['provenance']['method'])

    def test_missing_and_invalid_extraction_evidence_is_rejected(self):
        self.write('App.csproj')
        extraction = self.extraction()
        for evidence in [[], [{}]]:
            changed = deepcopy(extraction)
            changed['candidates'][0]['evidence'] = evidence
            report = self.normalize(changed)
            self.assertFalse(report['ok'])
            self.assertFalse(report['records']['claims'])

    def test_original_validator_detects_missing_evidence_and_bad_links(self):
        self.write('App.csproj')
        records = self.normalize()['records']
        changed = deepcopy(records)
        changed['evidence'] = []
        self.assertFalse(validate_records(self.root / '.ai', changed)['ok'])
        changed = deepcopy(records)
        changed['evidence'][0]['substantiates'] = ['missing.claim']
        self.assertFalse(validate_records(self.root / '.ai', changed)['ok'])
        changed = deepcopy(records)
        changed['evidence'][0]['captured_at'] = 'not-a-date'
        self.assertFalse(validate_records(self.root / '.ai', changed)['ok'])
        changed = deepcopy(records)
        changed['claims'][0].update(status='CONFIRMED', last_verified='2000-01-01')
        changed['evidence'][0]['substantiates'] = []
        self.assertFalse(validate_records(self.root / '.ai', changed)['ok'])

    def test_staging_ids_cannot_escape_to_host_paths(self):
        self.write('App.csproj')
        records = self.normalize()['records']
        records['claims'][0]['id'] = '../../escape'
        before = self.snapshot()
        self.assertFalse(validate_records(self.root / '.ai', records)['ok'])
        self.assertEqual(before, self.snapshot())

    def test_existing_generated_records_are_unchanged_and_reuse_capture_time(self):
        self.write('App.csproj')
        first = self.normalize()
        self.seed(first)
        before = self.snapshot()
        second = self.normalize()
        self.assertEqual(first['records'], second['records'])
        self.assertTrue(all(e['classification'] == 'unchanged' for e in second['change_set']))
        self.assertEqual(before, self.snapshot())
        self.assert_valid(second)

    def test_preserve_human_confirmed_knowledge(self):
        self.write('App.csproj')
        first = self.normalize()
        claim = first['records']['claims'][0]
        claim.update(status='CONFIRMED', last_verified='2000-01-01')
        claim['provenance'] = {'actor': 'human-reviewer', 'method': 'manual inspection'}
        self.seed(first)
        before = self.snapshot()
        second = self.normalize()
        self.assertEqual(self.entry(second, claim['id'])['classification'], 'conflict')
        self.assertEqual(before, self.snapshot())
        self.assert_valid(second)

    def test_changed_value_conflicts_with_confirmed_prior_subject(self):
        path = self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net9.0'
                          '</TargetFramework></PropertyGroup></Project>')
        first = self.normalize()
        old_id = self.context(first, 'project_property')['claim_id']
        claim = next(c for c in first['records']['claims'] if c['id'] == old_id)
        claim.update(status='CONFIRMED', last_verified='2000-01-01')
        self.seed(first)
        path.write_text('<Project><PropertyGroup><TargetFramework>net10.0'
                        '</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
        second = self.normalize()
        new_id = self.context(second, 'project_property')['claim_id']
        self.assertEqual(self.entry(second, new_id)['classification'], 'conflict')
        self.assertIn(old_id, self.entry(second, new_id)['related_ids'])
        self.assert_valid(second)

    def test_multiple_values_same_subject_require_review_not_fake_conflict_edges(self):
        self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net9.0</TargetFramework>'
                   '<TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        report = self.normalize()
        properties = [c for c in report['contexts'] if c['kind'] == 'project_property']
        self.assertEqual(len(properties), 2)
        for context in properties:
            self.assertEqual(self.entry(report, context['claim_id'])['classification'], 'conflict')
        self.assertTrue(all(c['conflicts_with'] == [] for c in report['records']['claims']))
        self.assertEqual(report['records']['relationships'], [])
        self.assert_valid(report)

    def test_distinct_conditions_are_not_mutually_conflicting(self):
        self.write('App.csproj', '<Project><PropertyGroup>'
                   '<TargetFramework Condition="a">net9.0</TargetFramework>'
                   '<TargetFramework Condition="b">net10.0</TargetFramework></PropertyGroup></Project>')
        report = self.normalize()
        self.assertNotIn('conflict', {c['classification'] for c in report['change_set']})

    def test_removed_source_stale_evidence_and_claims_never_deleted(self):
        source = self.write('App.csproj')
        first = self.normalize()
        self.seed(first)
        source.unlink()
        before = self.snapshot()
        second = self.normalize()
        self.assert_valid(second)
        self.assertFalse(second['records']['claims'])
        self.assertTrue(all(e['classification'] == 'unresolved' for e in second['change_set']))
        self.assertIn('source-not-observed-removed-excluded-or-unsupported',
                      {r for e in second['change_set'] for r in e['reasons']})
        self.assertEqual(before, self.snapshot())

    def test_inactive_evidence_never_silently_reactivated(self):
        self.write('App.csproj')
        first = self.normalize()
        for status in ['retracted', 'superseded']:
            with self.subTest(status=status):
                first['records']['evidence'][0]['status'] = status
                self.seed(first)
                before = self.snapshot()
                second = self.normalize()
                evidence_id = first['records']['evidence'][0]['id']
                self.assertEqual(self.entry(second, evidence_id)['classification'], 'conflict')
                self.assertEqual(before, self.snapshot())
                self.assert_valid(second)

    def test_uninterpreted_human_prose_is_explicit_unresolved_overlap(self):
        self.write('App.csproj')
        first = self.normalize()
        claim = first['records']['claims'][0]
        claim.update(id='human.architecture', statement='Human architectural assertion.', type='architecture')
        first['records']['evidence'][0]['substantiates'] = [claim['id']]
        self.seed(first)
        before = self.snapshot()
        second = self.normalize()
        self.assertIn('uninterpreted-canonical-overlap',
                      {r for e in second['change_set'] for r in e['reasons']})
        self.assertEqual(before, self.snapshot())
        self.assert_valid(second)

    def test_relationship_context_not_canonical_depends_on(self):
        self.write('App.csproj', '<Project><ItemGroup><ProjectReference Include="Other.csproj"/>'
                   '</ItemGroup></Project>')
        self.write('Other.csproj')
        report = self.normalize()
        self.assertEqual(report['records']['relationships'], [])
        self.assertTrue(all(c['depends_on'] == [] for c in report['records']['claims']))
        self.assertIn('no-canonical-dependency-relationships', self.codes(report))
        changed = deepcopy(report['records'])
        a, b = changed['claims'][:2]
        changed['relationships'] = [{'id': 'bad.relation', 'type': 'project_reference',
                                     'from': a['id'], 'to': b['id'],
                                     'provenance': {'actor': 'test', 'method': 'synthetic'}}]
        self.assertFalse(validate_records(self.root / '.ai', changed)['ok'])

    def test_existing_v1_relationships_preserved_and_validated(self):
        self.write('App.csproj')
        claims = [{'id': 'human.one', 'statement': 'One.', 'type': 'technical_fact',
                   'status': 'UNKNOWN', 'evidence': [], 'provenance': {'actor': 'human', 'method': 'manual'},
                   'last_verified': None, 'depends_on': [], 'conflicts_with': []}]
        claims.append(dict(claims[0], id='human.two', statement='Two.', depends_on=['human.one']))
        relationship = {'id': 'human.link', 'type': 'depends_on', 'from': 'human.two', 'to': 'human.one',
                        'provenance': {'actor': 'human', 'method': 'manual'}}
        self.seed({'records': {'claims': claims, 'evidence': [], 'relationships': [relationship]}})
        before = self.snapshot()
        report = self.normalize()
        self.assert_valid(report)
        self.assertEqual(self.entry(report, 'human.link')['classification'], 'unchanged')
        self.assertEqual(before, self.snapshot())

    def test_no_business_rules_architecture_or_name_inference(self):
        self.write('BusinessRules.PaymentOwner.csproj')
        report = self.normalize()
        self.assertTrue(all(c['type'] == 'technical_fact' and c['status'] != 'CONFIRMED'
                            for c in report['records']['claims']))
        self.assertIn('filename label', report['records']['claims'][0]['statement'])
        self.assertNotIn('responsible', json.dumps(report['records']))

    def test_no_network_execution_canonical_or_host_modifications(self):
        self.write('App.csproj', '<Project><Target Name="Build"><Exec Command="NEVER_EXECUTE"/>'
                   '</Target><PropertyGroup><Password>DO_NOT_COPY</Password></PropertyGroup></Project>')
        self.write('Directory.Build.props', 'DO_NOT_PARSE')
        self.write('.editorconfig', 'keep')
        before = self.snapshot()
        extraction = self.extraction()
        def denied(*args, **kwargs):
            raise AssertionError('network or execution attempted')
        with patch.object(socket, 'socket', denied), patch.object(socket, 'getaddrinfo', denied), \
                patch.object(subprocess, 'Popen', denied), patch.object(os, 'system', denied):
            report = self.normalize(extraction)
        self.assert_valid(report)
        self.assertEqual(before, self.snapshot())
        for secret in ['DO_NOT_COPY', 'DO_NOT_PARSE', 'NEVER_EXECUTE']:
            self.assertNotIn(secret, json.dumps(report))

    def test_tampered_statement_source_hash_and_stale_extraction_rejected(self):
        source = self.write('App.csproj')
        original = self.extraction()
        changed = deepcopy(original)
        changed['candidates'][0]['value']['name'] = 'fabrication'
        self.assertFalse(self.normalize(changed)['ok'])
        changed = deepcopy(original)
        changed['candidates'][0]['evidence'][0]['content_hash'] = 'sha256:' + '0' * 64
        self.assertFalse(self.normalize(changed)['ok'])
        source.write_text('<Project Sdk="Changed"/>', encoding='utf-8')
        self.assertFalse(self.normalize(original)['ok'])

    def test_invalid_canonical_input_is_not_repaired(self):
        self.write('App.csproj')
        self.write('.ai/knowledge/claims/bad.json', '{"id":"missing-fields"}')
        before = self.snapshot()
        report = self.normalize()
        self.assertFalse(report['ok'])
        self.assertFalse(report['validation']['existing']['ok'])
        self.assertFalse(report['records']['claims'])
        self.assertEqual(before, self.snapshot())

    def test_validator_reuse_three_isolated_views(self):
        self.write('App.csproj')
        with patch('kb.validate', wraps=kb.validate) as validator:
            report = self.normalize()
        self.assert_valid(report)
        self.assertEqual(validator.call_count, 3)
        for call in validator.call_args_list:
            self.assertNotEqual(call.args[0], self.root / '.ai')
            self.assertFalse(call.args[0].exists())  # Staging has been cleaned.

    def test_cli_portability_dry_run_and_deterministic_changeset(self):
        self.write('App.csproj')
        before = self.snapshot()
        def run(cli):
            result = subprocess.run([sys.executable, '-B', str(cli), 'normalize',
                                     '--root', str(self.root), '--json'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        first = run(CLI)
        second = run(self.root / '.ai/tools/kb.py')
        self.assertEqual(first['change_set'], second['change_set'])
        self.assertEqual(before, self.snapshot())
        self.assert_valid(first)

    def test_slnx_membership_without_invented_project_identifiers(self):
        self.write('App.csproj')
        self.write('App.slnx', '<Solution><Folder Name="/src/">'
                   '<Project Path="App.csproj"/></Folder></Solution>')
        report = self.normalize()
        context = self.context(report, 'solution_membership')
        self.assertEqual(context['declared_value']['declared_path'], 'App.csproj')
        self.assertNotIn('declared_id', context['declared_value'])
        self.assertNotIn('name', context['declared_value'])
        self.assert_valid(report)

    def test_multiple_package_versions_are_candidate_conflicts(self):
        self.write('App.csproj', '<Project><ItemGroup>'
                   '<PackageReference Include="NUnit" Version="4.5.1"/>'
                   '<PackageReference Include="NUnit" Version="4.5.2"/>'
                   '</ItemGroup></Project>')
        report = self.normalize()
        versions = [c for c in report['contexts'] if c['kind'] == 'package_version']
        self.assertEqual(len(versions), 2)
        for context in versions:
            self.assertEqual(self.entry(report, context['claim_id'])['classification'], 'conflict')
        self.assert_valid(report)

    def test_pinned_schema_mutation_fails_without_repair(self):
        self.write('App.csproj')
        schema_path = self.root / '.ai/schema/claim.schema.json'
        schema = kb.read_json(schema_path)
        schema['required'] = []
        schema_path.write_text(json.dumps(schema), encoding='utf-8')
        before = self.snapshot()
        report = self.normalize()
        self.assertFalse(report['ok'])
        self.assertFalse(report['validation']['existing']['ok'])
        self.assertEqual(before, self.snapshot())

    def test_deterministic_changesets_with_pending_evidence_refresh(self):
        source = self.write('App.csproj')
        self.seed(self.normalize())
        source.write_text('<Project>\n</Project>', encoding='utf-8')
        first, second = self.normalize(), self.normalize()
        self.assertEqual(first['change_set'], second['change_set'])
        self.assertIn('potential update', {e['classification'] for e in first['change_set']})


if __name__ == '__main__':
    unittest.main()
