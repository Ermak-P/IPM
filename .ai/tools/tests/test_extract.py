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
from population_dotnet import DotNetAnalyzer, MAX_BYTES, MAX_DEPTH, MAX_NODES
from population_scan import RepositoryScanner

CLI = Path(__file__).resolve().parents[1] / 'kb.py'
TYPE_ID = '{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}'
PROJECT_ID = '{5751E520-961D-4769-AF60-D7BB815D412A}'
HEADER = 'Microsoft Visual Studio Solution File, Format Version 12.00\n'


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.analyzer = DotNetAnalyzer()

    def write(self, name, content='<Project/>'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))
        return path

    def scan(self, exclusions=()):
        return RepositoryScanner().scan(self.root, exclusions)

    def extract(self, inventory=None):
        return self.analyzer.extract(self.root, inventory if inventory is not None else self.scan())

    def facts(self, result, kind):
        return [c for c in result['candidates'] if c['kind'] == kind]

    def codes(self, result):
        return {d['code'] for d in result['diagnostics']}

    def cli(self, *args, expected=0, cli=CLI):
        run = subprocess.run([sys.executable, '-B', str(cli), *args,
                              '--root', str(self.root), '--json'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
        return json.loads(run.stdout)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def link(self, path, target):
        try:
            path.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError):
            self.skipTest('symbolic link creation unavailable or not permitted')

    def test_single_project_properties_and_evidence(self):
        self.write('App.csproj', '<Project>\n<PropertyGroup><ProjectName>Declared</ProjectName>'
                   '<AssemblyName>Binary</AssemblyName><ProjectGuid>' + PROJECT_ID +
                   '</ProjectGuid><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        report = self.extract()
        self.assertTrue(report['ok'])
        project = self.facts(report, 'project')[0]
        self.assertEqual(project['value'], {'path': 'App.csproj', 'name': 'App',
                                           'name_origin': 'filename'})
        properties = {c['value']['name']: c for c in self.facts(report, 'project_property')}
        self.assertEqual(properties['ProjectName']['value']['declared'], 'Declared')
        self.assertEqual(properties['TargetFramework']['value']['declared'], 'net10.0')
        evidence = properties['TargetFramework']['evidence'][0]
        self.assertEqual(evidence['source'], 'App.csproj')
        self.assertEqual(evidence['location']['line'], 2)
        self.assertIn('/TargetFramework[1]', evidence['location']['selector'])
        self.assertEqual(evidence['provenance']['method'], 'static-xml-declaration-v1')
        self.assertTrue(evidence['content_hash'].startswith('sha256:'))
        self.assertNotIn('CONFIRMED', json.dumps(report))

    def test_multiple_frameworks_and_legacy_namespace(self):
        self.write('App.csproj', '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
                   '<PropertyGroup><TargetFrameworks>net9.0;net10.0</TargetFrameworks>'
                   '</PropertyGroup></Project>')
        report = self.extract()
        self.assertTrue(report['ok'])
        self.assertEqual(self.facts(report, 'project_property')[0]['value'],
                         {'name': 'TargetFrameworks', 'declared': 'net9.0;net10.0'})

    def test_multi_project_direct_not_transitive(self):
        self.write('src/A.csproj', '<Project><ItemGroup><ProjectReference Include="B.csproj"/>'
                   '</ItemGroup></Project>')
        self.write('src/B.csproj', '<Project><ItemGroup><ProjectReference Include="C.csproj"/>'
                   '</ItemGroup></Project>')
        self.write('src/C.csproj')
        self.write('App.sln', HEADER +
                   f'Project("{TYPE_ID}") = "A", "src\\A.csproj", "{PROJECT_ID}"\nEndProject\n')
        report = self.extract()
        self.assertTrue(report['ok'])
        edges = {(c['source'], c['value']['target'])
                 for c in self.facts(report, 'project_reference')}
        self.assertEqual(edges, {('src/A.csproj', 'src/B.csproj'),
                                 ('src/B.csproj', 'src/C.csproj')})
        membership = self.facts(report, 'solution_membership')[0]
        self.assertEqual(membership['value']['target'], 'src/A.csproj')
        self.assertEqual(membership['value']['declared_id'], PROJECT_ID)

    def test_slnx_folder_paths_relative_to_solution(self):
        self.write('sub/A.csproj')
        self.write('sub/App.slnx', '<Solution><Folder Name="/src/">'
                   '<Project Path="A.csproj" Id="one"/></Folder></Solution>')
        member = self.facts(self.extract(), 'solution_membership')[0]
        self.assertEqual(member['value']['target'], 'sub/A.csproj')
        self.assertEqual(member['value']['declared_id'], 'one')
        self.assertIn('/Folder[1]/Project[1]', member['evidence'][0]['location']['selector'])

    def test_conditions_preserved_on_groups_items_and_metadata(self):
        self.write('A.csproj', '''<Project Condition="'$(Root)' == 'yes'">
<PropertyGroup Condition="'$(Configuration)' == 'Debug'">
<TargetFramework Condition="'$(OS)' == 'Windows_NT'">net10.0</TargetFramework>
</PropertyGroup><ItemGroup Condition="'$(TargetFramework)' == 'net10.0'">
<ProjectReference Include="B.csproj" Condition="Exists('B.csproj')"/>
<PackageReference Include="NUnit" Condition="'$(Test)' == 'true'">
<Version Condition="'$(Pinned)' == 'true'">4.5.1</Version>
</PackageReference></ItemGroup></Project>''')
        self.write('B.csproj')
        result = self.extract()
        prop = self.facts(result, 'project_property')[0]
        self.assertEqual(prop['conditions'], ["'$(Root)' == 'yes'",
                                             "'$(Configuration)' == 'Debug'",
                                             "'$(OS)' == 'Windows_NT'"])
        version = self.facts(result, 'package_version')[0]
        self.assertEqual(version['conditions'][-2:], ["'$(Test)' == 'true'",
                                                     "'$(Pinned)' == 'true'"])
        self.assertIn("Exists('B.csproj')", self.facts(result, 'project_reference')[0]['conditions'])
        self.assertIn('unresolved-msbuild-expression', self.codes(result))

    def test_packages_versions_attributes_children_override_and_missing(self):
        self.write('App.csproj', '''<Project><ItemGroup>
<PackageReference Include="A" Version="1.0"/>
<PackageReference Include="B"><Version>2.0</Version><VersionOverride>3.0</VersionOverride></PackageReference>
<PackageReference Include="Central"/>
</ItemGroup></Project>''')
        result = self.extract()
        self.assertEqual(len(self.facts(result, 'package_reference')), 3)
        versions = {(c['value']['include'], c['value']['name'], c['value']['declared'])
                    for c in self.facts(result, 'package_version')}
        self.assertEqual(versions, {('A', 'Version', '1.0'), ('B', 'Version', '2.0'),
                                    ('B', 'VersionOverride', '3.0')})
        self.assertIn('package-version-not-declared', self.codes(result))

    def test_duplicate_references_aggregate_occurrence_evidence(self):
        self.write('A.csproj', '<Project><ItemGroup><ProjectReference Include="B.csproj"/>'
                   '<ProjectReference Include="B.csproj"/></ItemGroup></Project>')
        self.write('B.csproj')
        result = self.extract()
        edges = self.facts(result, 'project_reference')
        self.assertEqual(len(edges), 1)
        self.assertEqual(len(edges[0]['evidence']), 2)
        self.assertIn('duplicate-declaration', self.codes(result))

    def test_missing_excluded_projects_never_opened(self):
        self.write('A.csproj', '<Project><ItemGroup><ProjectReference Include="Missing.csproj"/>'
                   '<ProjectReference Include="vendor/Excluded.csproj"/></ItemGroup></Project>')
        self.write('vendor/Excluded.csproj', 'not xml')
        result = self.extract(self.scan(['vendor']))
        self.assertTrue(result['ok'])
        self.assertEqual({c['value']['resolution'] for c in self.facts(result, 'project_reference')},
                         {'not-in-inventory'})
        self.assertNotIn('malformed-xml', self.codes(result))

    def test_msbuild_expressions_never_expanded(self):
        self.write('A.csproj', '''<Project><PropertyGroup>
<TargetFramework>$(Framework)</TargetFramework></PropertyGroup><ItemGroup>
<ProjectReference Include="$(Root)/B.csproj"/><PackageReference Include="X" Version="$(Version)"/>
</ItemGroup></Project>''')
        result = self.extract()
        edge = self.facts(result, 'project_reference')[0]['value']
        self.assertIsNone(edge['target'])
        self.assertEqual(edge['resolution'], 'unresolved-expression')
        self.assertEqual(self.facts(result, 'package_version')[0]['value']['declared'], '$(Version)')
        self.assertIn('unresolved-msbuild-expression', self.codes(result))

    def test_malformed_xml_no_partial_candidates(self):
        self.write('Bad.csproj', '<Project><PropertyGroup><TargetFramework>net10.0</Project>')
        self.write('Good.csproj')
        result = self.extract()
        self.assertFalse(result['ok'])
        self.assertEqual([c['source'] for c in result['candidates']], ['Good.csproj'])
        self.assertIn('malformed-xml', self.codes(result))

    def test_dtd_and_entities_rejected_including_utf16(self):
        inputs = [
            '<!DOCTYPE Project [<!ENTITY x "expanded">]><Project>&x;</Project>',
            '<!DOCTYPE Project SYSTEM "https://example.invalid/project.dtd"><Project/>',
            '<!DOCTYPE Project [<!ENTITY x SYSTEM "file:///etc/passwd">]><Project>&x;</Project>']
        for index, text in enumerate(inputs):
            for encoding in ['utf-8', 'utf-16']:
                with self.subTest(index=index, encoding=encoding):
                    self.write('Bad.csproj', text.encode(encoding))
                    result = self.extract()
                    self.assertFalse(result['ok'])
                    self.assertFalse(result['candidates'])
                    self.assertIn('xml-dtd-or-entity-forbidden', self.codes(result))
        self.write('Bad.csproj', '<Project>&undefined;</Project>')
        self.assertFalse(self.extract()['ok'])

    def test_resource_limits(self):
        self.write('Big.csproj', b' ' * (MAX_BYTES + 1))
        self.assertIn('source-size-limit', self.codes(self.extract()))
        (self.root / 'Big.csproj').unlink()
        self.write('Deep.csproj', '<Project>' + '<X>' * MAX_DEPTH +
                   '</X>' * MAX_DEPTH + '</Project>')
        self.assertIn('xml-resource-limit', self.codes(self.extract()))
        (self.root / 'Deep.csproj').unlink()
        self.write('Nodes.csproj', '<Project>' + '<X/>' * MAX_NODES + '</Project>')
        self.assertIn('xml-resource-limit', self.codes(self.extract()))

    def test_unsupported_constructs_not_guessed(self):
        self.write('A.csproj', '''<Project Sdk="Some.Sdk">
<Import Project="secret.props"/><Choose><When Condition="true">
<ItemGroup><ProjectReference Include="NeverGuessed.csproj"/></ItemGroup></When></Choose>
<Target Name="BeforeBuild"><Exec Command="SHOULD_NOT_RUN"/></Target>
<ItemGroup><ProjectReference Update="B.csproj"/><PackageReference Remove="X"/>
<ProjectReference Include="*.csproj"/><ProjectReference Include="B.csproj;C.csproj"/>
</ItemGroup></Project>''')
        result = self.extract()
        self.assertTrue(result['ok'])
        self.assertIn('unsupported-project-construct', self.codes(result))
        self.assertIn('unsupported-item-operation', self.codes(result))
        self.assertIn('unsupported-reference-path', self.codes(result))
        self.assertEqual(len(self.facts(result, 'project_reference')), 2)
        self.assertNotIn('SHOULD_NOT_RUN', json.dumps(result))

    def test_windows_path_rules_on_every_platform(self):
        self.write('src/A.csproj', r'''<Project><ItemGroup>
<ProjectReference Include="..\lib\B.csproj"/>
<ProjectReference Include="C:\outside\X.csproj"/>
<ProjectReference Include="\\server\share\X.csproj"/>
<ProjectReference Include="..\..\escape.csproj"/>
</ItemGroup></Project>''')
        self.write('lib/B.csproj')
        values = [c['value'] for c in self.facts(self.extract(), 'project_reference')]
        self.assertIn({'include': '..\\lib\\B.csproj', 'target': 'lib/B.csproj',
                       'resolution': 'discovered'}, values)
        self.assertEqual(sum(v['target'] is None for v in values), 3)

    def test_determinism_inventory_order_and_formatting_stable_ids(self):
        path = self.write('A.csproj', '<Project><PropertyGroup><TargetFramework>'
                          'net10.0</TargetFramework></PropertyGroup></Project>')
        self.write('B.csproj')
        first = self.extract()
        self.assertEqual(first, self.extract())
        inventory = self.scan()
        inventory['sources'].reverse()
        reordered = self.extract(inventory)
        self.assertEqual(first['candidates'], reordered['candidates'])
        self.assertEqual(first['diagnostics'], reordered['diagnostics'])
        path.write_text('<Project>\n  <PropertyGroup>\n<TargetFramework> net10.0 </TargetFramework>'
                        '</PropertyGroup></Project>', encoding='utf-8')
        changed = self.extract()
        self.assertEqual({c['id'] for c in first['candidates']},
                         {c['id'] for c in changed['candidates']})
        self.assertNotEqual(first['candidates'], changed['candidates'])  # Evidence changed.

    def test_modified_removed_and_stale_inventory(self):
        path = self.write('App.csproj', '<Project><PropertyGroup><TargetFramework>net9.0'
                          '</TargetFramework></PropertyGroup></Project>')
        before = self.extract()
        inventory = self.scan()
        path.write_text('<Project><PropertyGroup><TargetFramework>net10.0'
                        '</TargetFramework></PropertyGroup></Project>')
        after = self.extract(inventory)
        self.assertNotEqual(self.facts(before, 'project_property')[0]['id'],
                            self.facts(after, 'project_property')[0]['id'])
        path.unlink()
        self.assertFalse(self.extract(inventory)['ok'])
        self.assertFalse(self.extract()['candidates'])

    def test_inventory_injection_invalid_and_excluded_paths(self):
        self.write('Good.csproj')
        for name in ['../escape.csproj', '/outside.csproj', 'C:/outside.csproj', 'a\\b.csproj']:
            inventory = self.scan()
            inventory['sources'][0]['path'] = name
            self.assertFalse(self.extract(inventory)['ok'])
        self.write('.git/Hidden.csproj')
        inventory = self.scan()
        inventory['sources'] = [{'path': '.git/Hidden.csproj', 'kind': 'dotnet-project'}]
        self.assertIn('excluded-inventory-path', self.codes(self.extract(inventory)))
        inventory = self.scan()
        inventory['ok'] = False
        self.assertFalse(self.extract(inventory)['ok'])
        inventory = self.scan()
        inventory['sources'] *= 2
        self.assertFalse(self.extract(inventory)['ok'])
        inventory = self.scan()
        inventory['sources'] = [{'path': 'secret.txt', 'kind': None}]
        self.assertFalse(self.extract(inventory)['ok'])

    def test_symlinks_added_after_scan_not_followed(self):
        path = self.write('App.csproj')
        inventory = self.scan()
        path.unlink()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'Secret.csproj'
            target.write_text('SECRET_CONTENT')
            self.link(path, target)
            result = self.extract(inventory)
        self.assertFalse(result['ok'])
        self.assertIn('linked-source', self.codes(result))
        self.assertNotIn('SECRET_CONTENT', json.dumps(result))

    def test_directory_symlink_added_after_scan(self):
        self.write('src/App.csproj')
        inventory = self.scan()
        (self.root / 'src/App.csproj').unlink()
        (self.root / 'src').rmdir()
        with tempfile.TemporaryDirectory() as outside:
            self.link(self.root / 'src', Path(outside))
            self.assertIn('linked-source', self.codes(self.extract(inventory)))

    def test_offline_no_execution_no_source_copies_and_no_writes(self):
        self.cli('init')
        self.write('A.csproj', '''<Project><PropertyGroup>
<Password>PRIVATE_CONTENT</Password></PropertyGroup>
<Target Name="Build"><Exec Command="NETWORK_OR_EXEC_SHOULD_NOT_RUN"/></Target></Project>''')
        self.write('Directory.Build.props', 'NOT_READ')
        self.write('.env', 'SECRET')
        before = self.snapshot()
        inventory = self.scan()
        def denied(*args, **kwargs):
            raise AssertionError('network or execution attempted')
        with patch.object(socket, 'socket', denied), patch.object(socket, 'getaddrinfo', denied), \
                patch.object(subprocess, 'Popen', denied), patch.object(os, 'system', denied), \
                patch('population_dotnet.os.open', wraps=os.open) as opened:
            result = self.extract(inventory)
        self.assertEqual([call.args[0] for call in opened.call_args_list], [self.root / 'A.csproj'])
        serialized = json.dumps(result)
        for content in ['PRIVATE_CONTENT', 'NETWORK_OR_EXEC_SHOULD_NOT_RUN', 'NOT_READ', 'SECRET']:
            self.assertNotIn(content, serialized)
        self.assertEqual(before, self.snapshot())

    def test_cli_excludes_portability_and_read_only(self):
        self.write('A.csproj')
        self.write('vendor/Bad.csproj', 'invalid')
        self.cli('extract', expected=1)
        self.cli('init')
        before = self.snapshot()
        result = self.cli('extract', '--exclude', 'vendor')
        self.assertEqual(result, self.cli('extract', '--exclude', 'vendor',
                                         cli=self.root / '.ai/tools/kb.py'))
        self.assertEqual(before, self.snapshot())

    def test_sln_encodings_malformed_declarations_and_solution_folders(self):
        self.write('App.csproj')
        folder = '{2150E333-8FDC-42A3-9474-1A3956D46DE8}'
        text = (HEADER + f'Project("{folder}") = "Folder", "Folder", "{PROJECT_ID}"\n'
                f'Project("{TYPE_ID}") = "App", "App.csproj", "{PROJECT_ID}"\n')
        for encoding in ['utf-8-sig', 'utf-16']:
            self.write('App.sln', text.encode(encoding))
            result = self.extract()
            self.assertTrue(result['ok'])
            self.assertEqual(len(self.facts(result, 'solution_membership')), 1)
        self.write('App.sln', HEADER + 'Project("bad") = malformed\n')
        self.assertIn('malformed-solution-project', self.codes(self.extract()))
        self.write('App.sln', 'unrecognized solution format')
        self.assertFalse(self.extract()['ok'])

    def test_slnx_missing_unsupported_and_malformed(self):
        self.write('App.slnx', '<Solution><Project Path="Missing.csproj"/>'
                   '<Project Path="Other.vbproj"/><Project/><Unknown/></Solution>')
        result = self.extract()
        self.assertFalse(result['ok'])
        self.assertIn('reference-not-in-inventory', self.codes(result))
        self.assertIn('unsupported-project-type', self.codes(result))
        self.assertIn('missing-solution-project-path', self.codes(result))
        self.assertIn('unsupported-solution-construct', self.codes(result))
        self.write('App.slnx', '<Solution><Project></Solution>')
        self.assertIn('malformed-xml', self.codes(self.extract()))

    def test_unexpected_roots_and_namespaces(self):
        for value in ['<NotProject/>', '<Project xmlns="https://untrusted.invalid"/>']:
            self.write('App.csproj', value)
            result = self.extract()
            self.assertFalse(result['ok'])
            self.assertFalse(result['candidates'])

    def test_no_inherited_framework_guess(self):
        self.write('App.csproj', '<Project Sdk="Microsoft.NET.Sdk"/>')
        self.write('Directory.Build.props', '<Project><PropertyGroup>'
                   '<TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        result = self.extract()
        self.assertFalse(self.facts(result, 'project_property'))
        self.assertIn('msbuild-imports-and-evaluation-not-performed', self.codes(result))

    def test_reference_id_survives_target_removal(self):
        self.write('A.csproj', '<Project><ItemGroup><ProjectReference Include="B.csproj"/>'
                   '</ItemGroup></Project>')
        target = self.write('B.csproj')
        before = self.facts(self.extract(), 'project_reference')[0]
        target.unlink()
        after = self.facts(self.extract(), 'project_reference')[0]
        self.assertEqual(before['id'], after['id'])
        self.assertEqual(before['value']['resolution'], 'discovered')
        self.assertEqual(after['value']['resolution'], 'not-in-inventory')

    def test_scan_output_preserved_and_inventory_not_mutated(self):
        self.write('A.csproj')
        inventory = self.scan()
        before = json.dumps(inventory, sort_keys=True)
        self.extract(inventory)
        self.assertEqual(before, json.dumps(inventory, sort_keys=True))
        self.assertEqual(before, json.dumps(self.scan(), sort_keys=True))

    def test_attribute_order_does_not_change_ids(self):
        path = self.write('A.csproj', '<Project><ItemGroup>'
                          '<PackageReference Include="NUnit" Version="4.5.1"/>'
                          '</ItemGroup></Project>')
        before = {c['id'] for c in self.extract()['candidates']}
        path.write_text('<Project><ItemGroup>'
                        '<PackageReference Version="4.5.1" Include="NUnit"/>'
                        '</ItemGroup></Project>')
        self.assertEqual(before, {c['id'] for c in self.extract()['candidates']})


if __name__ == '__main__':
    unittest.main()
