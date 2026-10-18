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
from population_scan import RepositoryScanner, Scanner

CLI = Path(__file__).resolve().parents[1] / 'kb.py'


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scanner: Scanner = RepositoryScanner()

    def write(self, name, content='synthetic'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def scan(self, exclusions=()):
        return self.scanner.scan(self.root, exclusions)

    def cli(self, *args, expected=0, cli=CLI):
        run = subprocess.run([sys.executable, '-B', str(cli), *args,
                              '--root', str(self.root), '--json'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
        return json.loads(run.stdout)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def link(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest('symbolic link creation unavailable or not permitted')

    def test_single_project(self):
        self.write('App.sln')
        self.write('src/App.csproj')
        result = self.scan()
        self.assertTrue(result['ok'])
        self.assertEqual(result['sources'], [
            {'path': 'App.sln', 'kind': 'dotnet-solution'},
            {'path': 'src/App.csproj', 'kind': 'dotnet-project'}])

    def test_multi_project_and_slnx(self):
        for name in ['App.slnx', 'src/A/A.csproj', 'src/B/B.CSPROJ']:
            self.write(name)
        self.assertEqual(self.scan()['counts']['sources'], 3)
        self.assertEqual(self.scan()['sources'][0]['kind'], 'dotnet-solution-xml')

    def test_defaults_prune_directories(self):
        for directory in ['.git', '.ai', 'bin', 'obj', 'generated', 'node_modules',
                          'packages', '.local', '.cache', '.venv', 'TestResults']:
            self.write(directory + '/nested/hidden.csproj')
        result = self.scan()
        self.assertEqual(result['sources'], [])
        self.assertEqual(len(result['skipped']), 11)
        self.assertTrue(all(r['reason'] == 'excluded' for r in result['skipped']))

    def test_secret_and_generated_names(self):
        for name in ['.env', '.env.local', 'cert.pem', 'private.key', 'secrets/a.csproj',
                     'X.generated.csproj', 'X.g.cs', '.aws/credentials']:
            self.write(name, 'PRIVATE_VALUE_NOT_FOR_OUTPUT')
        report = self.scan()
        self.assertFalse(report['sources'])
        self.assertNotIn('PRIVATE_VALUE_NOT_FOR_OUTPUT', json.dumps(report))
        self.assertTrue(all(r['reason'] == 'excluded' for r in report['skipped']))

    def test_custom_exclusions_are_additive(self):
        for name in ['src/Keep.csproj', 'vendor/X.csproj', 'src/Skip.csproj', 'bin/X.csproj']:
            self.write(name)
        result = self.scan(['vendor/', 'src/Skip.*'])
        self.assertEqual([x['path'] for x in result['sources']], ['src/Keep.csproj'])

    def test_invalid_exclusions(self):
        for pattern in ['', '../outside', '/absolute', 'C:/outside', 'a\\b', 'a\nb']:
            with self.subTest(pattern=pattern):
                self.assertFalse(self.scan([pattern])['ok'])

    def test_links_are_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside)
            (external / 'Secret.csproj').write_text('DO_NOT_READ')
            self.write('real/Inside.csproj')
            self.link(self.root / 'escape', external, True)
            self.link(self.root / 'internal', self.root / 'real', True)
            self.link(self.root / 'loop', self.root, True)
            self.link(self.root / 'broken.csproj', external / 'missing')
            self.link(self.root / 'linked.csproj', external / 'Secret.csproj')
            result = self.scan()
            self.assertEqual([r['path'] for r in result['sources']], ['real/Inside.csproj'])
            self.assertEqual(len(result['skipped']), 5)
            self.assertTrue(all(r['reason'] == 'link-not-followed' for r in result['skipped']))

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'named pipes require os.mkfifo (Unix)')
    def test_special_files(self):
        os.mkfifo(self.root / 'pipe.csproj')
        self.assertEqual(self.scan()['skipped'], [
            {'path': 'pipe.csproj', 'reason': 'special-file'}])

    def test_unsupported_and_malformed_discovery_only(self):
        self.write('bad.csproj', '<not valid xml')
        self.write('source.cs', 'not C#')
        result = self.scan()
        self.assertTrue(result['ok'])
        self.assertEqual(result['sources'][0]['path'], 'bad.csproj')
        self.assertEqual(result['skipped'][0]['reason'], 'unsupported-source-type')
        self.assertIn('no contents parsed', result['warnings'][0])

    def test_determinism_and_traversal_order(self):
        for name in ['z/Z.csproj', 'a/A.csproj', 'M.sln', 'other.txt']:
            self.write(name)
        first = self.scan()
        self.assertEqual(first, self.scan())
        files = self.snapshot()
        for name in files:
            (self.root / name).unlink()
        for name, data in reversed(list(files.items())):
            (self.root / name).write_bytes(data)
        self.assertEqual(first, self.scan())
        self.assertNotIn(str(self.root), json.dumps(first))

    def test_modified_and_removed_files(self):
        path = self.write('App.csproj', '<Project/>')
        before = self.scan()
        path.write_text('completely different contents')
        self.assertEqual(before, self.scan())  # Inventory is not a content fingerprint.
        path.unlink()
        self.assertFalse(self.scan()['sources'])

    def test_read_only_offline_no_scripts(self):
        self.cli('init')
        self.write('App.csproj', '<Project/>')
        self.write('danger.sh', 'exit 99')
        before = self.snapshot()
        def denied(*args, **kwargs):
            raise AssertionError('content read, execution or network attempted')
        with patch.object(Path, 'open', denied), patch.object(socket, 'socket', denied), \
                patch.object(socket, 'getaddrinfo', denied), \
                patch.object(subprocess, 'Popen', denied), patch.object(os, 'system', denied):
            result = self.scan()
        self.assertTrue(result['ok'])
        self.cli('scan')
        self.assertEqual(before, self.snapshot())

    def test_unreadable_directory_fails_without_leaking_paths(self):
        original = os.scandir
        self.write('denied/A.csproj')
        def scandir(path):
            if Path(path).name == 'denied':
                raise PermissionError('sensitive absolute path')
            return original(path)
        with patch('population_scan.os.scandir', scandir):
            result = self.scan()
        self.assertFalse(result['ok'])
        self.assertEqual(result['errors'], [
            {'path': 'denied', 'reason': 'directory-unreadable'}])

    def test_invalid_roots(self):
        self.assertFalse(self.scanner.scan(self.root / 'missing')['ok'])
        path = self.write('file')
        self.assertFalse(self.scanner.scan(path)['ok'])
        link = self.root / 'rootlink'
        self.link(link, self.root, True)
        self.assertFalse(self.scanner.scan(link)['ok'])

    def test_cli_and_installed_portability(self):
        self.write('App.csproj')
        self.write('vendor/Other.csproj')
        result = self.cli('scan', '--exclude', 'vendor')
        self.assertEqual([r['path'] for r in result['sources']], ['App.csproj'])
        self.cli('scan', '--exclude', '../invalid', expected=1)
        self.cli('init')
        installed = self.root / '.ai/tools/kb.py'
        result = self.cli('scan', '--exclude', 'vendor')
        self.assertEqual(result, self.cli('scan', '--exclude', 'vendor', cli=installed))


if __name__ == '__main__':
    unittest.main()
