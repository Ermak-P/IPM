import argparse
from contextlib import ExitStack
import hashlib
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys


VERSION = '1.0.0'
MANIFEST = {
    'format': 'universal-architecture-kb', 'format_version': '1.0.0',
    'schema_versions': {'claim': '1.0.0', 'evidence': '1.0.0', 'relationship': '1.0.0'},
    'capabilities': ['init', 'validate', 'check-scaffold', 'version'],
    'storage': {'manifest': 'JSON-compatible YAML 1.2', 'records': 'UTF-8 JSON, one object per file',
                'documentation': 'Markdown'},
}
DIRECTORIES = ['schema', 'knowledge/claims', 'knowledge/relationships', 'knowledge/domains',
               'knowledge/decisions', 'knowledge/open-questions', 'evidence', 'sources',
               'generated', 'state', 'docs', 'tools', 'tools/tests', 'tools/examples',
               'tools/examples/existing-knowledge']
FILES = ['README.md', 'manifest.yaml', 'schema/claim.schema.json', 'schema/evidence.schema.json',
         'schema/relationship.schema.json', 'docs/knowledge-lifecycle.md',
         'docs/evidence-and-confidence.md', 'docs/schema-versioning.md',
         'docs/contract-v1.md', 'tools/kb.py', 'tools/tests/test_acceptance.py',
         'tools/examples/claim.json', 'tools/examples/evidence.json', 'tools/examples/relationship.json',
         'tools/examples/basis.json']
FILES += ['tools/population_scan.py', 'tools/tests/test_scan.py', 'docs/population-scan.md']
FILES += ['tools/population_dotnet.py', 'tools/tests/test_extract.py', 'docs/population-extract.md']
FILES += ['tools/population_normalize.py', 'tools/tests/test_normalize.py', 'docs/population-normalize.md']
FILES += ['tools/population_transaction.py', 'tools/tests/test_population.py', 'docs/population-apply.md']
FILES += ['.gitignore']
FILES += ['docs/transaction-review-d1.md', 'docs/windows11-ntfs-checklist.md']
FILES += ['tools/knowledge_graph.py', 'tools/tests/test_graph.py', 'docs/graphs-and-reports.md',
          'tools/examples/graph_demo.py']
FILES += ['tools/compatibility_inspector.py', 'tools/tests/test_compatibility.py',
          'docs/compatibility-inspector.md', 'tools/examples/existing-knowledge/fixture.json',
          'tools/examples/existing-knowledge/README.md']
FILES += ['tools/compatibility_adapter.py', 'tools/tests/test_adapter.py', 'docs/compatibility-adapter.md']
PLACEHOLDERS = [directory + '/.gitkeep' for directory in DIRECTORIES
                if directory not in ['schema', 'docs', 'tools', 'tools/tests', 'tools/examples', 'tools/examples/existing-knowledge']]
SOURCE = Path(__file__).resolve().parents[1]
SCHEMA_HASHES = {
    'claim': '43c3c811e9a9f2b32dfcbeba1519d5a4f0024ca36378b457aeafcbf63da9d2cc',
    'evidence': '984f980ab218359871f4fc8424b748cc093688c42b762d07e0e225170c768bcf',
    'relationship': '31ee6cb31d25adca58ece3bf8c6db08660f910c8eb040b84f24c39740be5d95a',
}


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON: ' + value)))


def linked(path):
    return path.is_symlink() or path.is_junction()


def check_paths(base):
    if linked(base):
        raise ValueError('.ai must not be a symbolic link or junction')
    if base.exists():
        if not base.is_dir():
            raise ValueError('.ai must be a directory')
        for path in sorted(base.rglob('*')):
            if linked(path):
                raise ValueError('symbolic links and junctions are not allowed: ' + str(path.relative_to(base)))


