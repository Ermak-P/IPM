from copy import deepcopy
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
import compatibility_adapter as adapter
from compatibility_adapter import CompatibilityAdapter, proposed_id
from compatibility_inspector import CompatibilityInspector
from population_normalize import validate_records

CLI = Path(__file__).resolve().parents[1] / 'kb.py'
FIXTURE = CLI.parent / 'examples/existing-knowledge/fixture.json'
PROVENANCE = {'actor': 'synthetic-author', 'method': 'explicit-fixture-observation'}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = CompatibilityAdapter()

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')
        return target

    def manifest(self, native=False):
        self.write('.ai/manifest.yaml', kb.MANIFEST if native else {'format':'harbor-team-architecture','revision':3})

    def pair(self, status='NEEDS_HUMAN_CONFIRMATION'):
        self.manifest()
        claim = dict(id='RULE/1', kind='business-policy', text='Synthetic explicit policy assertion.',
            state=status, support=['EV/1'], provenance=PROVENANCE, last_verified=None,
            depends_on=[], conflicts_with=[])
        evidence = dict(id='EV/1', kind='meeting-note', state='active', uri='urn:synthetic:note-1',
            provenance=PROVENANCE, captured_at='2026-01-01T12:00:00Z',
            location={'reference':'urn:synthetic:note-1#section-1'}, description='Synthetic note reference.', supports=['RULE/1'])
        self.seed(claim, evidence)
        return claim, evidence

    def seed(self, claim, evidence):
        self.write('.ai/knowledge/claims/a.json', claim)
        self.write('.ai/evidence/a.json', evidence)

    def propose(self, inspection=None):
        return self.tool.propose(self.root, inspection)

    def codes(self, report):
        return {d['code'] for d in report['diagnostics']}

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and not p.is_symlink()}

    def assert_valid(self, result, count=2):
        self.assertTrue(result['ok'], json.dumps(result, indent=2))
        self.assertEqual(result['metrics']['candidates_passing_isolated_structural_validation'], count)
        self.assertTrue(result['validation']['proposed_dataset']['ok'])
        self.assertTrue(validate_records(kb.SOURCE, result['records'])['ok'])
        self.assertFalse(result['integration_approved'])
        self.assertFalse(result['canonical_insertion_approved'])

    def test_complete_literal_harbor_mapping_and_reference_closure(self):
        original_claim, original_evidence = self.pair()
        before = self.snapshot(); result = self.propose(); self.assert_valid(result)
        claim, = result['records']['claims']; evidence, = result['records']['evidence']
        self.assertEqual(claim['id'], proposed_id('claims', 'RULE/1'))
        self.assertEqual(claim['evidence'], [evidence['id']])
        self.assertEqual(evidence['substantiates'], [claim['id']])
        self.assertEqual(claim['status'], 'NEEDS_HUMAN_CONFIRMATION')
        self.assertIsNone(claim['last_verified'])
        self.assertEqual(evidence['captured_at'], original_evidence['captured_at'])
        self.assertEqual(evidence['provenance'], original_evidence['provenance'])
        self.assertEqual(claim['provenance'], original_claim['provenance'])
        self.assertEqual(result['metrics']['records_requiring_human_review'], 2)
        self.assertTrue(all(m['original_id'] and m['source_content_hash'] for m in result['id_mappings']))
        self.assertEqual(before, self.snapshot())

    def test_original_harbor_blocked_without_fabrication(self):
        for name, content in json.loads(FIXTURE.read_text())['files'].items():
            self.write(name, content)
        before=self.snapshot(); report=self.propose()
        self.assertTrue(report['ok'])
        self.assertEqual(report['metrics']['legacy_records_inspected'], 5)
        self.assertEqual(report['metrics']['blocked_records'], 5)
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'], 0)
        self.assertTrue(report['validation']['proposed_dataset']['ok'])
        self.assertEqual(report['records'], {'claims': [], 'evidence': [], 'relationships': []})
        self.assertEqual(report['metrics']['unsupported_relationship_types'], 1)
        self.assertTrue(report['inspection']['graph_tools'])
        self.assertEqual(before, self.snapshot())

    def test_unknown_top_and_nested_properties_each_reported_and_blocked(self):
        claim, evidence=self.pair(); claim['custom_a']='private'; claim['custom_b']={"private":"value"}
        evidence['provenance']={**PROVENANCE,'review_tool':'private'}
        self.seed(claim,evidence); report=self.propose()
        fields={d.get('field') for d in report['diagnostics'] if d['code']=='unsupported-property-data-loss-risk'}
        self.assertTrue({'custom_a','custom_b','review_tool'} <= fields)
        self.assertEqual(report['metrics']['blocked_records'],2)
        self.assertNotIn('"private"',json.dumps(report))

    def test_unsafe_long_custom_field_diagnostic_is_bounded(self):
        claim,evidence=self.pair(); key='private secret '*1000;claim[key]='not echoed'
        self.seed(claim,evidence); report=self.propose()
        self.assertNotIn(key,json.dumps(report))
        self.assertTrue(any(d.get('field_fingerprint') for d in report['diagnostics']))

    def test_invalid_original_identity_and_stable_slash_identity(self):
        self.pair(); first=self.propose(); second=self.propose()
        self.assertEqual(first,second)
        claim,evidence=self.pair();claim['id']='bad\nidentity';self.seed(claim,evidence)
        report=self.propose()
        self.assertIn('missing-invalid-or-over-limit-original-id',self.codes(report))
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_duplicate_original_id_blocks_all_not_deduplicated(self):
        claim,evidence=self.pair();self.write('.ai/knowledge/claims/duplicate.json',claim)
        report=self.propose()
        self.assertIn('duplicate-original-id',self.codes(report))
        self.assertIn('unresolved-missing-ambiguous-or-wrong-kind-reference',self.codes(report))
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_native_id_collision_with_proposed_harbor_id(self):
        self.pair(); native=dict(id=proposed_id('claims','RULE/1'),statement='Literal native record.',
            type='technical_fact',status='UNKNOWN',evidence=[],provenance=PROVENANCE,last_verified=None,
            depends_on=[],conflicts_with=[])
        self.write('.ai/knowledge/claims/native.json',native)
        report=self.propose()
        self.assertIn('proposed-id-collision',self.codes(report))
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_missing_evidence_reference_not_erased(self):
        claim,evidence=self.pair();claim['support'].append('EV/missing');self.seed(claim,evidence)
        report=self.propose()
        self.assertIn('unresolved-missing-ambiguous-or-wrong-kind-reference',self.codes(report))
        self.assertIn('reference-closure-reaches-blocked-record',self.codes(report))
        self.assertEqual(report['records']['claims'],[])

    def test_withdrawn_and_approved_not_translated(self):
        claim,evidence=self.pair();claim['state']='approved';evidence['state']='withdrawn';self.seed(claim,evidence)
        report=self.propose()
        self.assertEqual(report['metrics']['blocked_records'],2)
        self.assertEqual({m['original_lifecycle'] for m in report['id_mappings']},{'withdrawn','approved'})
        self.assertEqual(report['records']['claims'],[])
        self.assertIn('unsupported-lifecycle-no-conversion',self.codes(report))

    def test_explicit_retracted_and_superseded_are_retained(self):
        for status in ['retracted','superseded']:
            claim,evidence=self.pair();evidence['state']=status;self.seed(claim,evidence)
            report=self.propose();self.assert_valid(report)
            self.assertEqual(report['records']['evidence'][0]['status'],status)

    def test_missing_capture_time_not_replaced_by_observed_on(self):
        claim,evidence=self.pair();evidence.pop('captured_at');evidence['observed_on']='2026-01-01';self.seed(claim,evidence)
        report=self.propose()
        self.assertIn('missing-observation-timestamp-no-fabrication',self.codes(report))
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_date_only_capture_time_not_repaired(self):
        claim,evidence=self.pair();evidence['captured_at']='2026-01-01';self.seed(claim,evidence)
        self.assertEqual(self.propose()['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_missing_provenance_not_invented_from_reviewer(self):
        claim,evidence=self.pair();evidence.pop('provenance');evidence['reviewer']='invented-human';self.seed(claim,evidence)
        report=self.propose()
        self.assertEqual(report['metrics']['missing_provenance'],1)
        self.assertIn('missing-explicit-provenance',self.codes(report))
        self.assertEqual(report['records']['evidence'],[])

    def test_business_confirmation_without_authority_rejected_by_core_validator(self):
        claim,evidence=self.pair('CONFIRMED');claim['last_verified']='2026-01-01';self.seed(claim,evidence)
        report=self.propose()
        self.assertTrue(report['ok'])
        self.assertFalse(report['validation']['attempted_reference_closed_dataset']['ok'])
        self.assertTrue(any('appropriate direct evidence' in e for e in report['validation']['attempted_reference_closed_dataset']['errors']))
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)
        self.assertIn('complete-dataset-validator-rejected',self.codes(report))

    def test_confirmed_status_only_preserved_with_explicit_structural_basis(self):
        claim,evidence=self.pair('CONFIRMED');claim['last_verified']='2026-01-01'
        evidence['kind']='direct-authoritative';self.seed(claim,evidence)
        report=self.propose();self.assert_valid(report)
        self.assertEqual(report['records']['claims'][0]['status'],'CONFIRMED')
        self.assertFalse(report['semantic_acceptance_established'])
        self.assertEqual(report['records']['evidence'][0]['provenance'],PROVENANCE)

    def test_missing_verification_event_never_created(self):
        claim,evidence=self.pair('CONFIRMED');evidence['kind']='direct-authoritative';self.seed(claim,evidence)
        report=self.propose()
        self.assertIn('missing-verification-event-no-fabrication',self.codes(report))
        self.assertEqual(report['records']['claims'],[])

    def test_no_status_promotion_for_inferred_unknown(self):
        for status in ['INFERRED','UNKNOWN','NEEDS_HUMAN_CONFIRMATION']:
            self.pair(status);report=self.propose();self.assert_valid(report)
            self.assertEqual(report['records']['claims'][0]['status'],status)

    def test_unsupported_component_relationship_and_conditional_field(self):
        self.pair();self.write('.ai/knowledge/relationships/component.json',dict(id='EDGE/1',kind='calls',
            source='A',target='B',conditional=True))
        report=self.propose();self.assert_valid(report)
        self.assertEqual(report['metrics']['unsupported_relationship_types'],1)
        self.assertEqual(report['records']['relationships'],[])
        self.assertTrue(any(d.get('field')=='conditional' for d in report['diagnostics']))

    def test_graph_ownership_blockers_preserved_without_tool_import(self):
        self.pair();self.write('.ai/tools/my_graph.py','raise AssertionError("NEVER EXECUTE")')
        report=self.propose();self.assert_valid(report)
        self.assertIn('graph-builder-ownership-selection-required',{d['code'] for d in report['inspection']['blockers']})
        self.assertFalse(report['graph_boundary']['tools_executed'])

    def test_compatible_native_v1_records_verbatim_and_native_relationships(self):
        self.manifest(native=True)
        a=dict(id='claim.a',statement='Literal native assertion.',type='technical_fact',status='UNKNOWN',
            evidence=[],provenance=PROVENANCE,last_verified=None,depends_on=['claim.b'],conflicts_with=[])
        b={**deepcopy(a),'id':'claim.b','depends_on':[]}
        relation=dict(id='relation.a',type='depends_on',**{'from':'claim.a','to':'claim.b'},provenance=PROVENANCE)
        self.write('.ai/knowledge/claims/a.json',a);self.write('.ai/knowledge/claims/b.json',b)
        self.write('.ai/knowledge/relationships/r.json',relation)
        report=self.propose();self.assert_valid(report,3)
        self.assertEqual(report['records']['claims'],[a,b]);self.assertEqual(report['records']['relationships'],[relation])

    def test_native_illegal_id_not_repaired_as_harbor(self):
        self.manifest(native=True)
        self.write('.ai/knowledge/claims/a.json',dict(id='bad/id',statement='literal',type='technical_fact',
            status='UNKNOWN',evidence=[],provenance=PROVENANCE,last_verified=None,depends_on=[],conflicts_with=[]))
        report=self.propose()
        self.assertIn('native-id-not-v1-compatible-no-repair',self.codes(report))
        self.assertIsNone(report['id_mappings'][0]['proposed_id'])

    def test_invalid_reference_shapes_are_not_silently_fixed(self):
        for raw in ['EV/1',{'id':'EV/1'},[1]]:
            claim,evidence=self.pair();claim['support']=raw;self.seed(claim,evidence)
            report=self.propose()
            self.assertIn('invalid-reference-field-shape-no-repair',self.codes(report))
            self.assertEqual(report['records']['claims'],[])

    def test_supported_explicit_source_base_and_ambiguous_base(self):
        claim,evidence=self.pair();evidence['uri']='.ai/sources/review.md';self.seed(claim,evidence)
        self.assertIn('ambiguous-or-unsafe-source-reference-base',self.codes(self.propose()))
        evidence['uri_base']='repository-root';self.seed(claim,evidence)
        report=self.propose();self.assert_valid(report)
        mapping=next(m for m in report['id_mappings'] if m['record_type']=='evidence')
        self.assertEqual(mapping['legacy_source_base'],'repository-root')

    def test_unsupported_container_versions_not_guessed(self):
        for manifest in [{'format':'foreign'}, {'format':'harbor-team-architecture','revision':4}]:
            self.write('.ai/manifest.yaml',manifest)
            report=self.propose()
            self.assertFalse(report['ok']);self.assertIn('unsupported-explicit-container-format',self.codes(report))

    def test_inspector_incomplete_cannot_be_bypassed(self):
        self.pair();self.write('.ai/.env','SECRET=private')
        report=self.propose()
        self.assertFalse(report['ok']);self.assertIn('inspector-incomplete-proposal-refused',self.codes(report))
        self.assertFalse(report['mapping_attempted'])

    def test_missing_or_modified_inspection_reauthenticated(self):
        self.pair();inspection=CompatibilityInspector().inspect(self.root)
        self.assert_valid(self.propose(inspection))
        tampered=deepcopy(inspection);tampered['blockers']=[]
        report=self.propose(tampered)
        self.assertFalse(report['ok']);self.assertIn('inspection-stale-or-modified',self.codes(report))
        self.write('.ai/extra.md','changed')
        self.assertFalse(self.propose(inspection)['ok'])

    def test_transaction_state_refuses_projection(self):
        self.pair();self.write('.ai/state/population/journal.json','{}')
        report=self.propose()
        self.assertFalse(report['ok']);self.assertIn('transaction-state-proposal-refused',self.codes(report))

    def test_source_change_after_mapping_discards_proposals(self):
        self.pair()
        with patch('compatibility_adapter._checkpoint',side_effect=lambda:self.write('.ai/new.md','new')):
            report=self.propose()
        self.assertFalse(report['ok']);self.assertEqual(report['records']['claims'],[])
        self.assertFalse(report['validation']['proposal_usable'])
        self.assertEqual(report['metrics']['candidates_passing_isolated_structural_validation'],0)

    def test_no_staging_inside_inspected_repository(self):
        self.pair();before=self.snapshot()
        with patch('compatibility_adapter.tempfile.tempdir',str(self.root)):
            report=self.propose()
        self.assertFalse(report['ok']);self.assertIn('no-safe-external-validation-staging',self.codes(report))
        self.assertEqual(before,self.snapshot())

    def test_determinism_across_copies_and_formatting_changes(self):
        self.pair();first=self.propose();self.assertEqual(first,self.propose())
        with tempfile.TemporaryDirectory() as other:
            shutil.copytree(self.root/'.ai',Path(other)/'.ai')
            self.assertEqual(first,self.tool.propose(Path(other)))
        path=self.root/'.ai/knowledge/claims/a.json';path.write_text(json.dumps(json.loads(path.read_text()),indent=4))
        second=self.propose()
        self.assertEqual(first['records'],second['records'])
        self.assertEqual([m['proposed_id'] for m in first['id_mappings']],[m['proposed_id'] for m in second['id_mappings']])
        a=next(m for m in first['id_mappings'] if m['record_type']=='claims')
        b=next(m for m in second['id_mappings'] if m['record_type']=='claims')
        self.assertNotEqual(a['source_content_hash'],b['source_content_hash'])

    def test_unrelated_valid_component_survives_blocked_record(self):
        self.pair();self.write('.ai/knowledge/claims/blocked.json',{'id':'missing','kind':'business-policy','state':'approved'})
        report=self.propose();self.assert_valid(report)
        self.assertEqual(report['metrics']['blocked_records'],1)

    def test_validator_dependency_cycle_blocks_dataset_not_silently_trimmed(self):
        claim,evidence=self.pair();claim['depends_on']=['RULE/1'];self.seed(claim,evidence)
        report=self.propose()
        self.assertFalse(report['validation']['attempted_reference_closed_dataset']['ok'])
        self.assertEqual(report['records']['claims'],[])

    def test_no_target_writes_network_or_executable_tools(self):
        self.pair();before=self.snapshot();real_write=Path.write_text;real_bytes=Path.write_bytes
        def outside(path,*args,**kwargs):
            self.assertFalse(path.resolve().is_relative_to(self.root))
            return real_write(path,*args,**kwargs)
        def outside_bytes(path,*args,**kwargs):
            self.assertFalse(path.resolve().is_relative_to(self.root))
            return real_bytes(path,*args,**kwargs)
        with patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('tool execution')), \
             patch.object(os,'system',side_effect=AssertionError('execution')), \
             patch.object(Path,'write_text',outside),patch.object(Path,'write_bytes',outside_bytes):
            report=self.propose();self.assertTrue(report['ok'])
        self.assertEqual(before,self.snapshot())

    def test_source_hash_is_not_fabricated_from_record_hash(self):
        self.pair(); report=self.propose(); self.assert_valid(report)
        self.assertNotIn('content_hash',report['records']['evidence'][0])
        claim,evidence=self.pair();evidence['content_hash']='sha256:'+'a'*64;self.seed(claim,evidence)
        report=self.propose();self.assert_valid(report)
        self.assertEqual(report['records']['evidence'][0]['content_hash'],'sha256:'+'a'*64)

    def test_unsupported_format_is_blocked_record_not_parsed(self):
        self.pair();self.write('.ai/knowledge/claims/legacy.yaml','!!python/object/apply:os.system ["bad"]')
        report=self.propose();self.assert_valid(report)
        self.assertEqual(report['metrics']['legacy_records_inspected'],3)
        self.assertIn('unsupported-or-malformed-record-format',self.codes(report))

    def test_unsafe_link_cannot_bypass_inspector(self):
        self.pair()
        try:
            (self.root/'.ai/link').symlink_to(self.root/'outside')
        except OSError:
            self.skipTest('symlinks unavailable')
        report=self.propose()
        self.assertFalse(report['ok']);self.assertFalse(report['mapping_attempted'])

    def test_global_validation_failure_does_not_return_unvalidated_empty_success_count(self):
        claim,evidence=self.pair('CONFIRMED');claim['last_verified']='2026-01-01';self.seed(claim,evidence)
        report=self.propose()
        self.assertFalse(report['validation']['attempted_reference_closed_dataset']['ok'])
        self.assertTrue(report['validation']['proposed_dataset']['ok'])
        self.assertFalse(report['nonempty_candidates_validated'])
        self.assertEqual(report['metrics']['blocked_records'],2)

    def test_cli_json_summary_options_and_installed_command(self):
        self.pair();before=self.snapshot()
        run=subprocess.run([sys.executable,'-B',str(CLI),'adapt-compatibility','--root',str(self.root),'--json'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout),self.propose())
        self.assertEqual(before,self.snapshot())
        summary=subprocess.run([sys.executable,'-B',str(CLI),'adapt-compatibility','--root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(summary.returncode,0,summary.stderr)
        self.assertIn('not approved',summary.stdout)
        for options in [['--write-generated'],['--approve','yes'],['--dry-run'],['--exclude','x']]:
            result=subprocess.run([sys.executable,'-B',str(CLI),'adapt-compatibility',*options],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(kb.init(Path(other)/'.ai'),[])
            run=subprocess.run([sys.executable,'-B',str(Path(other)/'.ai/tools/kb.py'),'adapt-compatibility',
                '--root',str(self.root),'--json'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)


if __name__=='__main__':
    unittest.main()
