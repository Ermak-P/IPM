"""Read-only proposals using Contract v1 and its existing validator."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

import kb
from population_dotnet import DotNetAnalyzer, EXPRESSION, canonical_json, safe_relative
from population_scan import RepositoryScanner, SOURCE_KINDS

GROUPS = {'claims': 'knowledge/claims', 'evidence': 'evidence',
          'relationships': 'knowledge/relationships'}
ACTOR = 'dotnet-candidate-normalizer'
METHOD = 'static-dotnet-normalization-v1'
KINDS = {'project', 'project_property', 'project_reference', 'package_reference',
         'package_version', 'solution_membership'}
OWN_ID = re.compile(r'^(claim|evidence)\.dotnet\.([a-f0-9]{64})\.([a-f0-9]{64})$')


def empty_records():
    return {group: [] for group in GROUPS}


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def load_canonical(base):
    kb.check_paths(base)
    records = empty_records()
    for group, directory in GROUPS.items():
        if not (base / directory).is_dir():
            raise ValueError('missing-canonical-record-directory')
        for path in sorted((base / directory).rglob('*')):
            if path.is_file() and path.name != '.gitkeep':
                if path.suffix != '.json':
                    raise ValueError('unsupported-canonical-record-format')
                records[group].append(kb.read_json(path))
    return records


def validate_records(base, records):
    """Run the *unmodified* core validator on an isolated temporary dataset."""
    with tempfile.TemporaryDirectory(prefix='kb-normalize-') as temporary:
        staging = Path(temporary) / '.ai'
        for directory in ['schema', *GROUPS.values()]:
            (staging / directory).mkdir(parents=True, exist_ok=True)
        for name in ['manifest.yaml', *(f'schema/{kind}.schema.json'
                                       for kind in ['claim', 'evidence', 'relationship'])]:
            (staging / name).write_bytes((base / name).read_bytes())
        for group, directory in GROUPS.items():
            for index, record in enumerate(sorted(records[group], key=canonical_json)):
                # Input IDs never become filesystem paths.
                (staging / directory / f'record-{index:06}.json').write_text(
                    canonical_json(record), encoding='utf-8')
        try:
            errors, warnings = kb.validate(staging)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error) as error:
            errors, warnings = [type(error).__name__ + ': staging validation failed'], []
        return {'ok': not errors, 'errors': sorted(set(errors)),
                'record_counts': {group: len(values) for group, values in records.items()},
                'warnings': sorted(set(warnings)), 'validator': 'Contract v1 kb.validate'}


def combine_preserving_existing(existing, proposed):
    """Validation context only, never an application plan or filesystem mutation."""
    identifiers = {r['id'] for values in existing.values() for r in values}
    return {group: deepcopy(existing[group]) +
            [deepcopy(r) for r in proposed[group] if r['id'] not in identifiers]
            for group in GROUPS}


def definition(candidate):
    """Exact declarations only; resolution is observation context, not claim truth."""
    kind, source = candidate['kind'], candidate['source']
    value = {key: item for key, item in candidate['value'].items()
             if key not in ['resolution', 'target']}
    conditions = list(candidate['conditions'])
    if kind == 'project':
        conditions = []  # XML evaluation conditions cannot make a file cease to exist.
        key = []
        statement = (f'Repository contains project file {json.dumps(source)}; '
                     f'its filename label is {json.dumps(value["name"])}.')
    elif kind == 'project_property':
        key = [value['name']]
        statement = (f'Project {json.dumps(source)} declares property {json.dumps(value["name"])} '
                     f'with value {json.dumps(value["declared"])}.')
    elif kind == 'project_reference':
        key = [value['include']]
        # A declaration does not prove target existence or evaluated dependency.
        statement = (f'Project {json.dumps(source)} declares a ProjectReference '
                     f'with Include {json.dumps(value["include"])}.')
    elif kind == 'package_reference':
        key = [value['include']]
        statement = (f'Project {json.dumps(source)} declares a PackageReference '
                     f'with Include {json.dumps(value["include"])}.')
    elif kind == 'package_version':
        key = [value['include'], value['name']]
        statement = (f'Project {json.dumps(source)} declares PackageReference '
                     f'{json.dumps(value["include"])} metadata {json.dumps(value["name"])} '
                     f'with value {json.dumps(value["declared"])}.')
    elif kind == 'solution_membership':
        key = [value['declared_path']]
        statement = (f'Solution {json.dumps(source)} declares project membership '
                     f'{canonical_json(value)}.')
    else:
        raise ValueError('unsupported-candidate-kind')
    if kind != 'project':
        statement += ' Conditions (not evaluated): ' + canonical_json(conditions) + '.'
    subject = {'kind': kind, 'source': source, 'key': key, 'conditions': conditions}
    return subject, value, statement


def canonical_source(record):
    source = record.get('source')
    return source.get('reference') if isinstance(source, dict) else source


class CandidateNormalizer:
    def normalize(self, root, extraction):
        return _Normalization(root, extraction).run()


class _Normalization:
    def __init__(self, root, extraction):
        self.root = Path(root)
        self.extraction = extraction
        self.records = empty_records()
        self.contexts = {}
        self.diagnostics = []
        self.validation = {}
        self.observed_at = None

    def diagnostic(self, code, **details):
        self.diagnostics.append(dict(code=code, **details))

    def run(self):
        try:
            if self.root.is_symlink() or self.root.is_junction() or not self.root.is_dir():
                raise ValueError('invalid-root')
            base = self.root.resolve() / '.ai'
            try:
                self.existing = load_canonical(base)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.validation['existing'] = {'ok': False,
                    'errors': ['Unable to read canonical snapshot; missing, malformed or linked records.'],
                    'warnings': []}
                return self.finish([])
            self.validation['existing'] = validate_records(base, self.existing)
            if not self.validation['existing']['ok']:
                self.diagnostic('invalid-existing-canonical-dataset', severity='error')
                return self.finish([])
            # Never trust a saved/tampered extraction as a new observation.
            if (not isinstance(self.extraction, dict)
                    or self.extraction.get('command') != 'extract'
                    or self.extraction.get('ok') is not True):
                raise ValueError('invalid-or-incomplete-extraction')
            inventory = self.extraction['scan']
            current = DotNetAnalyzer().extract(
                self.root, RepositoryScanner().scan(self.root, inventory['exclusions']))
            if not current['ok'] or canonical_json(current) != canonical_json(self.extraction):
                raise ValueError('extraction-not-current-or-not-authentic-to-local-analyzer')
            self.observed_at = utc_now()  # Real completed re-observation, never an approval event.
            for candidate in current['candidates']:
                self.add(candidate)
            self.diagnostic('active-evaluated-dependencies-unknown')
            self.diagnostic('no-canonical-dependency-relationships',
                            reason='v1 depends_on links claims, not projects; declaration edges retained in context')
            for item in current['diagnostics']:
                self.diagnostic('extractor-diagnostic', diagnostic=item)
            changes = self.compare(current)
            for group in GROUPS:
                self.records[group].sort(key=lambda record: record['id'])
            self.validation['proposed'] = validate_records(base, self.records)
            self.validation['combined_preserving_existing'] = validate_records(
                base, combine_preserving_existing(self.existing, self.records))
            return self.finish(changes)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            # No OS paths, source contents or untrusted exception strings in diagnostics.
            known = str(error) if type(error) is ValueError else 'normalization-input-or-read-error'
            if known not in {'invalid-root', 'invalid-or-incomplete-extraction',
                             'extraction-not-current-or-not-authentic-to-local-analyzer',
                             'unsupported-candidate-kind', 'unsupported-canonical-record-format'}:
                known = 'normalization-input-or-read-error'
            self.diagnostic(known, severity='error')
            return self.finish([])

    def add(self, candidate):
        kind = candidate['kind']
        if kind not in KINDS:
            raise ValueError('unsupported-candidate-kind')
        subject, value, statement = definition(candidate)
        slot, fact = digest(subject), digest(value)
        claim_id = f'claim.dotnet.{slot}.{fact}'
        evidence_id = f'evidence.dotnet.{slot}.{fact}'
        occurrences = candidate['evidence']
        if (not occurrences or any(e['source'] != candidate['source'] or not e.get('location')
                                   or not e.get('content_hash') for e in occurrences)):
            raise ValueError('invalid-candidate-evidence')
        locations = sorted({canonical_json(e['location']): e['location']
                            for e in occurrences}.values(), key=canonical_json)
        evidence = {
            'id': evidence_id, 'type': 'direct-technical', 'status': 'active',
            'source': candidate['source'],
            'provenance': {'actor': occurrences[0]['provenance']['actor'],
                           'method': occurrences[0]['provenance']['method'] +
                           '; ' + METHOD + '; live source observation'},
            'captured_at': self.observed_at,
            'location': {'reference': candidate['source'] + '#locations=' + canonical_json(locations)},
            'description': 'Static source observation supporting the narrow declaration: ' + statement,
            'content_hash': occurrences[0]['content_hash'], 'substantiates': [claim_id]}
        claim = {'id': claim_id, 'statement': statement, 'type': 'technical_fact',
                 'status': 'NEEDS_HUMAN_CONFIRMATION', 'evidence': [evidence_id],
                 'provenance': {'actor': ACTOR, 'method': METHOD},
                 'last_verified': None, 'depends_on': [], 'conflicts_with': []}
        context = {'claim_id': claim_id, 'evidence_id': evidence_id, 'subject': subject,
                   'declared_value': value, 'extraction_ids': [candidate['id']],
                   'conditions': subject['conditions'],
                   'source': candidate['source'], 'kind': kind,
                   'active_evaluated_dependency': 'unknown' if kind == 'project_reference' else 'not-applicable',
                   'resolution': candidate['value'].get('resolution', 'not-applicable')}
        if kind in ['project_reference', 'solution_membership']:
            context['resolved_target'] = candidate['value'].get('target')
        if kind == 'project':
            context['file_existence'] = 'observed-source-file'
            context['declared_xml_conditions'] = candidate['conditions']
        if claim_id not in self.contexts:
            self.records['claims'].append(claim)
            self.records['evidence'].append(evidence)
            self.contexts[claim_id] = context
        else:
            old = self.contexts[claim_id]
            old['extraction_ids'] = sorted(set(old['extraction_ids'] + context['extraction_ids']))
            self.diagnostic('equivalent-fact-deduplicated', id=claim_id)

    def compare(self, current):
        existing = {r['id']: (group, r) for group in GROUPS for r in self.existing[group]}
        proposed = {r['id']: (group, r) for group in GROUPS for r in self.records[group]}
        slots = {}
        for claim_id, context in self.contexts.items():
            slot = OWN_ID.fullmatch(claim_id)[2]
            slots.setdefault(slot, []).append(claim_id)
        prior_slots = {}
        for claim in self.existing['claims']:
            match = OWN_ID.fullmatch(claim['id'])
            if match and match[1] == 'claim':
                prior_slots.setdefault(match[2], []).append(claim)
        changes = {}
        for identifier, (group, record) in sorted(proposed.items()):
            claim_id = identifier if group == 'claims' else record['substantiates'][0]
            context = self.contexts[claim_id]
            slot = OWN_ID.fullmatch(claim_id)[2]
            classification, reasons, related = 'add', [], []
            if identifier in existing:
                old_group, old = existing[identifier]
                equal = old_group == group and (
                    {k: v for k, v in old.items() if k != 'captured_at'} ==
                    {k: v for k, v in record.items() if k != 'captured_at'})
                if equal:
                    classification = 'unchanged'
                    if group == 'evidence':
                        record['captured_at'] = old['captured_at']  # Reuse a retained observation.
                elif (group == old_group == 'evidence' and old['status'] == 'active'
                      and old['type'] == record['type']
                      and old['provenance'] == record['provenance']
                      and old['substantiates'] == record['substantiates']):
                    classification, reasons = 'potential update', ['source-observation-refresh']
                else:
                    classification, reasons = 'conflict', ['preserve-existing-record']
                related.append(identifier)
            others = [r for r in prior_slots.get(slot, []) if r['id'] != claim_id]
            if others:
                classification = ('conflict' if any(r['status'] == 'CONFIRMED' or
                                  r['provenance']['actor'] != ACTOR for r in others)
                                  else 'potential update')
                reasons.append('different-canonical-value-for-subject')
                related.extend(r['id'] for r in others)
            if len(slots[slot]) > 1:
                classification = 'conflict'
                reasons.append('multiple-declared-values-no-evaluation')
                related.extend(slots[slot])
            for canonical in self.existing['claims']:
                if canonical['id'] == claim_id or OWN_ID.fullmatch(canonical['id']):
                    continue
                overlap = (canonical['statement'] == self.context_statement(claim_id) or any(
                    canonical_source(e) == context['source'] and e['id'] in canonical['evidence']
                    for e in self.existing['evidence']))
                if overlap:
                    if classification in ['add', 'unchanged']:
                        classification = 'unresolved'
                    reasons.append('uninterpreted-canonical-overlap')
                    related.append(canonical['id'])
            if (context['resolution'] not in ['not-applicable', 'discovered'] or
                    EXPRESSION.search(canonical_json(
                        [context['declared_value'], context['conditions']]))):
                if classification == 'add':
                    classification = 'unresolved'
                reasons.append('unresolved-declaration-or-reference')
            changes[identifier] = {'id': identifier, 'record_type': group,
                                   'classification': classification,
                                   'reasons': sorted(set(reasons)), 'related_ids': sorted(set(related))}
        observed_hashes = {e['source']: e['content_hash']
                           for c in current['candidates'] for e in c['evidence']}
        stale_evidence = set()
        for identifier, (group, record) in sorted(existing.items()):
            if identifier in changes:
                continue
            reason = None
            if group == 'evidence':
                source = canonical_source(record)
                if isinstance(source, str) and safe_relative(source) and Path(source).suffix.lower() in SOURCE_KINDS:
                    if source not in observed_hashes:
                        reason = 'source-not-observed-removed-excluded-or-unsupported'
                    elif record.get('content_hash') and record['content_hash'] != observed_hashes[source]:
                        reason = 'source-hash-changed-evidence-needs-review'
                if reason:
                    stale_evidence.add(identifier)
            if OWN_ID.fullmatch(identifier):
                reason = reason or 'declaration-no-longer-proposed-potentially-superseded'
            changes[identifier] = {'id': identifier, 'record_type': group,
                                   'classification': 'unresolved' if reason else 'unchanged',
                                   'reasons': [reason] if reason else ['existing-record-retained'],
                                   'related_ids': []}
        for claim in self.existing['claims']:
            affected = sorted(set(claim['evidence']) & stale_evidence)
            if affected:
                entry = changes[claim['id']]
                if entry['classification'] == 'unchanged':
                    entry['classification'] = 'unresolved'
                entry['reasons'] = sorted(set(entry['reasons'] + ['potentially-stale-supporting-evidence']))
                entry['related_ids'] = sorted(set(entry['related_ids'] + affected))
        for entry in changes.values():
            if entry['classification'] in ['conflict', 'unresolved', 'potential update']:
                self.diagnostic('proposal-requires-review', **entry)
        return sorted(changes.values(), key=lambda item: (item['record_type'], item['id']))

    def context_statement(self, claim_id):
        return next(r['statement'] for r in self.records['claims'] if r['id'] == claim_id)

    def finish(self, changes):
        errors = any(d.get('severity') == 'error' for d in self.diagnostics)
        validation_ok = (len(self.validation) == 3 and
                         all(result['ok'] for result in self.validation.values()))
        return {
            'command': 'normalize', 'report_version': '1.0', 'ok': validation_ok and not errors,
            'observation': {'captured_at': self.observed_at,
                            'policy': 'actual UTC time after live extraction revalidation; never part of IDs or change_set'},
            'records': self.records,
            'contexts': sorted(self.contexts.values(), key=lambda item: item['claim_id']),
            'change_set': changes, 'validation': self.validation,
            'diagnostics': sorted({canonical_json(d): d for d in self.diagnostics}.values(),
                                  key=canonical_json),
            'counts': {group: len(records) for group, records in self.records.items()},
            'limitations': [
                'Structural validation does not prove semantic truth; all new claims require human confirmation.',
                'Project references do not become canonical claim depends_on relationships.',
                'Unknown human prose is not semantically interpreted; overlapping source evidence requires review.',
                'No canonical writes, approval or application; conflicts and stale observations remain proposals.',
                'Stable tree required; inherited metadata and active evaluated dependencies remain unknown.'
            ]}