def schema_errors(value, schema, location='$'):
    errors = []
    if 'anyOf' in schema:
        if not any(not schema_errors(value, option, location) for option in schema['anyOf']):
            errors.append(location + ': no allowed alternative matches')
        return errors
    types = {'object': dict, 'array': list, 'string': str, 'null': type(None)}
    if 'type' in schema and not isinstance(value, types[schema['type']]):
        return [location + ': expected ' + schema['type']]
    if 'enum' in schema and value not in schema['enum']:
        errors.append(location + ': value outside enumeration')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:
                errors.append(location + ': missing ' + key)
        properties = schema.get('properties', {})
        for key in sorted(value):
            if key in properties:
                errors.extend(schema_errors(value[key], properties[key], location + '.' + key))
            elif schema.get('additionalProperties') is False:
                errors.append(location + ': unknown field ' + key)
    if isinstance(value, list):
        if schema.get('uniqueItems') and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(location + ': duplicate array entries')
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get('items', {}), f'{location}[{index}]'))
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(location + ': string too short')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(location + ': invalid string pattern')
        try:
            if schema.get('format') == 'date':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError()
                date.fromisoformat(value)
            if schema.get('format') == 'date-time':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})', value):
                    raise ValueError()
                datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            errors.append(location + ': invalid ' + schema['format'])
    return errors


def check_schema(schema):
    if not isinstance(schema, dict):
        raise ValueError('schema must be an object')
    supported = {'$schema', 'type', 'required', 'properties', 'additionalProperties', 'enum',
                 'anyOf', 'items', 'uniqueItems', 'minLength', 'pattern', 'format'}
    if set(schema) - supported:
        raise ValueError('unsupported schema keywords: ' + ', '.join(sorted(set(schema) - supported)))
    if 'type' in schema and schema['type'] not in ['object', 'array', 'string', 'null']:
        raise ValueError('unsupported schema type')
    if 'pattern' in schema:
        re.compile(schema['pattern'])
    for child in schema.get('properties', {}).values():
        check_schema(child)
    for child in schema.get('anyOf', []):
        check_schema(child)
    if 'items' in schema:
        check_schema(schema['items'])


def manifest_errors(base):
    value = read_json(base / 'manifest.yaml')
    if value != MANIFEST:
        return ['manifest.yaml: unsupported or malformed manifest; expected format and schema versions 1.0.0']
    return []


def init(base):
    check_paths(base)
    if base.exists() and any(base.iterdir()):
        if not (base / 'manifest.yaml').is_file():
            return ['.ai: existing data without a recognized manifest; reconcile manually']
        errors = manifest_errors(base)
        if errors:
            return errors
    templates = {}
    for name in FILES:
        source = SOURCE / name
        if not source.is_file() or linked(source):
            return [name + ': installer source is incomplete or linked']
        templates[name] = source.read_bytes()
    errors = []
    for directory in DIRECTORIES:
        path = base / directory
        if path.exists() and not path.is_dir():
            errors.append(directory + ': expected directory; preserved existing data')
    for name in FILES + PLACEHOLDERS:
        path = base / name
        if path.exists() and not path.is_file():
            errors.append(name + ': expected file; preserved existing data')
        elif name in templates and path.exists() and path.read_bytes() != templates[name]:
            errors.append(name + ': existing content differs; reconcile manually')
    if errors:
        return errors
    for directory in DIRECTORIES:
        (base / directory).mkdir(parents=True, exist_ok=True)
    for name in FILES + PLACEHOLDERS:
        path = base / name
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(templates.get(name, b''))
    return []


def scaffold_errors(base):
    errors = manifest_errors(base)
    for directory in DIRECTORIES:
        if not (base / directory).is_dir():
            errors.append(directory + ': missing directory')
    for name in FILES:
        if not (base / name).is_file():
            errors.append(name + ': missing scaffold file')
    return errors


