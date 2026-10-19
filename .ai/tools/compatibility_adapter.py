"""Read-only, versioned compatibility proposals. No migration or approval interface."""
from copy import deepcopy
from pathlib import Path
import os
import tempfile
from typing import Protocol
from urllib.parse import urlsplit

import kb
from compatibility_inspector import (CompatibilityInspector, Inventory, GROUPS,
    encoded, fingerprint, label, safe_path, ID)
from population_normalize import empty_records

MAX_TEXT = 4096
CLAIM_STATES = {'CONFIRMED', 'INFERRED', 'UNKNOWN', 'NEEDS_HUMAN_CONFIRMATION'}
EVIDENCE_STATES = {'active', 'retracted', 'superseded'}
TYPE_MAP = {'business-policy': 'business_rule', 'component-responsibility': 'architecture',
            'technical-fact': 'technical_fact'}
EVIDENCE_MAP = {'meeting-note': 'supporting', 'source-code': 'direct-technical',
                'supporting': 'supporting', 'derived': 'derived',
                'direct-technical': 'direct-technical', 'direct-authoritative': 'direct-authoritative'}
SCHEMA_KINDS = {'claims': 'claim', 'evidence': 'evidence', 'relationships': 'relationship'}


class Adapter(Protocol):
    profile: str
    def map_fields(self, group: str, value: dict) -> tuple[dict, list[dict]]: ...


class ContractV1Adapter:
    profile = 'contract-v1-verbatim'
    def map_fields(self, group, value):
        return deepcopy(value), []


class HarborRevision3Adapter:
    """Exact synthetic field rules; missing values are never synthesized."""
    profile = 'harbor-revision-3-explicit-fields-v1'
    def map_fields(self, group, value):
        issues, result = [], {}
        if group == 'relationships':
            issues = [{'code': 'unsupported-harbor-relationship-type'}]
            for key in sorted(set(value) - {'id', 'kind', 'source', 'target', 'provenance'}):
                issues.append({'code': 'unsupported-property-data-loss-risk', 'field': label(key),
                               'field_fingerprint': fingerprint(key)})
            return {}, issues
        if group == 'claims':
            names = {'id': 'id', 'kind': 'type', 'text': 'statement', 'state': 'status',
                'support': 'evidence', 'provenance': 'provenance', 'last_verified': 'last_verified',
                'depends_on': 'depends_on', 'conflicts_with': 'conflicts_with'}
            mapping = TYPE_MAP
        else:
            names = {'id': 'id', 'kind': 'type', 'state': 'status', 'uri': 'source',
                'provenance': 'provenance', 'captured_at': 'captured_at', 'location': 'location',
                'description': 'description', 'supports': 'substantiates', 'content_hash': 'content_hash'}
            mapping = EVIDENCE_MAP
        for key, target in names.items():
            if key in value:
                result[target] = deepcopy(value[key])
        kind = value.get('kind')
        if isinstance(kind, str) and kind in mapping:
            result['type'] = mapping[kind]
        else:
            issues.append({'code': 'unsupported-explicit-record-kind'})
        allowed = set(names) | ({'uri_base'} if group == 'evidence' else set())
        for key in sorted(set(value) - allowed):
            issues.append({'code': 'unsupported-property-data-loss-risk', 'field': label(key),
                           'field_fingerprint': fingerprint(key)})
        if group == 'evidence':
            uri = value.get('uri')
            if isinstance(uri, str):
                try:
                    scheme = urlsplit(uri).scheme.lower()
                except ValueError:
                    issues.append({'code': 'invalid-source-reference'})
                    scheme = 'invalid'
                if not scheme and (value.get('uri_base') != 'repository-root' or not safe_path(uri)):
                    issues.append({'code': 'ambiguous-or-unsafe-source-reference-base'})
                elif scheme and scheme not in ['https', 'http', 'urn']:
                    issues.append({'code': 'unsupported-source-reference-scheme'})
            else:
                issues.append({'code': 'unsupported-source-reference-form'})
            if 'uri_base' in value and value['uri_base'] != 'repository-root':
                issues.append({'code': 'unsupported-source-reference-base'})
        return result, issues


