"""Read-only discovery boundary. No parsing, project evaluation or content reads."""
from fnmatch import fnmatchcase
import os
from pathlib import Path
import stat
from typing import Iterable, Protocol


# Additive exclusions: callers cannot disable the safety defaults.
DEFAULT_EXCLUSIONS = (
    '.git', '.ai', '.svn', '.hg', '.vs', '.idea', '.vscode',
    'bin', 'obj', 'build', 'dist', 'out', 'target', 'generated',
    'node_modules', 'packages', '.local', '.cache', '__pycache__',
    '.pytest_cache', '.mypy_cache', '.nuget', '.venv', 'venv',
    'TestResults', 'coverage', '.aws', '.ssh', '.azure', '.secrets',
    'secrets', '.env', '.env.*', '*.pem', '*.key', '*.pfx', '*.p12',
    '*.g.cs', '*.g.i.cs', '*.generated.*',
)
SOURCE_KINDS = {'.sln': 'dotnet-solution', '.slnx': 'dotnet-solution-xml',
                '.csproj': 'dotnet-project'}


class Scanner(Protocol):
    """A scanner returns inventory only, never canonical claims or evidence.

    Paths are root-relative POSIX strings; lists are sorted by path. Excluded
    directories are represented once, without inspecting their descendants.
    Errors make ok false; skipped/unsupported entries are explicit non-errors.
    """

    def scan(self, root: Path, exclusions: Iterable[str] = ()) -> dict: ...


def exclusion_patterns(exclusions):
    patterns = set(DEFAULT_EXCLUSIONS)
    for pattern in exclusions:
        if (not isinstance(pattern, str) or not pattern or pattern.startswith('/')
                or '\\' in pattern or ':' in pattern or '..' in pattern.split('/')
                or any(ord(char) < 32 for char in pattern)):
            raise ValueError('exclusions must be nonempty relative POSIX patterns without parent traversal')
        patterns.add(pattern.rstrip('/'))
    return sorted(patterns)


class RepositoryScanner:
    def scan(self, root: Path, exclusions: Iterable[str] = ()) -> dict:
        result = {'command': 'scan', 'report_version': '1.0', 'ok': True,
                  'sources': [], 'skipped': [], 'errors': [], 'warnings': [
                      'Discovery only; no contents parsed or technical claims validated.',
                      'All links are skipped. Excluded directories are not traversed.',
                      'Do not scan a concurrently modified tree; filename exclusions are not secret detection.'
                  ]}
        try:
            patterns = exclusion_patterns(exclusions)
            result['exclusions'] = patterns
            root = Path(root)
            if root.is_symlink() or root.is_junction() or not root.is_dir():
                raise ValueError('root must be an existing directory, not a symbolic link or junction')
            root = root.resolve(strict=True)
        except (OSError, ValueError, TypeError):
            result['errors'].append({'path': '.', 'reason': 'invalid-root-or-exclusions'})
            return self._finish(result)

        pending = [root]
        while pending:
            directory = pending.pop()
            relative = directory.relative_to(root).as_posix()
            try:
                # Recheck queued directories without following links.
                if directory.is_junction() or not stat.S_ISDIR(directory.lstat().st_mode):
                    result['errors'].append({'path': relative, 'reason': 'directory-changed'})
                    continue
                with os.scandir(directory) as entries:
                    entries = sorted(entries, key=lambda entry: entry.name)
            except OSError:
                result['errors'].append({'path': relative, 'reason': 'directory-unreadable'})
                continue
            for entry in entries:
                path = directory / entry.name
                name = path.relative_to(root).as_posix()
                record = {'path': name}
                try:
                    if entry.is_symlink() or path.is_junction():
                        result['skipped'].append(dict(record, reason='link-not-followed'))
                        continue
                    match = next((p for p in patterns if fnmatchcase(
                        name if '/' in p else entry.name, p)), None)
                    if match is not None:
                        result['skipped'].append(dict(record, reason='excluded', pattern=match))
                    elif entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        kind = SOURCE_KINDS.get(path.suffix.lower())
                        if kind:
                            result['sources'].append(dict(record, kind=kind))
                        else:
                            result['skipped'].append(dict(record, reason='unsupported-source-type'))
                    else:
                        result['skipped'].append(dict(record, reason='special-file'))
                except OSError:
                    result['errors'].append(dict(record, reason='entry-unreadable'))
        return self._finish(result)

    @staticmethod
    def _finish(result):
        for key in ('sources', 'skipped', 'errors'):
            result[key].sort(key=lambda item: item['path'])
        result['ok'] = not result['errors']
        result['counts'] = {key: len(result[key]) for key in ('sources', 'skipped', 'errors')}
        return result