def validate(base):
    errors = manifest_errors(base)
    if errors:
        return errors, []
    groups = {'claim': 'knowledge/claims', 'evidence': 'evidence', 'relationship': 'knowledge/relationships'}
    records = {kind: {} for kind in groups}
    all_ids = {}
    for kind, directory in groups.items():
        schema_path = base / 'schema' / (kind + '.schema.json')
        schema = read_json(schema_path)
        check_schema(schema)
        digest = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        if digest != SCHEMA_HASHES[kind]:
            errors.append(str(schema_path.relative_to(base)) + ': schema differs from supported v1 schema')
            continue
        if not (base / directory).is_dir():
            errors.append(directory + ': missing record directory')
            continue
        for path in sorted((base / directory).rglob('*')):
            if path.is_dir() or path.name == '.gitkeep':
                continue
            name = path.relative_to(base).as_posix()
            if path.suffix != '.json':
                errors.append(name + ': records must use .json')
                continue
            try:
                value = read_json(path)
                issues = schema_errors(value, schema)
            except (ValueError, OSError) as error:
                errors.append(name + ': ' + str(error))
                continue
            if issues:
                errors.extend(name + ': ' + issue for issue in issues)
                continue
            identifier = value['id']
            if identifier in all_ids:
                errors.append(f'{name}: duplicate identifier {identifier}; also in {all_ids[identifier]}')
            else:
                all_ids[identifier] = name
                records[kind][identifier] = value
    claims, evidence, relationships = (records[kind] for kind in groups)

    def issue(identifier, message):
        errors.append(f'{all_ids[identifier]}: {identifier}: {message}')

    for identifier, item in evidence.items():
        for target in item['substantiates']:
            if target not in claims:
                issue(identifier, 'substantiates missing claim ' + target)
    for identifier, claim in claims.items():
        for field, targets in [('evidence', evidence), ('depends_on', claims), ('conflicts_with', claims)]:
            for target in claim[field]:
                if target not in targets:
                    issue(identifier, field + ' references missing identifier ' + target)
                elif field != 'evidence' and target == identifier:
                    issue(identifier, field + ' prohibits self-reference ' + target)
                elif field == 'conflicts_with' and identifier not in claims[target]['conflicts_with']:
                    issue(identifier, 'asymmetric conflict with ' + target)
        if claim['status'] == 'CONFIRMED':
            allowed = ['direct-authoritative'] if claim['type'] == 'business_rule' else ['direct-authoritative', 'direct-technical']
            sufficient = [item for key in claim['evidence'] if (item := evidence.get(key))
                          and item['status'] == 'active' and item['type'] in allowed
                          and identifier in item['substantiates'] and item.get('location')]
            if not sufficient:
                issue(identifier, 'CONFIRMED requires active, appropriate direct evidence with location and explicit substantiates link')
            if claim['last_verified'] is None:
                issue(identifier, 'CONFIRMED requires last_verified date')
    edges = set()
    for identifier, relation in relationships.items():
        start, end, kind = relation['from'], relation['to'], relation['type']
        if start not in claims or end not in claims:
            issue(identifier, f'relationship has missing claim: {start} -> {end}')
        elif start == end:
            issue(identifier, 'relationship prohibits self-reference ' + start)
        elif end not in claims[start][kind]:
            issue(identifier, f'relationship must match claim {start}.{kind}: {end}')
        edge = (kind, *sorted([start, end])) if kind == 'conflicts_with' else (kind, start, end)
        if edge in edges:
            issue(identifier, f'duplicate relationship {start} -> {end}')
        edges.add(edge)
    pending = {key: set(value['depends_on']) & claims.keys() for key, value in claims.items()}
    while pending:
        ready = {key for key, dependencies in pending.items() if not dependencies}
        if not ready:
            errors.append('knowledge/claims: dependency cycle involving ' + ', '.join(sorted(pending)))
            break
        pending = {key: dependencies - ready for key, dependencies in pending.items() if key not in ready}
    warnings = ['Structural validation does not prove claim truth, source authority, or evidence freshness; human review is required.']
    for identifier, claim in claims.items():
        for target in claim['conflicts_with']:
            if target in claims and identifier < target:
                warnings.append(f'{all_ids[identifier]}: unresolved conflict {identifier} <-> {target} ({all_ids[target]})')
    return errors, warnings


