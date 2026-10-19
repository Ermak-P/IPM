"""Deterministic clean distribution builder. Does not install or touch a target repo."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

import kb

PROFILE = 'clean-runtime-v1'
TOOLS = ['kb.py', 'population_scan.py', 'population_dotnet.py', 'population_normalize.py',
         'population_transaction.py', 'knowledge_graph.py', 'compatibility_inspector.py',
         'compatibility_adapter.py']
DOCS = ['contract-v1.md', 'knowledge-lifecycle.md', 'evidence-and-confidence.md',
        'schema-versioning.md', 'population-scan.md', 'population-extract.md',
        'population-normalize.md', 'population-apply.md', 'graphs-and-reports.md',
        'compatibility-inspector.md', 'compatibility-adapter.md',
        'windows11-ntfs-checklist.md', 'clean-deployment.md']
DIRECTORIES = [n for n in kb.DIRECTORIES if n != 'tools/examples/existing-knowledge']
PLACEHOLDERS = [n + '/.gitkeep' for n in DIRECTORIES
                if n not in ['schema', 'docs', 'tools', 'tools/tests', 'tools/examples']]
FILES = ['README.md', 'manifest.yaml', '.gitignore', 'deployment-profile.json',
         *['schema/' + k + '.schema.json' for k in ['claim', 'evidence', 'relationship']],
         *['tools/' + n for n in TOOLS], *['docs/' + n for n in DOCS]]
CATEGORIES = ['reusable-framework-code-and-contracts', 'required-scaffold-files',
              'framework-tests-and-documentation', 'synthetic-sample-data',
              'generated-artifacts', 'runtime-state-plans-and-journals']
LIMIT = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def checked_file(path):
    for parent in [*reversed(path.parents), path]:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError('linked-package-source-or-output')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
        raise ValueError('unsafe-or-oversized-package-file')
    data = path.read_bytes()
    current = path.stat()
    stable = lambda item: (item.st_mode, item.st_dev, item.st_ino, item.st_nlink, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if stable(current) != stable(info) or len(data) != info.st_size:
        raise ValueError('package-input-changed')
    return data


def runtime_cli(source):
    tree = ast.parse(source)
    starts, ends = [], []
    for node in tree.body:
        names = ([t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign)
                 else [node.target.id] if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) else [])
        if set(names) & {'DIRECTORIES', 'FILES', 'PLACEHOLDERS'}:
            starts.append(node.lineno - 1); ends.append(node.end_lineno)
    if not starts:
        raise ValueError('unrecognized-development-registry')
    lines = source.splitlines(keepends=True)
    registry = ('# Generated clean-runtime-v1 registry; canonical contracts/functions unchanged.\n'
                + 'DIRECTORIES = ' + repr(DIRECTORIES) + '\nFILES = ' + repr(FILES)
                + '\nPLACEHOLDERS = ' + repr(PLACEHOLDERS) + '\n')
    result = ''.join(lines[:min(starts)]) + registry + ''.join(lines[max(ends):])
    # Fail closed if a future source layout would remove anything except registry assignments.
    def remaining(code):
        parsed = ast.parse(code)
        kept = []
        for node in parsed.body:
            names = ([t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign)
                     else [node.target.id] if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) else [])
            if not set(names) & {'DIRECTORIES', 'FILES', 'PLACEHOLDERS'}:
                kept.append(ast.dump(node, include_attributes=False))
        return kept
    if remaining(source) != remaining(result):
        raise ValueError('unexpected-code-in-registry-region')
    return result.encode('utf-8')


def runtime_document(name, data):
    """Omit development case-study observations, not operational rules/contracts."""
    text = data.decode('utf-8')
    if name == 'docs/compatibility-inspector.md':
        text = text.split('## Harbor example and regression')[0]
    elif name == 'docs/compatibility-adapter.md':
        start, end = text.index('### Original Harbor Tickets result'), text.index('## Graph ownership boundary and next decision')
        text = text[:start] + text[end:]
        text = text.split('## Executed verification and changed files')[0]
        text = '\n'.join(line for line in text.split('\n') if not line.startswith('Baseline: '))
    elif name == 'docs/clean-deployment.md':
        start = text.index('## Acceptance evidence and open gates')
        end = text.index('Native Windows 11/NTFS is **NOT TESTED** here.', start)
        text = text[:start] + '## Remaining acceptance gates\n\n' + text[end:]
    return text.encode('utf-8')


def category(relative):
    if relative.startswith('generated/'):
        return CATEGORIES[4]
    if relative.startswith('state/'):
        return CATEGORIES[5]
    if relative.startswith('tools/examples/') or relative.startswith(('knowledge/', 'evidence/', 'sources/')) and not relative.endswith('/.gitkeep'):
        return CATEGORIES[3]
    if relative.startswith(('docs/', 'tools/tests/', 'deployment/')):
        return CATEGORIES[2]
    if relative.startswith(('tools/', 'schema/')) and not relative.endswith('/.gitkeep'):
        return CATEGORIES[0]
    if relative in ['README.md', 'manifest.yaml', '.gitignore'] or relative.endswith('/.gitkeep'):
        return CATEGORIES[1]
    raise ValueError('unclassified-ai-file-review-required: ' + relative)


def build(source_root):
    root = Path(source_root).absolute()
    base = root / '.ai'
    kb.check_paths(base)
    inputs = {}
    def read(name):
        data = checked_file(base / name)
        inputs[name] = sha(data)
        return data
    payload = {}
    origins = {}
    for name in FILES:
        if name == 'deployment-profile.json':
            continue
        origin = 'deployment/README.clean.md' if name == 'README.md' else name
        data = read(origin)
        if name == 'tools/kb.py':
            data = runtime_cli(data.decode('utf-8'))
        elif name.startswith('docs/'):
            data = runtime_document(name, data)
        payload['.ai/' + name] = data
        origins[origin] = '.ai/' + name
    if json.loads(payload['.ai/manifest.yaml']) != kb.MANIFEST:
        raise ValueError('unsupported-package-manifest')
    for kind in ['claim', 'evidence', 'relationship']:
        value = json.loads(payload['.ai/schema/' + kind + '.schema.json'])
        if sha(json.dumps(value, sort_keys=True).encode()) != kb.SCHEMA_HASHES[kind]:
            raise ValueError('unsupported-package-schema')
    for name in PLACEHOLDERS:
        payload['.ai/' + name] = b''  # Never copy local canonical/state/generated bytes.
    profile = {'profile': PROFILE, 'profile_version': '1.0', 'canonical_contract': '1.0.0',
        'empty_canonical_store': True, 'project_specific_records_included': False,
        'runtime_state_included': False, 'generated_observations_included': False,
        'documentation_policy': 'Operational instructions retained; development case-study observation/verification sections omitted from archive copies only.',
        'runtime_cli_transformation': 'Only DIRECTORIES/FILES/PLACEHOLDERS registry replaced; all other AST nodes identical.',
        'included_files': [{'path': name, 'sha256': sha(data), 'bytes': len(data)} for name, data in sorted(payload.items())],
        'self_manifest': '.ai/deployment-profile.json (verified by trusted outer archive SHA-256)',
        'excluded_policy': ['All development tools/examples and tests; no fixtures or sample knowledge.',
            'All existing knowledge/evidence/source contents, regardless of record validity.',
            'All generated outputs and state, including plans/receipts/journals/locks/verification history.',
            'Historical project assessments/acceptance reports; no source project observations.',
            'Build-only package generator; retained in the development checkout.']}
    payload['.ai/deployment-profile.json'] = canonical(profile).encode()
    # Every current .ai file is classified; unrecognized or unsafe files require review.
    inventory = []
    for path in sorted(base.rglob('*')):
        if path.is_dir():
            continue
        name = path.relative_to(base).as_posix()
        if path.is_symlink() or path.is_junction() or not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('unsafe-inventory-object')
        item = {'path': '.ai/' + name, 'category': category(name),
                'included_as': origins.get(name), 'original_preserved': True,
                'archive_transformation': ('clean-runtime registry' if name == 'tools/kb.py' else
                    'omit development observation sections' if name in ['docs/compatibility-inspector.md', 'docs/compatibility-adapter.md', 'docs/clean-deployment.md']
                    else 'clean runtime README' if name == 'deployment/README.clean.md' else None)}
        if item['included_as']:
            item['source_sha256'] = inputs[name]
            item['exclusion_reason'] = None
        else:
            item['exclusion_reason'] = ('Empty placeholder generated independently; original never copied.' if name.endswith('/.gitkeep')
                else 'Outside explicit runtime allowlist; retained only in development repository.')
        inventory.append(item)
    for name, digest in inputs.items():
        if sha(checked_file(base / name)) != digest:
            raise ValueError('package-input-changed')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        entries = {'.ai/': None, **{'.ai/' + n + '/': None for n in DIRECTORIES}, **payload}
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((stat.S_IFDIR | 0o755) << 16 | 0x10) if data is None else ((stat.S_IFREG | 0o644) << 16)
            archive.writestr(info, b'' if data is None else data)
    archive_bytes = output.getvalue()
    audit = {'format': 'clean-deployment-inventory', 'version': '1.0', 'profile': PROFILE,
             'archive_sha256': sha(archive_bytes), 'source_scope': 'Current development .ai; no source observations copied.',
             'categories': CATEGORIES, 'inventory': inventory,
             'package_files': profile['included_files'] + [{'path': '.ai/deployment-profile.json', 'sha256': sha(payload['.ai/deployment-profile.json']), 'bytes': len(payload['.ai/deployment-profile.json'])}]}
    return archive_bytes, audit


def write_new_or_identical(path, data):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        if checked_file(path) != data:
            raise ValueError('output-exists-with-different-content')
        return
    # Parent must already exist and be explicitly selected; never mkdir foreign paths.
    for parent in [*reversed(path.parent.parents), path.parent]:
        if parent.is_symlink() or parent.is_junction() or not parent.is_dir():
            raise ValueError('unsafe-output-parent')
    with path.open('xb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True, help='explicit ZIP artifact path; existing differing files are preserved')
    parser.add_argument('--inventory', type=Path, help='external included/excluded audit JSON; never deployed as project knowledge')
    args = parser.parse_args()
    try:
        data, audit = build(args.source)
        write_new_or_identical(args.output, data)
        if args.inventory:
            write_new_or_identical(args.inventory, canonical(audit).encode())
        print(json.dumps({'ok': True, 'profile': PROFILE, 'archive_sha256': sha(data), 'bytes': len(data)}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError):
        print(json.dumps({'ok': False, 'error': 'Package inputs/output unsafe, incomplete, changed or occupied; inspect locally.'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
