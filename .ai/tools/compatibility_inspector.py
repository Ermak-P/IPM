"""Bounded read-only foreign .ai inspection. No imports of inspected code or writes."""
from collections import Counter
from fnmatch import fnmatchcase
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import unicodedata

import kb

MAX_ENTRIES = 4096
MAX_DEPTH = 32
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_JSON_DEPTH = 48
MAX_JSON_NODES = 50000
EXCLUDED = ('.git', 'node_modules', '__pycache__', '.venv', '.cache',
            '.env', '.env.*', '*.pem', '*.key', '*.pfx', '*.p12',
            'secrets', '.secrets', 'credentials')
SCRIPT_SUFFIXES = {'.py', '.ps1', '.sh', '.cmd', '.bat', '.js', '.ts', '.exe', '.dll'}
LABEL = re.compile(r'^[A-Za-z0-9._:/-]{1,160}$')
ID = re.compile(r'^[A-Za-z][A-Za-z0-9._:-]*$')
GROUPS = {'claims': '.ai/knowledge/claims', 'evidence': '.ai/evidence',
          'relationships': '.ai/knowledge/relationships'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def fingerprint(value):
    return 'sha256:' + hashlib.sha256(encoded(value).encode()).hexdigest()


def label(value):
    # Only selected bounded metadata, never prose/snippets/exception messages.
    return value if isinstance(value, str) and LABEL.fullmatch(value) else None


def safe_path(value):
    return (isinstance(value, str) and value and len(value) <= 512 and '\\' not in value and ':' not in value
            and not value.startswith('/') and not any(ord(c) < 32 for c in value)
            and all(p not in ('', '.', '..') for p in value.split('/')))


def signature(info):
    return (info.st_mode, info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate-json-key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite-json')
    result = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    pending, count = [(result, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError('json-resource-limit')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('nonfinite-json')
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)
    return result


def role(name):
    for group, prefix in GROUPS.items():
        if name.startswith(prefix + '/'):
            return group
    for prefix, result in [('knowledge/domains', 'domain-documentation'),
                           ('knowledge/decisions', 'decisions'), ('sources', 'sources'),
                           ('schema', 'schemas'), ('tools', 'tools'),
                           ('generated', 'potentially-durable-generated'),
                           ('state', 'potentially-durable-state'), ('business', 'business-documentation')]:
        if name == '.ai/' + prefix or name.startswith('.ai/' + prefix + '/'):
            return result
    if Path(name).name.endswith('.schema.json'):
        return 'schemas'
    return 'manifest' if name == '.ai/manifest.yaml' else 'unknown'


class UnsafeInput(ValueError):
    pass


class Inventory:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.entries, self.observations, self.documents, self.issues = [], {}, {}, []
        self.total = 0

    def issue(self, code, path):
        self.issues.append({'code': code, 'path': path})

    def checked(self, path):
        # Recheck every ancestor without resolving through a foreign link/junction.
        for part in [*reversed(path.parents), path]:
            if part.is_symlink() or part.is_junction():
                raise UnsafeInput('unsafe-link')
            info = part.lstat()
            if part != path and not stat.S_ISDIR(info.st_mode):
                raise UnsafeInput('unsafe-parent')
        return info

    def read(self, path, expected):
        current = self.checked(path)
        if signature(current) != signature(expected):
            raise UnsafeInput('input-changed-during-read')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or signature(opened) != signature(expected)):
                raise UnsafeInput('input-changed-during-open')
            data = stream.read(MAX_FILE_BYTES + 1)
            if signature(os.fstat(stream.fileno())) != signature(expected):
                raise UnsafeInput('input-changed-during-read')
        if len(data) > MAX_FILE_BYTES or signature(self.checked(path)) != signature(expected):
            raise UnsafeInput('input-changed-or-size-limit')
        return data

    def run(self):
        try:
            if '..' in self.root.parts or not stat.S_ISDIR(self.checked(self.root).st_mode):
                raise UnsafeInput('invalid-root')
            self.observations['<root>'] = signature(self.root.lstat())
            base = self.root / '.ai'
            if not base.exists() and not base.is_symlink() and not base.is_junction():
                return self
            if not base.is_symlink() and not base.is_junction() and not stat.S_ISDIR(base.lstat().st_mode):
                self.issue('ai-not-directory', '.ai')
                return self
            pending = [(base, 0)]
            while pending:
                path, depth = pending.pop()
                name = path.relative_to(self.root).as_posix()
                if len(self.entries) >= MAX_ENTRIES:
                    self.issue('entry-limit', '.ai')
                    break
                entry = {'path': name, 'role': role(name), 'ownership': 'unknown-provisional',
                         'disposable': False, 'content_fingerprint': None}
                self.entries.append(entry)
                if not safe_path(name):
                    entry['type'] = 'unsafe-name'; self.issue('unsafe-name', name); continue
                try:
                    info = path.lstat()
                    self.observations[name] = signature(info)
                    if path.is_symlink() or path.is_junction():
                        entry['type'] = 'link'; self.issue('unsafe-link', name); continue
                    if stat.S_ISDIR(info.st_mode):
                        entry['type'] = 'directory'
                    elif stat.S_ISREG(info.st_mode):
                        entry['type'] = 'file'; entry['bytes'] = info.st_size
                    else:
                        entry['type'] = 'special'; self.issue('unsafe-object', name); continue
                    if any(fnmatchcase(path.name.lower(), pattern) for pattern in EXCLUDED):
                        entry['excluded'] = True; self.issue('excluded-sensitive-or-cache-content', name); continue
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= MAX_DEPTH:
                            self.issue('depth-limit', name); continue
                        self.checked(path)
                        with os.scandir(path) as iterator:
                            # Bound enumeration as well as traversal/output memory.
                            names = []
                            remaining = MAX_ENTRIES - len(self.entries) - len(pending)
                            for child in iterator:
                                if len(names) >= remaining:
                                    self.issue('entry-limit', name); break
                                names.append(child.name)
                        pending.extend((path / child, depth + 1) for child in reversed(sorted(names)))
                    else:
                        if info.st_nlink != 1:
                            self.issue('unsafe-hardlink', name); continue
                        if info.st_size > MAX_FILE_BYTES or self.total + info.st_size > MAX_TOTAL_BYTES:
                            self.issue('content-size-limit', name); continue
                        data = self.read(path, info)
                        self.total += len(data)
                        entry['content_fingerprint'] = 'sha256:' + hashlib.sha256(data).hexdigest()
                        # Do not parse scripts, Markdown, source or arbitrary config formats.
                        structured = (name == '.ai/manifest.yaml' or role(name) in ['claims', 'evidence', 'relationships', 'schemas']
                                      or path.name == 'graph-contract.json')
                        if structured:
                            if path.suffix.lower() != '.json' and name != '.ai/manifest.yaml':
                                entry['structured_status'] = 'unsupported-format'
                                continue
                            try:
                                document = strict_json(data)
                                if not isinstance(document, dict):
                                    raise ValueError('expected-json-object')
                                self.documents[name] = document
                                entry['structured_status'] = 'json-object'
                            except (ValueError, UnicodeError, RecursionError) as error:
                                entry['structured_status'] = 'invalid-or-over-limit-json'
                                if isinstance(error, RecursionError) or str(error) == 'json-resource-limit':
                                    self.issue('json-resource-limit', name)
                except (OSError, UnsafeInput):
                    self.issue('unsafe-unreadable-or-changing-path', name)
                    entry.setdefault('type', 'unreadable')
        except (OSError, UnsafeInput):
            self.issue('invalid-unsafe-or-unreadable-root', '.')
        self.entries.sort(key=lambda e: e['path'])
        return self

    def snapshot(self):
        return fingerprint([{k: v for k, v in entry.items() if k != 'occupied_framework_path'}
                            for entry in self.entries])


def _checkpoint():
    """Test seam for observable changes; not a CLI option or tool hook."""


class CompatibilityInspector:
    def inspect(self, root):
        first = Inventory(root).run()
        assessment = Assessment(first)
        assessment.analyze()
        _checkpoint()
        final = Inventory(root).run()
        changed = (first.snapshot() != final.snapshot() or first.observations != final.observations
                   or first.issues != final.issues)
        if changed:
            assessment.diagnostic('inputs-changed-during-inspection', '.', scope='inspection')
        return assessment.finish(final, changed)


class Assessment:
    def __init__(self, inventory):
        self.inventory = inventory
        self.diagnostics, self.tools, self.schema_declarations, self.records = [], {}, [], []
        self.capabilities = ['bounded-read-only-ai-inventory', 'strict-json-metadata',
                             'provisional-ownership-only', 'no-tool-execution', 'graph-metadata-discovery']
        self.manifest = {'classification': 'absent', 'accepted_as_contract': False}
        self.templates = {'.ai/' + n for n in [*kb.FILES, *kb.PLACEHOLDERS, *kb.DIRECTORIES]}

    def diagnostic(self, code, path, scope='integration', **details):
        self.diagnostics.append(dict(code=code, path=path, scope=scope, **details))

    def tool(self, path, origin, inputs=(), outputs=(), owner=None):
        if path not in self.tools:
            self.tools[path] = dict(entrypoint=path, discovery=[], declared_inputs=[], declared_outputs=[],
                                    ownership='unknown-provisional', declared_owner=None,
                                    declared_owners=[], declarations=[], universal_overlap='possible', activated=False)
        tool = self.tools[path]
        tool['discovery'] = sorted(set(tool['discovery'] + [origin]))
        tool['declared_inputs'] = sorted(set(tool['declared_inputs'] + list(inputs)))
        tool['declared_outputs'] = sorted(set(tool['declared_outputs'] + list(outputs)))
        declaration = dict(origin=origin, inputs=sorted(set(inputs)), outputs=sorted(set(outputs)), declared_owner=label(owner))
        tool['declarations'] = sorted({encoded(d): d for d in tool['declarations'] + [declaration]}.values(), key=encoded)
        if label(owner):
            tool['declared_owners'] = sorted(set(tool['declared_owners'] + [owner]))
        tool['declared_owner'] = tool['declared_owners'][0] if len(tool['declared_owners']) == 1 else None
        if len(tool['declared_owners']) > 1:
            self.diagnostic('conflicting-graph-owner-declarations', path, scope='operation')

    def declared_path(self, raw, source):
        if not safe_path(raw):
            self.diagnostic('unsafe-or-ambiguous-declared-path', source)
            return None
        return raw if raw.startswith('.ai/') else '.ai/' + raw

    def analyze(self):
        for issue in self.inventory.issues:
            self.diagnostic(issue['code'], issue['path'], scope='inspection')
        documents = self.inventory.documents
        manifest = documents.get('.ai/manifest.yaml')
        if manifest is not None:
            native = manifest == kb.MANIFEST
            self.manifest['classification'] = 'exact-v1-declaration' if native else 'foreign-json-declaration'
            self.manifest['declared_format'] = label(manifest.get('format'))
            self.manifest['accepted_as_contract'] = False  # This is never adoption/validation approval.
            if native:
                self.capabilities.append('exact-v1-manifest-metadata-only')
            if not native:
                self.diagnostic('manifest-incompatible-with-v1', '.ai/manifest.yaml')
            if 'graph_builder' in manifest:
                target = self.declared_path(manifest['graph_builder'], '.ai/manifest.yaml')
                if target:
                    self.tool(target, 'manifest-declaration', owner=manifest.get('knowledge_owner'))
        elif self.inventory.entries:
            self.diagnostic('missing-or-unsupported-manifest', '.ai/manifest.yaml')
        harbor = manifest is not None and manifest.get('format') == 'harbor-team-architecture' and manifest.get('revision') == 3
        if harbor:
            self.capabilities.append('harbor-revision-3-json-field-diagnostics')
        schemas = {group: kb.read_json(kb.SOURCE / 'schema' / (kind + '.schema.json'))
                   for group, kind in [('claims', 'claim'), ('evidence', 'evidence'), ('relationships', 'relationship')]}
        for group, kind in [('claims', 'claim'), ('evidence', 'evidence'), ('relationships', 'relationship')]:
            if hashlib.sha256(json.dumps(schemas[group], sort_keys=True).encode()).hexdigest() != kb.SCHEMA_HASHES[kind]:
                raise ValueError('unsupported-trusted-schema')
        aliases = {}
        for entry in self.inventory.entries:
            name, kind = entry['path'], entry['type']
            aliases.setdefault(unicodedata.normalize('NFC', name).casefold(), []).append(name)
            entry['occupied_framework_path'] = name in self.templates
            if entry['occupied_framework_path']:
                self.diagnostic('occupied-framework-path-owner-approval-required', name)
            if entry['role'] in ['potentially-durable-generated', 'potentially-durable-state']:
                self.diagnostic('potentially-durable-content-preserve', name)
            if name == '.ai/state/population' or name.startswith('.ai/state/population/'):
                self.diagnostic('transaction-or-recovery-state-owner-review-required', name, scope='operation')
            if kind == 'file' and entry['role'] == 'unknown' and Path(name).name != '.gitkeep':
                self.diagnostic('unknown-content-not-interpreted', name)
            if entry.get('structured_status') in ['unsupported-format', 'invalid-or-over-limit-json']:
                self.diagnostic(entry['structured_status'], name)
            if (kind == 'file' and entry['role'] == 'tools' and 'graph' in Path(name).stem.lower()
                    and Path(name).suffix.lower() in SCRIPT_SUFFIXES):
                self.tool(name, 'filename-heuristic')
            if kind == 'file' and entry['role'] == 'tools' and Path(name).suffix.lower() in SCRIPT_SUFFIXES:
                self.diagnostic('tool-ownership-unverified', name)
            document = documents.get(name)
            if document is None:
                continue
            if name.endswith('/graph-contract.json'):
                target = self.declared_path(document.get('entrypoint'), name)
                if target:
                    inputs, outputs = [], []
                    raw_inputs = document.get('inputs', [])
                    raw_output = document.get('output')
                    if not isinstance(raw_inputs, list):
                        self.diagnostic('unsupported-graph-contract-inputs', name)
                        raw_inputs = []
                    for raw in raw_inputs:
                        path = self.declared_path(raw, name)
                        if path:
                            inputs.append(path)
                    if raw_output is not None:
                        path = self.declared_path(raw_output, name)
                        if path:
                            outputs.append(path)
                    self.tool(target, 'graph-contract', inputs, outputs, document.get('owner'))
            if entry['role'] == 'schemas':
                matching = [group for group, schema in schemas.items() if document == schema]
                self.schema_declarations.append({'path': name,
                    'dialect': 'draft-2020-12' if document.get('$schema') == 'https://json-schema.org/draft/2020-12/schema' else 'unknown-or-absent',
                    'matches_pinned_v1': sorted(matching), 'remote_schema_fetched': False})
                if not matching:
                    self.diagnostic('schema-incompatible-or-unsupported', name)
            if entry['role'] in GROUPS:
                self.record(name, entry['role'], document, harbor, schemas[entry['role']])
        for paths in aliases.values():
            if len(paths) > 1:
                self.diagnostic('case-or-unicode-path-alias', paths[0], paths=sorted(paths))
        for tool in self.tools.values():
            self.diagnostic('graph-builder-ownership-selection-required', tool['entrypoint'], scope='operation')
            if not any(e['path'] == tool['entrypoint'] for e in self.inventory.entries):
                self.diagnostic('declared-graph-tool-not-observed', tool['entrypoint'])
        self.references()
        if any(r['profile'] == 'v1-json-fields' for r in self.records):
            self.capabilities.append('v1-json-field-and-reference-diagnostics')
        if self.inventory.entries:
            self.diagnostic('ownership-unknown-no-adoption-authorized', '.ai')

    def record(self, path, group, value, harbor, schema):
        profile = ('harbor-revision-3-json' if harbor and 'kind' in value else
                   'v1-json-fields' if any(k in value for k in ['statement', 'substantiates', 'from', 'type']) else None)
        if profile is None:
            self.diagnostic('unsupported-record-shape', path)
            return
        identifier = value.get('id')
        if not isinstance(identifier, str):
            self.diagnostic('missing-or-invalid-record-id', path)
            identifier = None
        elif not ID.fullmatch(identifier):
            self.diagnostic('id-incompatible-with-v1', path, declared_id=label(identifier), id_fingerprint=fingerprint(identifier))
        required_missing = sorted(set(schema['required']) - value.keys())
        if required_missing:
            self.diagnostic('missing-v1-required-fields', path, fields=required_missing)
        issues = kb.schema_errors(value, schema)
        if issues:
            # Core schema_errors may contain arbitrary foreign keys: never echo them.
            self.diagnostic('v1-record-structural-errors', path, count=len(issues))
        provenance = value.get('provenance')
        if not isinstance(provenance, dict) or not all(isinstance(provenance.get(k), str) and provenance[k].strip() for k in ['actor', 'method']):
            self.diagnostic('missing-or-invalid-provenance', path)
        states = (['CONFIRMED', 'INFERRED', 'UNKNOWN', 'NEEDS_HUMAN_CONFIRMATION'] if group == 'claims'
                  else ['active', 'retracted', 'superseded'] if group == 'evidence' else [])
        if states and value.get('status') not in states:
            self.diagnostic('unrecognized-v1-lifecycle-status', path,
                            legacy_status_present='state' in value,
                            known_legacy_label=value.get('state') if value.get('state') in
                                ['approved', 'verified', 'current', 'withdrawn'] else None)
        if group == 'claims' and (value.get('status') == 'CONFIRMED' and not value.get('last_verified')):
            self.diagnostic('missing-genuine-verification-field', path)
        self.records.append({'path': path, 'group': group, 'profile': profile, 'id': identifier, 'value': value,
                             'v1_shape_valid': not issues})

    def references(self):
        index = {}
        for record in self.records:
            if record['id'] is not None:
                index.setdefault(record['id'], []).append(record)
        for identifier, matches in index.items():
            if len(matches) > 1:
                self.diagnostic('duplicate-record-id', matches[0]['path'], declared_id=label(identifier),
                                id_fingerprint=fingerprint(identifier), paths=sorted(r['path'] for r in matches))
        for record in self.records:
            value, path, group = record['value'], record['path'], record['group']
            fields = ([('evidence', 'evidence'), ('depends_on', 'claims'), ('conflicts_with', 'claims')]
                      if group == 'claims' else [('substantiates', 'claims')] if group == 'evidence'
                      else [('from', 'claims'), ('to', 'claims')])
            if record['profile'] == 'harbor-revision-3-json':
                fields = [('support', 'evidence')] if group == 'claims' else [('supports', 'claims')] if group == 'evidence' else []
                if group == 'relationships':
                    self.diagnostic('unsupported-component-relationship-not-claim-dependency', path)
            for field, target_group in fields:
                raw = value.get(field, [])
                targets = raw if isinstance(raw, list) else [raw] if field in ['from', 'to'] else []
                for target in targets:
                    if not isinstance(target, str):
                        continue
                    matches = index.get(target, [])
                    if not matches or len(matches) != 1 or matches[0]['group'] != target_group:
                        self.diagnostic('missing-ambiguous-or-wrong-kind-reference', path, field=field,
                                        target_id=label(target), target_fingerprint=fingerprint(target))

        # Additional explicit v1 invariants are diagnostics only, never adoption/verification.
        unique = {key: values[0] for key, values in index.items() if len(values) == 1}
        claims = {key: r for key, r in unique.items() if r['group'] == 'claims' and r['v1_shape_valid']}
        evidence = {key: r for key, r in unique.items() if r['group'] == 'evidence' and r['v1_shape_valid']}
        for key, record in claims.items():
            value, path = record['value'], record['path']
            if key in value['depends_on'] or key in value['conflicts_with']:
                self.diagnostic('self-referencing-claim', path)
            for target in value['conflicts_with']:
                if target in claims and key not in claims[target]['value']['conflicts_with']:
                    self.diagnostic('asymmetric-claim-conflict', path, target_id=label(target))
            if value['status'] == 'CONFIRMED':
                allowed = ['direct-authoritative'] if value['type'] == 'business_rule' else ['direct-authoritative', 'direct-technical']
                support = [evidence[e]['value'] for e in value['evidence'] if e in evidence]
                if not any(e['status'] == 'active' and e['type'] in allowed and e.get('location')
                           and key in e['substantiates'] for e in support):
                    self.diagnostic('confirmed-support-not-structurally-sufficient', path)
        pending = {key: set(r['value']['depends_on']) & claims.keys() for key, r in claims.items()}
        while pending:
            ready = {key for key, dependencies in pending.items() if not dependencies}
            if not ready:
                self.diagnostic('claim-dependency-cycle', '.ai/knowledge/claims',
                                record_paths=sorted(claims[key]['path'] for key in pending))
                break
            pending = {key: dependencies - ready for key, dependencies in pending.items() if key not in ready}
        edges = set()
        for record in self.records:
            if record['group'] != 'relationships' or not record['v1_shape_valid']:
                continue
            value, path = record['value'], record['path']
            start, end, kind = value['from'], value['to'], value['type']
            if start == end or start in claims and end not in claims[start]['value'][kind]:
                self.diagnostic('relationship-not-matching-claim-arrays', path)
            edge = (kind, *sorted([start, end])) if kind == 'conflicts_with' else (kind, start, end)
            if edge in edges:
                self.diagnostic('duplicate-explicit-relationship', path)
            edges.add(edge)

    def finish(self, final, changed):
        diagnostics = sorted({encoded(d): d for d in self.diagnostics}.values(), key=encoded)
        complete = not self.inventory.issues and not final.issues and not changed
        blockers = diagnostics  # Nothing here authorizes integration, even on exact v1 data.
        operation_blocked = any(d['scope'] in ['operation', 'inspection'] for d in diagnostics)
        mode = ('integration-blocked' if operation_blocked else
                'read-only-compatibility-inspection' if self.manifest['classification'] != 'exact-v1-declaration' and self.inventory.entries
                else 'read-only-source-analysis')
        return {'command': 'inspect-compatibility', 'inspection_format': 'existing-knowledge-compatibility',
            'inspection_version': '1.0', 'ok': complete, 'complete': complete,
            'scope': '.ai only; source files outside .ai are not read',
            'repository_snapshot_fingerprint': self.inventory.snapshot(),
            'final_snapshot_fingerprint': final.snapshot(),
            'fingerprint_scope': 'bounded .ai inventory paths/types/content hashes; not whole-host or excluded bytes',
            'integration_approved': False, 'canonical_validation_performed': False,
            'manifest': self.manifest, 'schema_declarations': sorted(self.schema_declarations, key=encoded),
            'inventory': self.inventory.entries,
            'inventory_summary': {'entries': len(self.inventory.entries), 'content_bytes_hashed': self.inventory.total,
                'by_type': dict(sorted(Counter(e['type'] for e in self.inventory.entries).items())),
                'by_role': dict(sorted(Counter(e['role'] for e in self.inventory.entries).items())),
                'structured_records_recognized': len(self.records)},
            'recognized_capabilities': sorted(self.capabilities),
            'provisional_ownership': {'default': 'unknown-provisional', 'framework_ownership_inferred': False,
                'all_existing_content_preserved': True, 'disposable_paths': []},
            'graph_tools': sorted(self.tools.values(), key=encoded),
            'diagnostics': diagnostics, 'blockers': blockers,
            'unresolved_human_decisions': ['Identify knowledge/tool owners and approve any proposed integration scope.',
                'Select exactly one responsible graph builder; preserve canonical versus declared-preview trust boundaries.',
                'Review unsupported schemas, IDs, references, lifecycle, provenance and transaction state without conversion.',
                'Classify generated/state content before any future write or cleanup; no disposal is authorized.'],
            'suggested_integration_mode': mode,
            'limitations': ['No integration, migration approval, canonical conversion or status changes.',
                'Only strict bounded JSON objects and explicit Harbor revision 3 fields are analyzed; YAML/prose/scripts are not interpreted.',
                'Graph discovery is declarations plus filename heuristics; undeclared or obfuscated tools may be missed.',
                'Structural field diagnostics are not full dataset validation, semantic truth or authority verification.',
                'Stable trusted tree required; portable checks detect observable races, not hostile same-user path swaps.',
                'Native Windows/NTFS acceptance remains open.']}