def _main(stack):
    parser = argparse.ArgumentParser(description='Offline universal architecture knowledge base v1')
    parser.add_argument('command', choices=['init', 'validate', 'check-scaffold', 'version', 'scan', 'extract', 'normalize', 'populate', 'build', 'report', 'inspect-compatibility', 'adapt-compatibility'])
    parser.add_argument('populate_action', nargs='?', choices=['prepare', 'apply', 'status', 'recover'])
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='existing host repository directory')
    parser.add_argument('--json', action='store_true', help='machine-readable deterministic output')
    parser.add_argument('--plan', help='populate: saved sha256 plan fingerprint, never a file path')
    parser.add_argument('--approve', help='populate apply: explicit approval of the exact plan fingerprint')
    parser.add_argument('--dry-run', action='store_true', help='populate apply: validate without applying')
    parser.add_argument('--exclude', action='append', default=[],
                        help='scan/extract/normalize, populate prepare, technical-preview/report: additional exclusions (repeatable)')
    parser.add_argument('--view', choices=['canonical', 'technical-preview'],
                        help='build only: default canonical; technical-preview is noncanonical')
    parser.add_argument('--write-generated', action='store_true',
                        help='build/report only: save disposable JSON under .ai/generated/')
    args = parser.parse_args()
    if args.view and args.command != 'build':
        parser.error('--view requires build')
    if args.write_generated and args.command not in ['build', 'report']:
        parser.error('--write-generated requires build/report')
    if args.command == 'adapt-compatibility':
        if args.populate_action or args.plan or args.approve or args.dry_run or args.exclude:
            parser.error('adapt-compatibility accepts only --root and --json')
        from compatibility_adapter import CompatibilityAdapter
        result = CompatibilityAdapter().propose(args.root)
        if args.json or not result['ok']:
            print(json.dumps(result, sort_keys=True))
        else:
            print('Read-only compatibility proposal: ' + json.dumps(result['metrics'], sort_keys=True))
            print('Structural candidates only; integration and insertion are not approved.')
        return 0 if result['ok'] else 1
    if args.command == 'inspect-compatibility':
        if args.populate_action or args.plan or args.approve or args.dry_run or args.exclude:
            parser.error('inspect-compatibility accepts only --root and --json')
        from compatibility_inspector import CompatibilityInspector
        try:
            result = CompatibilityInspector().inspect(args.root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            result = {'command': args.command, 'ok': False, 'complete': False,
                      'inspection_format': 'existing-knowledge-compatibility', 'inspection_version': '1.0',
                      'integration_approved': False, 'suggested_integration_mode': 'integration-blocked',
                      'errors': ['Inspection inputs unsafe, unsupported, changed or unreadable.']}
        if args.json or not result['ok']:
            print(json.dumps(result, sort_keys=True))
        else:
            print('Compatibility inspection: {entries} entries; complete={complete}; mode={mode}; integration approved=False'.format(
                entries=result['inventory_summary']['entries'], complete=result['complete'],
                mode=result['suggested_integration_mode']))
            print('Blockers: ' + str(len(result['blockers'])) + '; ownership remains provisional.')
        return 0 if result['ok'] else 1
    if args.command in ['build', 'report']:
        if args.populate_action or args.plan or args.approve or args.dry_run:
            parser.error('population options require populate')
        if args.command == 'build' and (args.view or 'canonical') == 'canonical' and args.exclude:
            parser.error('--exclude requires technical-preview or report')
        from knowledge_graph import GraphBuilder, GraphInputError, human_report, save_generated
        from population_transaction import PopulationError
        try:
            builder = GraphBuilder()
            result = (builder.build(args.root, args.view or 'canonical', args.exclude)
                      if args.command == 'build' else builder.report(args.root, args.exclude))
            if args.write_generated:
                filename = ((result['graph']['view'] + '-graph.json') if args.command == 'build'
                            else 'knowledge-report.json')
                save_generated(args.root, filename, result)
        except GraphInputError as error:
            result = {'command': args.command, 'ok': False, 'errors': [str(error)], **error.details}
        except PopulationError as error:
            result = {'command': args.command, 'ok': False, 'errors': [str(error)],
                      'guidance': 'Run validate, extract, normalize or populate status/recover as appropriate.'}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            result = {'command': args.command, 'ok': False,
                      'errors': ['Graph/report inputs invalid, changed, unsafe, busy or recovery required; run validate, extract, normalize and populate status.']}
        if args.json or args.command == 'build' or not result['ok']:
            print(json.dumps(result, sort_keys=True))
        else:
            print(human_report(result), end='')
        return 0 if result['ok'] else 1
    if args.command == 'populate':
        from population_transaction import PopulationStore, PopulationError
        action = args.populate_action or 'prepare'
        if args.exclude and action != 'prepare':
            parser.error('--exclude is supported only for populate prepare')
        if (args.approve or args.dry_run) and action != 'apply':
            parser.error('--approve/--dry-run are supported only for populate apply')
        if action in ['apply', 'recover'] and not args.plan:
            parser.error('--plan is required for populate apply/recover')
        if action == 'prepare' and args.plan:
            parser.error('prepare creates a fresh plan; --plan is not accepted')
        try:
            store = PopulationStore(args.root)
            if action == 'prepare':
                result = store.prepare(args.exclude)
            elif action == 'apply':
                result = store.apply(args.plan, args.approve, args.dry_run)
            elif action == 'status':
                result = store.status(args.plan)
            else:
                result = store.recover(args.plan)
        except PopulationError as error:
            result = {'ok': False, 'error': str(error)}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            result = {'ok': False, 'error': 'population-input-or-io-error-inspect-status-before-retry'}
        result.update(command='populate', action=action)
        print(json.dumps(result, sort_keys=True, **({} if args.json else {'indent': 2})))
        return 0 if result['ok'] else 1
    if args.populate_action or args.plan or args.approve or args.dry_run:
        parser.error('population action/options require the populate command')
    if args.command != 'version':
        from population_transaction import normal_operation, PopulationError
        try:
            stack.enter_context(normal_operation(args.root))
        except (PopulationError, OSError, ValueError, TypeError, KeyError, AttributeError):
            print(json.dumps({'command': args.command, 'ok': False,
                              'errors': ['Population is busy or recovery is required; run populate status/recover.'],
                              'warnings': []}, sort_keys=True))
            return 1
    if args.command in ['scan', 'extract', 'normalize']:
        from population_scan import RepositoryScanner
        result = RepositoryScanner().scan(args.root, args.exclude)
        if args.command in ['extract', 'normalize']:
            from population_dotnet import DotNetAnalyzer
            result = DotNetAnalyzer().extract(args.root, result)
        if args.command == 'normalize':
            from population_normalize import CandidateNormalizer
            result = CandidateNormalizer().normalize(args.root, result)
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            if args.command == 'scan':
                print('Scan: {sources} sources, {skipped} skipped, {errors} errors'.format(**result['counts']))
            elif args.command == 'extract':
                print('Extract: {candidates} candidates, {diagnostics} diagnostics'.format(**result['counts']))
            else:
                print('Normalize: {claims} claims, {evidence} evidence, {relationships} relationships'.format(**result['counts']))
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result['ok'] else 1
    if args.exclude:
        parser.error('--exclude is supported only for scan/extract/normalize')
    errors, warnings = [], []
    try:
        if args.command != 'version':
            if not args.root.is_dir():
                raise ValueError('--root must be an existing directory')
            base = args.root.resolve() / '.ai'
            check_paths(base)
            if args.command == 'init':
                errors = init(base)
            elif args.command == 'validate':
                errors, warnings = validate(base)
            else:
                errors = scaffold_errors(base)
                validation_errors, warnings = validate(base)
                errors.extend(validation_errors)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error) as error:
        message = str(error)
        if args.command != 'version' and args.root.is_dir():
            message = message.replace(str(args.root.resolve()), '<root>')
        errors.append('.ai: ' + message)
    result = {'command': args.command, 'ok': not errors, 'errors': sorted(set(errors)),
              'warnings': sorted(set(warnings))}
    if args.command == 'version':
        result.update(cli_version=VERSION, supported_format_versions=['1.0.0'])
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


def main():
    with ExitStack() as stack:
        return _main(stack)


if __name__ == '__main__':
    sys.exit(main())