def nested_unsupported(value, schema, prefix=()):
    issues = []
    if 'anyOf' in schema:
        schema = next((s for s in schema['anyOf'] if s.get('type') == 'object' and isinstance(value, dict)), schema)
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        for key, nested in value.items():
            path = prefix + (key,)
            if key not in properties:
                issues.append({'code': 'unsupported-property-data-loss-risk', 'field': label(key),
                               'field_fingerprint': fingerprint(key), 'field_path_fingerprint': fingerprint(path)})
            else:
                issues.extend(nested_unsupported(nested, properties[key], path))
    elif isinstance(value, list):
        for nested in value:
            issues.extend(nested_unsupported(nested, schema.get('items', {}), prefix + ('[]',)))
    return issues


def staged_validation(root, records):
    # gettempdir() may itself probe/write candidate directories; select without probing.
    selected = tempfile.tempdir
    if selected is None:
        selected = next((os.environ[k] for k in ['TMPDIR', 'TEMP', 'TMP'] if os.environ.get(k)),
                        '/tmp' if os.name == 'posix' else str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Temp'))
    parent = Path(os.fsdecode(selected)).absolute()
    require(not parent.is_relative_to(root) and not parent.resolve().is_relative_to(root)
            and parent.is_dir(), 'no-safe-external-validation-staging')
    with tempfile.TemporaryDirectory(prefix='kb-adapter-validation-', dir=parent) as temporary:
        base = Path(temporary) / '.ai'
        for directory in ['schema', *['knowledge/claims', 'evidence', 'knowledge/relationships']]:
            (base / directory).mkdir(parents=True, exist_ok=True)
        for name in ['manifest.yaml', *['schema/' + k + '.schema.json' for k in SCHEMA_KINDS.values()]]:
            (base / name).write_bytes((kb.SOURCE / name).read_bytes())
        for group, prefix in GROUPS.items():
            for number, record in enumerate(sorted(records[group], key=lambda r: r['id'])):
                # Numeric filenames, never legacy IDs or input-controlled paths.
                (Path(temporary) / prefix / f'record-{number:06}.json').write_text(encoded(record), encoding='utf-8')
        errors, warnings = kb.validate(base)
        return {'ok': not errors, 'errors': sorted(set(errors)), 'warnings': sorted(set(warnings)),
                'record_counts': {g: len(v) for g, v in records.items()}, 'validator': 'Contract v1 kb.validate'}


def _checkpoint():
    """Test seam; no executable host hooks or CLI fault injection."""


def require(condition, code):
    if not condition:
        raise ValueError(code)


def proposed_id(group, original):
    if ID.fullmatch(original):
        return original
    return SCHEMA_KINDS[group] + '.legacy.harbor3.' + fingerprint(original).split(':')[1]


class CompatibilityAdapter:
    def propose(self, root, inspection=None):
        report = {'command': 'adapt-compatibility', 'proposal_format': 'read-only-compatibility-proposal',
            'proposal_version': '1.0', 'ok': False, 'mapping_attempted': False, 'integration_approved': False,
            'canonical_insertion_approved': False, 'semantic_acceptance_established': False,
            'records': empty_records(), 'id_mappings': [], 'blocked_mappings': [], 'unresolved_records': [],
            'diagnostics': [], 'validation': {}, 'metrics': {}, 'inspection': None,
            'graph_boundary': {'tools_executed': False, 'second_graph_pipeline_created': False,
                'requirements': ['Owner selects exactly one responsible existing builder before integration.',
                    'Input must distinguish validated canonical claims/evidence/claim relationships from nonauthoritative proposals.',
                    'Output must retain source, original/proposed IDs, provenance, lifecycle, conditions and unresolved diagnostics.',
                    'Component calls and declared project references must never be relabeled as canonical claim depends_on.',
                    'Owner agrees exact IO schemas, paths and trust labels; discovery/declarations do not authenticate ownership.']}}
        try:
            current = CompatibilityInspector().inspect(root)
            report['inspection'] = current
            require(current['ok'] and current['complete'], 'inspector-incomplete-proposal-refused')
            if inspection is not None:
                require(encoded(inspection) == encoded(current), 'inspection-stale-or-modified')
            require(not any(d['code'] == 'transaction-or-recovery-state-owner-review-required'
                            for d in current['diagnostics']), 'transaction-state-proposal-refused')
            inventory = Inventory(root).run()
            require(not inventory.issues and inventory.snapshot() == current['repository_snapshot_fingerprint'],
                    'inputs-changed-after-inspection')
            manifest = inventory.documents.get('.ai/manifest.yaml', {})
            native = manifest == kb.MANIFEST
            harbor = (manifest.get('format') == 'harbor-team-architecture'
                      and type(manifest.get('revision')) is int and manifest['revision'] == 3)
            require(native or harbor, 'unsupported-explicit-container-format')
            report['mapping_attempted'] = True
            self.map(inventory, harbor, report)
            _checkpoint()
            final = CompatibilityInspector().inspect(root)
            final_inventory = Inventory(root).run()
            require(encoded(final) == encoded(current) and not final_inventory.issues
                    and final_inventory.observations == inventory.observations,
                    'inputs-changed-during-proposal')
            report['ok'] = True
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            known = {'inspector-incomplete-proposal-refused', 'inspection-stale-or-modified',
                'transaction-state-proposal-refused', 'inputs-changed-after-inspection',
                'unsupported-explicit-container-format', 'inputs-changed-during-proposal',
                'no-safe-external-validation-staging'}
            code = str(error) if type(error) is ValueError and str(error) in known else 'adapter-input-or-validation-io-error'
            report['diagnostics'].append({'code': code})
            # Never expose a dataset that was not safely authenticated through the last check.
            report['records'] = empty_records()
            report['validation']['proposal_usable'] = False
            for item in report['id_mappings']:
                item['reasons'] = sorted(set(item['reasons'] + [code]))
                item['classification'] = 'blocked'
            self.finish_metrics(report)
        self.finish_metrics(report)
        return report

    def map(self, inventory, harbor, report):
        schemas = {g: kb.read_json(kb.SOURCE / 'schema' / (k + '.schema.json')) for g, k in SCHEMA_KINDS.items()}
        items = []
        for entry in inventory.entries:
            if entry['type'] != 'file' or entry['role'] not in GROUPS or Path(entry['path']).name == '.gitkeep':
                continue
            group, source = entry['role'], entry['path']
            value = inventory.documents.get(source)
            original = value.get('id') if value else None
            valid_identity = isinstance(original, str) and label(original) is not None
            adapter = HarborRevision3Adapter() if harbor and value and 'kind' in value else ContractV1Adapter()
            mapping = dict(source=source, source_content_hash=entry['content_fingerprint'],
                original_id=original if valid_identity else None,
                original_id_fingerprint=fingerprint(original) if original is not None else None,
                proposed_id=(proposed_id(group, original) if adapter.profile == HarborRevision3Adapter.profile
                             else original if ID.fullmatch(original) else None) if valid_identity else None,
                record_type=group, profile=adapter.profile,
                classification='blocked', reasons=[], original_lifecycle=label(value.get('state', value.get('status'))) if value else None,
                human_review_required=True,
                legacy_source_base=label(value.get('uri_base')) if value else None)
            record, issues = adapter.map_fields(group, value) if value else ({}, [{'code': 'unsupported-or-malformed-record-format'}])
            if valid_identity and adapter.profile == ContractV1Adapter.profile and not ID.fullmatch(original):
                issues.append({'code': 'native-id-not-v1-compatible-no-repair'})
            if not valid_identity:
                issues.append({'code': 'missing-invalid-or-over-limit-original-id'})
            allowed = set(schemas[group]['properties'])
            if adapter.profile == 'contract-v1-verbatim' and value:
                for key in sorted(set(value) - allowed):
                    issues.append({'code': 'unsupported-property-data-loss-risk', 'field': label(key),
                                   'field_fingerprint': fingerprint(key)})
            if mapping['proposed_id']:
                record['id'] = mapping['proposed_id']
            missing = sorted(set(schemas[group]['required']) - record.keys())
            if missing:
                issues.append({'code': 'missing-v1-required-fields', 'fields': missing})
            provenance = value.get('provenance') if value else None
            if value is None:
                issues.append({'code': 'provenance-unresolved-unsupported-format'})
            elif not isinstance(provenance, dict) or not all(isinstance(provenance.get(k), str) and provenance[k].strip() for k in ['actor', 'method']):
                issues.append({'code': 'missing-explicit-provenance'})
            if (group == 'relationships' and adapter.profile == ContractV1Adapter.profile and value
                    and 'type' in value and value['type'] not in ['depends_on', 'conflicts_with']):
                issues.append({'code': 'unsupported-native-relationship-type'})
            states = CLAIM_STATES if group == 'claims' else EVIDENCE_STATES if group == 'evidence' else None
            if states is not None and (not isinstance(record.get('status'), str) or record['status'] not in states):
                issues.append({'code': 'unsupported-lifecycle-no-conversion'})
            if group == 'evidence' and not record.get('captured_at'):
                issues.append({'code': 'missing-observation-timestamp-no-fabrication'})
            if group == 'claims' and record.get('status') == 'CONFIRMED' and not record.get('last_verified'):
                issues.append({'code': 'missing-verification-event-no-fabrication'})
            # Bound selected canonical text; report never contains complete arbitrary source files.
            for key in ['statement', 'description', 'source', 'location', 'provenance']:
                if key in record and len(encoded(record[key])) > MAX_TEXT:
                    issues.append({'code': 'selected-metadata-size-limit', 'field': key})
            item = dict(mapping=mapping, record=record, issues=issues, refs=[])
            items.append(item)
        original_index, proposed_index = {}, {}
        for item in items:
            mapping = item['mapping']
            if mapping['original_id'] is not None:
                original_index.setdefault(mapping['original_id'], []).append(item)
            if mapping['proposed_id'] is not None:
                proposed_index.setdefault(mapping['proposed_id'], []).append(item)
        for index, code in [(original_index, 'duplicate-original-id'), (proposed_index, 'proposed-id-collision')]:
            for matches in index.values():
                if len(matches) > 1:
                    for item in matches:
                        item['issues'].append({'code': code})
        for item in items:
            group, record = item['mapping']['record_type'], item['record']
            fields = ([('evidence', 'evidence'), ('depends_on', 'claims'), ('conflicts_with', 'claims')] if group == 'claims'
                      else [('substantiates', 'claims')] if group == 'evidence' else [('from', 'claims'), ('to', 'claims')])
            for field, expected in fields:
                if field not in record:
                    continue
                raw = record[field]
                scalar = field in ['from', 'to']
                if (scalar and not isinstance(raw, str)) or (not scalar and
                        (not isinstance(raw, list) or any(not isinstance(t, str) for t in raw))):
                    item['issues'].append({'code': 'invalid-reference-field-shape-no-repair', 'field': field})
                    continue
                targets = [raw] if scalar else raw
                resolved = []
                for target in targets:
                    matches = original_index.get(target, []) if isinstance(target, str) else []
                    if len(matches) != 1 or matches[0]['mapping']['record_type'] != expected:
                        item['issues'].append({'code': 'unresolved-missing-ambiguous-or-wrong-kind-reference',
                            'field': field, 'target_id': label(target), 'target_fingerprint': fingerprint(target)})
                        continue
                    linked = matches[0]
                    item['refs'].append(linked)
                    resolved.append(linked['mapping']['proposed_id'])
                if field in record:
                    # Missing references are not erased to manufacture a valid record.
                    if len(resolved) == len(targets) and all(resolved):
                        record[field] = resolved[0] if field in ['from', 'to'] and resolved else resolved
            for issue in nested_unsupported(record, schemas[group]):
                if issue not in item['issues']:
                    item['issues'].append(issue)
            errors = kb.schema_errors(record, schemas[group])
            if errors:
                item['issues'].append({'code': 'candidate-schema-errors', 'count': len(errors)})
        # Preserve closure: blocked evidence/claims are never emitted as dangling proposals.
        while True:
            affected = [i for i in items if not i['issues'] and any(r['issues'] for r in i['refs'])]
            if not affected:
                break
            for item in affected:
                item['issues'].append({'code': 'reference-closure-reaches-blocked-record'})
        report['id_mappings'] = [item['mapping'] for item in items]
        candidates = empty_records()
        for item in items:
            if not item['issues']:
                candidates[item['mapping']['record_type']].append(item['record'])
        # The existing validator creates temporary staging only outside the inspected host.
        root = inventory.root.resolve()
        attempted = staged_validation(root, candidates)
        report['validation']['attempted_reference_closed_dataset'] = attempted
        if not attempted['ok']:
            # Conservative PoC policy: do not guess which records to salvage from failed closure.
            for item in items:
                if not item['issues']:
                    item['issues'].append({'code': 'complete-dataset-validator-rejected'})
            candidates = empty_records()
        report['records'] = {g: sorted(values, key=lambda r: r['id']) for g, values in candidates.items()}
        report['validation']['proposed_dataset'] = (attempted if attempted['ok'] else staged_validation(root, candidates))
        report['validation']['proposal_usable'] = True  # Structurally checked, not approved for insertion.
        for item in items:
            mapping = item['mapping']
            mapping['reasons'] = sorted({d['code'] for d in item['issues']})
            mapping['classification'] = 'blocked' if item['issues'] else 'structurally-representable-proposal'
            for diagnostic in item['issues']:
                report['diagnostics'].append(dict(source=mapping['source'], **diagnostic))
        report['id_mappings'].sort(key=lambda m: (m['source'], m['record_type']))
        report['diagnostics'].sort(key=encoded)
        self.finish_metrics(report)

    @staticmethod
    def finish_metrics(report):
        mappings = report['id_mappings']
        blocked = [m for m in mappings if m['classification'] == 'blocked']
        report['blocked_mappings'] = deepcopy(blocked)
        report['unresolved_records'] = deepcopy(blocked)
        conflicts = {'native-id-not-v1-compatible-no-repair', 'invalid-reference-field-shape-no-repair', 'duplicate-original-id', 'proposed-id-collision', 'missing-invalid-or-over-limit-original-id',
                     'unresolved-missing-ambiguous-or-wrong-kind-reference', 'reference-closure-reaches-blocked-record'}
        report['metrics'] = {'legacy_records_inspected': len(mappings),
            'structurally_representable_records': sum(len(v) for v in report['records'].values()),
            'blocked_records': len(blocked), 'unresolved_mappings': len(blocked),
            'id_reference_conflicts': sum(bool(set(m['reasons']) & conflicts) for m in mappings),
            'missing_provenance': sum('missing-explicit-provenance' in m['reasons'] for m in mappings),
            'unsupported_relationship_types': sum(bool(set(m['reasons']) & {'unsupported-harbor-relationship-type', 'unsupported-native-relationship-type'}) for m in mappings),
            'candidates_passing_isolated_structural_validation': sum(len(v) for v in report['records'].values()) if report['validation'].get('proposal_usable') else 0,
            'records_requiring_human_review': len(mappings)}
        report['nonempty_candidates_validated'] = bool(report['metrics']['candidates_passing_isolated_structural_validation'])
        report['metrics_complete'] = report['ok']
        report['mapping_complete'] = report['ok'] and not blocked
        report['coverage_policy'] = 'Counts are structural compatibility only, never semantic correctness, source authority or integration GO.'
