"""Clean distribution acceptance; never deploy over an existing real .ai."""
import ast
import hashlib
import io
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
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb
import deployment_package as package

REPO = Path(__file__).resolve().parents[3]


def snapshot(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def expand(data, target):
    assert not (target / '.ai').exists(), 'Never extract over legacy .ai'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert all(n.startswith('.ai/') and '..' not in n.split('/') and '\\' not in n for n in archive.namelist())
        archive.extractall(target)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cli(self, root, *args, expected=0):
        result = subprocess.run([sys.executable, '-B', str(root/'.ai/tools/kb.py'), *args,
            '--root', str(root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_archive_determinism_and_zero_knowledge_samples_state(self):
        first, audit=package.build(REPO);second,other=package.build(REPO)
        self.assertEqual(first,second)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            names=archive.namelist()
            self.assertEqual(names,sorted(names));self.assertEqual(len(names),len(set(names)))
            self.assertFalse(any('existing-knowledge' in n for n in names))
            self.assertFalse(any(n.endswith('.json') for n in names if n.startswith(('.ai/knowledge/','.ai/evidence/','.ai/sources/'))))
            for prefix in ['.ai/state/','.ai/generated/','.ai/tools/examples/','.ai/tools/tests/']:
                self.assertFalse(any(n.startswith(prefix) and n not in [prefix,prefix+'.gitkeep'] for n in names))
            self.assertTrue(all(info.date_time==(1980,1,1,0,0,0) for info in archive.infolist()))
            profile=json.loads(archive.read('.ai/deployment-profile.json'))
            for item in profile['included_files']:
                self.assertEqual(hashlib.sha256(archive.read(item['path'])).hexdigest(),item['sha256'])
            self.assertTrue(profile['empty_canonical_store'])
            self.assertNotIn(b'## Harbor example and regression',archive.read('.ai/docs/compatibility-inspector.md'))
            self.assertNotIn(b'### Original Harbor Tickets result',archive.read('.ai/docs/compatibility-adapter.md'))
            self.assertNotIn(b'## Executed verification and changed files',archive.read('.ai/docs/compatibility-adapter.md'))
        self.assertEqual(set(package.CATEGORIES),{r['category'] for r in audit['inventory']})

    def test_registry_only_change_canonical_contract_and_function_bodies_identical(self):
        data,audit=package.build(REPO)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            original=(REPO/'.ai/tools/kb.py').read_text();clean=archive.read('.ai/tools/kb.py').decode()
            def nodes(text):
                return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
            self.assertEqual(nodes(original),nodes(clean))
            for name in ['manifest.yaml','schema/claim.schema.json','schema/evidence.schema.json','schema/relationship.schema.json']:
                self.assertEqual(archive.read('.ai/'+name),(REPO/'.ai'/name).read_bytes())
            for name in package.TOOLS[1:]:
                self.assertEqual(archive.read('.ai/tools/'+name),(REPO/'.ai/tools'/name).read_bytes())

    def test_complete_clean_deployment_and_all_cli_runtime_commands(self):
        data,_=package.build(REPO)
        # An existing .NET host and its independently owned legacy knowledge.
        original=self.root/'original';original.mkdir()
        for name in ['SyntheticIpm.sln','Directory.Build.props','Directory.Packages.props','NuGet.Config']:
            if (REPO/name).is_file():shutil.copyfile(REPO/name,original/name)
        for directory in ['src','tests']:
            shutil.copytree(REPO/directory,original/directory,
                ignore=shutil.ignore_patterns('bin','obj','TestResults'))
        bundle=json.loads((REPO/'.ai/tools/examples/existing-knowledge/fixture.json').read_text())
        for name,content in bundle['files'].items():
            if not name.startswith('.ai/'):continue
            p=original/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')
        original_before=snapshot(original)
        review=self.root/'legacy-review';review.mkdir();shutil.copytree(original/'.ai',review/'.ai')
        for file in (review/'.ai').rglob('*'):
            if file.is_file():file.chmod(0o444)
        def release_fixture_flags():
            if review.exists():
                for file in (review/'.ai').rglob('*'):
                    if file.is_file():file.chmod(0o644)
        self.addCleanup(release_fixture_flags)
        review_before=snapshot(review)
        target=self.root/'clean-evaluation';shutil.copytree(original,target,ignore=shutil.ignore_patterns('.ai'))
        host_before=snapshot(target)
        expand(data,target)
        clean_before=snapshot(target/'.ai')
        for area in ['knowledge','evidence','sources','state','generated']:
            files=[p.relative_to(target/'.ai'/area).as_posix() for p in (target/'.ai'/area).rglob('*') if p.is_file()]
            self.assertTrue(all(n.endswith('.gitkeep') for n in files),files)
        self.assertEqual(self.cli(target,'validate')['ok'],True)
        self.assertEqual(self.cli(target,'check-scaffold')['ok'],True)
        self.assertEqual(self.cli(target,'version')['cli_version'],'1.0.0')
        self.assertEqual(self.cli(target,'populate','status')['transactions'],[])
        empty=self.cli(target,'build','--view','canonical')['graph']
        self.assertEqual(empty['nodes'],[]);self.assertEqual(empty['edges'],[])
        scan=self.cli(target,'scan');self.assertEqual(len(scan['sources']),7)
        extraction=self.cli(target,'extract');self.assertEqual(len(extraction['candidates']),29)
        proposals=self.cli(target,'normalize');self.assertEqual(proposals['counts']['claims'],29)
        preview=self.cli(target,'build','--view','technical-preview')['graph']
        self.assertEqual(sum(n['kind']=='observed_project' for n in preview['nodes']),6)
        report=self.cli(target,'report');self.assertEqual(report['canonical']['claims']['total'],0)
        inspected=self.cli(target,'inspect-compatibility');self.assertTrue(inspected['complete'])
        adapted=self.cli(target,'adapt-compatibility');self.assertTrue(adapted['ok'])
        self.assertEqual(adapted['metrics']['legacy_records_inspected'],0)
        self.cli(target,'init')  # Runtime init remains clean and idempotent.
        # Trusted new CLI can inspect the separately preserved legacy root without adoption.
        result=subprocess.run([sys.executable,'-B',str(target/'.ai/tools/kb.py'),'inspect-compatibility',
            '--root',str(review),'--json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['manifest']['classification'],'foreign-json-declaration')
        self.assertEqual(original_before,snapshot(original));self.assertEqual(review_before,snapshot(review))
        self.assertEqual(host_before,{k:v for k,v in snapshot(target).items() if not k.startswith('.ai/')})
        self.assertFalse((target/'.ai/state/population').exists())
        self.assertEqual(self.cli(target,'validate')['ok'],True)
        self.assertEqual(clean_before,snapshot(target/'.ai'))

    def test_runtime_init_into_another_empty_root_stays_clean(self):
        data,_=package.build(REPO);seed=self.root/'seed';seed.mkdir();expand(data,seed)
        destination=self.root/'new';destination.mkdir()
        run=subprocess.run([sys.executable,'-B',str(seed/'.ai/tools/kb.py'),'init','--root',str(destination),'--json'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.cli(destination,'check-scaffold')
        self.assertFalse((destination/'.ai/tools/examples/claim.json').exists())
        self.assertFalse((destination/'.ai/tools/examples/existing-knowledge').exists())
        self.assertFalse((destination/'.ai/state/population').exists())

    def test_preserved_legacy_is_not_an_extract_target(self):
        data,_=package.build(REPO)
        legacy=self.root/'legacy';(legacy/'.ai').mkdir(parents=True)
        (legacy/'.ai/README.md').write_text('Do not overwrite')
        before=snapshot(legacy)
        with self.assertRaises(AssertionError):expand(data,legacy)
        seed=self.root/'trusted-runtime';seed.mkdir();expand(data,seed)
        result=subprocess.run([sys.executable,'-B',str(seed/'.ai/tools/kb.py'),'init',
            '--root',str(legacy),'--json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertEqual(before,snapshot(legacy))

    def test_inventory_covers_every_current_file_without_copying_runtime_contents(self):
        data,audit=package.build(REPO)
        expected={'.ai/'+p.relative_to(REPO/'.ai').as_posix() for p in (REPO/'.ai').rglob('*') if p.is_file()}
        self.assertEqual(expected,{r['path'] for r in audit['inventory']})
        for item in audit['inventory']:
            if item['category'] in [package.CATEGORIES[3],package.CATEGORIES[4],package.CATEGORIES[5]]:
                self.assertIsNone(item['included_as'])
            self.assertTrue(item['original_preserved'])

    def test_no_network_execution_or_source_mutation_during_build(self):
        with patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('execution')), \
             patch.object(os,'system',side_effect=AssertionError('execution')), \
             patch.object(Path,'write_bytes',side_effect=AssertionError('source write')), \
             patch.object(Path,'write_text',side_effect=AssertionError('source write')):
            data,_=package.build(REPO)
        self.assertTrue(data)

    def test_output_collision_and_identical_retry(self):
        output=self.root/'package.zip'
        package.write_new_or_identical(output,b'first')
        package.write_new_or_identical(output,b'first')
        with self.assertRaises(ValueError):package.write_new_or_identical(output,b'other')
        self.assertEqual(output.read_bytes(),b'first')

    def test_registry_transform_rejects_intervening_code(self):
        text=(REPO/'.ai/tools/kb.py').read_text().replace("FILES += ['.gitignore']","print('unexpected')\nFILES += ['.gitignore']")
        with self.assertRaises(ValueError):package.runtime_cli(text)

    def test_source_symlink_rejected_and_development_data_retained(self):
        with self.assertRaises(ValueError):package.category('unowned-secret.dat')
        original=self.root/'data';original.write_bytes(b'keep')
        link=self.root/'link'
        try:link.symlink_to(original)
        except OSError:self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):package.checked_file(link)
        self.assertEqual(original.read_bytes(),b'keep')


if __name__=='__main__':
    unittest.main()
