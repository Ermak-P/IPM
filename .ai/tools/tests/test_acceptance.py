import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / 'kb.py'


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=CLI.parent / 'tests')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, command, expected=0):
        result = subprocess.run(
            [sys.executable, '-B', str(CLI), command, '--root', str(self.root), '--json'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def snapshot(self, root=None):
        root = root or self.root
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def write(self, path, value):
        target = self.root / '.ai' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding='utf-8')

    def seed(self, claim_type='technical_fact', evidence_type='direct-technical'):
        self.run_cli('init')
        claim = dict(id='claim.one', statement='Synthetic assertion.', type=claim_type,
                     status='CONFIRMED', evidence=['evidence.one'],
                     provenance={'actor': 'test', 'method': 'manual review'},
                     last_verified='2000-01-01', depends_on=[], conflicts_with=[])
        evidence = dict(id='evidence.one', type=evidence_type, status='active',
                        source='synthetic-source', provenance={'actor': 'test', 'method': 'inspection'},
                        captured_at='2000-01-01T00:00:00Z', description='Synthetic example only.',
                        location='section 1', substantiates=['claim.one'])
        self.write('knowledge/claims/one.json', claim)
        self.write('evidence/one.json', evidence)
        return claim, evidence

    def test_01_complete_scaffold(self):
        self.run_cli('init')
        self.run_cli('check-scaffold')

    def test_02_repeat_init_preserves_bytes(self):
        self.run_cli('init')
        before = self.snapshot()
        self.run_cli('init')
        self.assertEqual(before, self.snapshot())

    def test_03_preserve_existing_ai(self):
        self.write('user.txt', {'private': 'keep'})
        before = self.snapshot()
        self.run_cli('init', 1)
        self.assertEqual(before, self.snapshot())

    def test_04_scope(self):
        (self.root / 'host.txt').write_bytes(b'host\x00data')
        self.run_cli('init')
        self.assertEqual((self.root / 'host.txt').read_bytes(), b'host\x00data')
        self.assertEqual({path.parts[0] for path in map(Path, self.snapshot())}, {'.ai', 'host.txt'})

    def test_05_host_settings(self):
        paths = ['host.sln', 'src/app.csproj', '.editorconfig', '.github/workflows/ci.yml',
                 '.vscode/settings.json', 'AGENTS.md']
        for path in paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'original\r\n')
        before = self.snapshot()
        self.run_cli('init')
        self.assertEqual(before, {key: value for key, value in self.snapshot().items()
                                  if not key.startswith('.ai')})

    def test_06_no_host_dependencies(self):
        for name in ['package.json', 'pyproject.toml', 'go.mod', 'pom.xml']:
            (self.root / name).write_text('original', encoding='utf-8')
        before = self.snapshot()
        self.run_cli('init')
        self.assertTrue(all(self.snapshot()[key] == value for key, value in before.items()))

    def test_07_schemas_and_examples(self):
        self.run_cli('init')
        self.run_cli('validate')
        for name, destination in [('claim', 'knowledge/claims'), ('evidence', 'evidence'),
                                  ('relationship', 'knowledge/relationships')]:
            example = json.loads((CLI.parent / 'examples' / (name + '.json')).read_text())
            self.write(destination + '/example.json', example)
        basis = json.loads((CLI.parent / 'examples/basis.json').read_text())
        self.write('knowledge/claims/basis.json', basis)
        self.run_cli('validate')

    def test_08_duplicates_and_missing_references(self):
        claim, evidence = self.seed()
        self.write('knowledge/claims/duplicate.json', claim)
        self.run_cli('validate', 1)
        (self.root / '.ai/knowledge/claims/duplicate.json').unlink()
        claim['depends_on'] = ['missing']
        self.write('knowledge/claims/one.json', claim)
        self.run_cli('validate', 1)

    def test_09_confirmed_requires_evidence(self):
        claim, evidence = self.seed()
        claim['evidence'] = []
        self.write('knowledge/claims/one.json', claim)
        self.run_cli('validate', 1)

    def test_10_business_requires_authority(self):
        self.seed('business_rule')
        self.run_cli('validate', 1)
        self.write('evidence/one.json', dict(id='evidence.one', type='direct-authoritative',
                   status='active', source='approved requirement',
                   provenance={'actor': 'owner', 'method': 'approval'},
                   captured_at='2000-01-01T00:00:00Z', description='Approved rule.',
                   location='rule 1', substantiates=['claim.one']))
        self.run_cli('validate')

    def test_11_indirect_evidence(self):
        for kind in ['supporting', 'derived']:
            with self.subTest(kind=kind):
                self.seed(evidence_type=kind)
                self.run_cli('validate', 1)

    def test_12_generated_disposable(self):
        self.seed()
        before = self.snapshot(self.root / '.ai/knowledge')
        (self.root / '.ai/generated/.gitkeep').unlink()
        (self.root / '.ai/generated').rmdir()
        self.run_cli('validate')
        self.run_cli('init')
        self.assertEqual(before, self.snapshot(self.root / '.ai/knowledge'))

    def test_13_state_is_not_knowledge(self):
        self.seed()
        before = self.snapshot(self.root / '.ai/knowledge')
        self.write('state/run.json', {'timestamp': '2000-01-01'})
        self.run_cli('validate')
        self.assertEqual(before, self.snapshot(self.root / '.ai/knowledge'))

    def test_14_language_independent(self):
        for filename in ['app.py', 'main.go', 'main.rs', 'index.js']:
            (self.root / filename).write_text('synthetic', encoding='utf-8')
        self.run_cli('init')
        self.run_cli('validate')

    def test_15_deterministic(self):
        claim, evidence = self.seed()
        claim['depends_on'] = ['missing']
        self.write('knowledge/claims/one.json', claim)
        first = self.run_cli('validate', 1)
        claim_path = self.root / '.ai/knowledge/claims/one.json'
        evidence_path = self.root / '.ai/evidence/one.json'
        claim_path.unlink()
        evidence_path.unlink()
        self.write('evidence/one.json', evidence)
        self.write('knowledge/claims/one.json', claim)
        self.assertEqual(first, self.run_cli('validate', 1))

    def test_16_inactive_evidence(self):
        claim, evidence = self.seed()
        for status in ['retracted', 'superseded']:
            evidence['status'] = status
            self.write('evidence/one.json', evidence)
            self.run_cli('validate', 1)

    def test_17_one_sufficient_active_evidence(self):
        claim, evidence = self.seed()
        evidence.update(id='evidence.old', status='retracted')
        self.write('evidence/old.json', evidence)
        claim['evidence'].append('evidence.old')
        self.write('knowledge/claims/one.json', claim)
        self.run_cli('validate')

    def test_18_conflicts(self):
        claim, evidence = self.seed()
        for reference in ['missing', 'claim.one', 'claim.two']:
            claim['conflicts_with'] = [reference]
            self.write('knowledge/claims/one.json', claim)
            self.run_cli('validate', 1)
        other = dict(claim, id='claim.two', status='UNKNOWN', evidence=[], conflicts_with=['claim.one'])
        self.write('knowledge/claims/two.json', other)
        self.run_cli('validate')

    def test_19_age_does_not_downgrade(self):
        self.seed()
        before = self.snapshot()
        self.run_cli('validate')
        self.assertEqual(before, self.snapshot())

    def test_20_unknown_version(self):
        self.run_cli('init')
        path = self.root / '.ai/manifest.yaml'
        value = json.loads(path.read_text())
        value['format_version'] = '99.0.0'
        path.write_text(json.dumps(value), encoding='utf-8')
        self.run_cli('validate', 1)
        self.run_cli('init', 1)

    def test_21_structure_dates_and_enums(self):
        claim, evidence = self.seed()
        for field, value in [('type', 'invalid'), ('status', 'invalid'),
                             ('last_verified', '2026-02-30'), ('statement', ' '),
                             ('provenance', {}), ('evidence', 'evidence.one')]:
            with self.subTest(field=field):
                self.write('knowledge/claims/one.json', dict(claim, **{field: value}))
                self.run_cli('validate', 1)
        del claim['statement']
        self.write('knowledge/claims/one.json', claim)
        self.run_cli('validate', 1)

    def test_22_schema_changes_rejected(self):
        self.run_cli('init')
        path = self.root / '.ai/schema/claim.schema.json'
        schema = json.loads(path.read_text())
        schema['required'] = []
        path.write_text(json.dumps(schema), encoding='utf-8')
        self.run_cli('validate', 1)

    def test_23_cycles(self):
        claim, evidence = self.seed()
        claim.update(status='UNKNOWN', evidence=[], depends_on=['claim.two'])
        self.write('knowledge/claims/one.json', claim)
        self.write('knowledge/claims/two.json', dict(claim, id='claim.two', depends_on=['claim.one']))
        self.run_cli('validate', 1)

    def test_24_evidence_must_link_specific_claim(self):
        claim, evidence = self.seed()
        for change in [{'substantiates': []}, {'location': ''},
                       {'captured_at': '2026-02-30T00:00:00Z'}]:
            self.write('evidence/one.json', dict(evidence, **change))
            self.run_cli('validate', 1)

    def test_25_malformed_relationships(self):
        self.seed()
        relation = dict(id='relation.one', type='depends_on', **{'from': 'claim.one'},
                        to='missing', provenance={'actor': 'test', 'method': 'manual'})
        self.write('knowledge/relationships/one.json', relation)
        self.run_cli('validate', 1)
        relation['to'] = 'claim.one'
        self.write('knowledge/relationships/one.json', relation)
        self.run_cli('validate', 1)

    def test_26_existing_scaffold_edits_preserved(self):
        self.run_cli('init')
        (self.root / '.ai/README.md').write_bytes(b'user documentation')
        before = self.snapshot()
        self.run_cli('init', 1)
        self.assertEqual(before, self.snapshot())

    def test_27_installed_cli_is_portable(self):
        self.run_cli('init')
        installed = self.root / '.ai/tools/kb.py'
        result = subprocess.run([sys.executable, '-B', str(installed), 'validate',
                                 '--root', str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_28_duplicate_json_keys(self):
        self.run_cli('init')
        (self.root / '.ai/knowledge/claims/bad.json').write_text('{"id":"one","id":"two"}')
        self.run_cli('validate', 1)


if __name__ == '__main__':
    unittest.main()
