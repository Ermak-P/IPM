"""Disposable deterministic views. Contract v1 records remain the only authority."""
from collections import Counter
from copy import deepcopy
import os
from pathlib import Path
import tempfile

from population_dotnet import DotNetAnalyzer, canonical_json, EXPRESSION, safe_relative
from population_normalize import (CandidateNormalizer, canonical_source, digest,
                                  load_canonical, validate_records)
from population_scan import RepositoryScanner
from population_transaction import (PopulationError, PopulationStore, normal_operation,
                                    regular, require)

VERSION = 'derived-graph-v1'


class GraphInputError(PopulationError):
    def __init__(self, code, details):
        super().__init__(code)
        self.details = details


def identity(kind, key):
    return kind + '.' + digest(key)


def ordered(values):
    return sorted({canonical_json(v): v for v in values}.values(), key=canonical_json)


class Graph:
    def __init__(self, view):
        self.view, self.nodes, self.edges = view, {}, {}

    def node(self, identifier, kind, data, sources=(), claims=(), evidence=(), provenance=()):
        self.nodes[identifier] = dict(id=identifier, kind=kind, data=deepcopy(data),
            source_references=ordered(sources), supporting_claim_ids=sorted(set(claims)),
            supporting_evidence_ids=sorted(set(evidence)), provenance=ordered(provenance))
        return identifier

    def edge(self, kind, start, end, *, key=None, metadata=None, sources=(), claims=(),
             evidence=(), provenance=(), relationships=(), directed=True):
        if not directed:
            start, end = sorted([start, end])
        identifier = identity('derived/edge', [self.view, kind, start, end, key])
        value = dict(id=identifier, kind=kind, **{'from': start, 'to': end},
                     directed=directed, metadata=metadata or {},
                     source_references=ordered(sources), supporting_claim_ids=sorted(set(claims)),
                     supporting_evidence_ids=sorted(set(evidence)), provenance=ordered(provenance),
                     canonical_relationship_ids=sorted(set(relationships)))
        if identifier in self.edges:
            old = self.edges[identifier]
            for field in ['source_references', 'supporting_claim_ids', 'supporting_evidence_ids',
                          'provenance', 'canonical_relationship_ids']:
                value[field] = ordered(old[field] + value[field])
        self.edges[identifier] = value

    def finish(self):
        return dict(graph_version=VERSION, view=self.view,
            authority=('validated-canonical-records' if self.view == 'canonical'
                       else 'noncanonical-technical-observation-preview'),
            semantic_truth_established=False,
            dependency_interpretation=('explicit-claim-dependencies-only' if self.view == 'canonical'
                                       else 'declared-not-evaluated; runtime-dependencies-unknown'),
            nodes=sorted(self.nodes.values(), key=lambda n: n['id']),
            edges=sorted(self.edges.values(), key=lambda e: e['id']))


def canonical_graph(records):
    graph = Graph('canonical')
    for group, kind in [('claims', 'claim'), ('evidence', 'evidence')]:
        for record in records[group]:
            sources = ([{'reference': canonical_source(record)}] if kind == 'evidence' else [])
            graph.node(record['id'], kind, record, sources, claims=[record['id']] if kind == 'claim' else [],
                       evidence=[record['id']] if kind == 'evidence' else [], provenance=[record['provenance']])
            actor = graph.node(identity('derived/provenance', record['provenance']), 'provenance', record['provenance'])
            graph.edge('has_provenance', record['id'], actor, provenance=[record['provenance']])
            if kind == 'evidence':
                source = canonical_source(record)
                target = graph.node(identity('derived/source', source), 'source_reference', {'reference': source})
                graph.edge('references_source', record['id'], target, sources=sources, evidence=[record['id']])
                for claim in record['substantiates']:
                    graph.edge('substantiates', record['id'], claim, evidence=[record['id']], claims=[claim],
                               metadata={'evidence_status': record['status']})
    relations = {}
    for relation in records['relationships']:
        key = (relation['type'], *(sorted([relation['from'], relation['to']])
                if relation['type'] == 'conflicts_with' else [relation['from'], relation['to']]))
        relations.setdefault(key, []).append(relation)
    for claim in records['claims']:
        for evidence in claim['evidence']:
            graph.edge('cites_evidence', claim['id'], evidence, claims=[claim['id']], evidence=[evidence])
        for kind in ['depends_on', 'conflicts_with']:
            for target in claim[kind]:
                start, end = sorted([claim['id'], target]) if kind == 'conflicts_with' else [claim['id'], target]
                support = relations.get((kind, start, end), [])
                graph.edge(kind, start, end, directed=kind != 'conflicts_with', claims=[start, end],
                           relationships=[r['id'] for r in support],
                           provenance=[r['provenance'] for r in support],
                           metadata={'semantics': 'canonical-claim-relationship'})
    return graph.finish()


def technical_graph(extraction, normalized):
    graph = Graph('technical-preview')
    contexts = {c['extraction_ids'][0]: c for c in normalized['contexts']}
    def project(path):
        return identity('observed.project', path)
    for candidate in extraction['candidates']:
        if candidate['kind'] == 'project':
            graph.node(project(candidate['source']), 'observed_project',
                       {'path': candidate['source'], **candidate['value'], 'existence': 'observed-file'},
                       sources=candidate['evidence'], provenance=[e['provenance'] for e in candidate['evidence']])
    for source in extraction['scan']['sources']:
        if source['kind'] in ['dotnet-solution', 'dotnet-solution-xml']:
            graph.node(identity('observed.solution', source['path']), 'observed_solution',
                       {'path': source['path'], 'existence': 'inventory-file'},
                       sources=[{'source': source['path'], 'method': 'scanner-inventory'}])
    for candidate in extraction['candidates']:
        kind, value, source = candidate['kind'], candidate['value'], candidate['source']
        context = contexts[candidate['id']]
        if kind == 'project':
            graph.nodes[project(source)]['proposed_claim_ids'] = [context['claim_id']]
            graph.nodes[project(source)]['proposed_evidence_ids'] = [context['evidence_id']]
            continue
        metadata = {'interpretation': 'declared-not-evaluated', 'conditions': candidate['conditions'],
                    'resolution': context['resolution'], 'active_evaluated_dependency':
                    'unknown' if kind == 'project_reference' else 'not-applicable',
                    'declared_value': context['declared_value'],
                    'extraction_ids': context['extraction_ids'],
                    'proposed_claim_ids': [context['claim_id']],
                    'proposed_evidence_ids': [context['evidence_id']]}
        start = project(source)
        if kind in ['project_reference', 'solution_membership']:
            target = value.get('target')
            end = project(target) if target else None
            if end not in graph.nodes:
                end = graph.node(identity('observed.unresolved', [source, kind, context['subject']]),
                    'unresolved_project_reference', {'target': target, 'resolution': context['resolution'],
                                                     'existence': 'not-established'})
            if kind == 'solution_membership':
                start = identity('observed.solution', source)
            edge_kind = 'declared_project_reference' if kind == 'project_reference' else 'declared_solution_membership'
        elif kind in ['package_reference', 'package_version']:
            end = graph.node(identity('observed.package', value['include']), 'declared_package',
                             {'include': value['include'], 'availability': 'unknown'})
            edge_kind = 'declared_' + kind
        else:
            end = graph.node(identity('observed.property', [context['subject'], context['declared_value']]),
                'target_framework_declaration' if value['name'] in ['TargetFramework', 'TargetFrameworks']
                else 'project_property_declaration', context['declared_value'])
            edge_kind = 'declared_project_property'
        graph.edge(edge_kind, start, end, key=context['claim_id'], metadata=metadata,
                   sources=candidate['evidence'], provenance=[e['provenance'] for e in candidate['evidence']])
    return graph.finish()


def connectivity(graph, kinds=None):
    ids = {n['id'] for n in graph['nodes'] if kinds is None or n['kind'] in kinds}
    adjacent = {key: set() for key in ids}
    for edge in graph['edges']:
        if edge['from'] in ids and edge['to'] in ids:
            adjacent[edge['from']].add(edge['to'])
            adjacent[edge['to']].add(edge['from'])
    remaining, components = set(ids), []
    while remaining:
        pending, component = [min(remaining)], set()
        while pending:
            node = pending.pop()
            if node not in component:
                component.add(node)
                pending.extend(adjacent[node] - component)
        remaining -= component
        components.append(sorted(component))
    return {'nodes': len(ids), 'weak_components': sorted(components),
            'isolated_node_ids': sorted(key for key in ids if not adjacent[key])}


def distribution(records, key):
    return dict(sorted(Counter(record[key] for record in records).items()))


class GraphBuilder:
    """Public guarded API; no canonical writes. Default view is canonical only."""
    def build(self, root, view='canonical', exclusions=()):
        require(view in ['canonical', 'technical-preview'], 'unsupported-graph-view')
        require(view != 'canonical' or not exclusions, 'canonical-view-does-not-use-exclusions')
        with normal_operation(root):
            data = self._read(root, view == 'technical-preview', exclusions)
            graph = canonical_graph(data['records']) if view == 'canonical' else technical_graph(
                data['extraction'], data['normalized'])
            self._unchanged(data)
            return {'command': 'build', 'ok': True, 'graph': graph, 'validation': data['validation']}

    def _read(self, root, technical, exclusions):
        store = PopulationStore(root)
        before = store.canonical_snapshot()
        records = load_canonical(store.base)
        validation = validate_records(store.base, records)
        if not validation['ok']:
            raise GraphInputError('invalid-canonical-dataset-run-validate', {'validation': validation})
        data = dict(store=store, before=before, records=records, validation=validation)
        if technical:
            inventory = RepositoryScanner().scan(store.root, exclusions)
            extraction = DotNetAnalyzer().extract(store.root, inventory)
            if not extraction['ok']:
                raise GraphInputError('technical-extraction-incomplete-run-extract',
                    {'validation': validation, 'scan': inventory, 'diagnostics': extraction['diagnostics']})
            normalized = CandidateNormalizer().normalize(store.root, extraction)
            if not normalized['ok']:
                raise GraphInputError('normalization-invalid-run-normalize',
                    {'validation': normalized['validation'], 'diagnostics': normalized['diagnostics']})
            data.update(extraction=extraction, normalized=normalized)
        return data

    def _unchanged(self, data):
        require(data['store'].canonical_snapshot() == data['before'], 'canonical-changed-during-read-retry')
        if 'extraction' in data:
            original = data['extraction']
            current = DotNetAnalyzer().extract(data['store'].root,
                RepositoryScanner().scan(data['store'].root, original['scan']['exclusions']))
            require(canonical_json(current) == canonical_json(original), 'sources-changed-during-read-retry')
            require(data['store'].canonical_snapshot() == data['before'], 'canonical-changed-during-read-retry')

    def report(self, root, exclusions=()):
        with normal_operation(root):
            data = self._read(root, True, exclusions)
            records, normalized, extraction = data['records'], data['normalized'], data['extraction']
            canonical = canonical_graph(records)
            preview = technical_graph(extraction, normalized)
            evidence = {e['id']: e for e in records['evidence']}
            insufficient = []
            for claim in records['claims']:
                allowed = ['direct-authoritative'] if claim['type'] == 'business_rule' else ['direct-authoritative', 'direct-technical']
                support = [evidence[e] for e in claim['evidence'] if evidence[e]['status'] == 'active'
                    and evidence[e]['type'] in allowed and evidence[e].get('location')
                    and claim['id'] in evidence[e]['substantiates']]
                if claim['status'] != 'CONFIRMED' or not claim['last_verified'] or not support:
                    insufficient.append(claim['id'])
            dependencies = [e for e in preview['edges'] if e['kind'] == 'declared_project_reference']
            # Source checks use only hashes already safely observed by the analyzer.
            observed = {e['source']: e['content_hash'] for c in extraction['candidates'] for e in c['evidence']}
            freshness = []
            for item in records['evidence']:
                source = canonical_source(item)
                status = ('not-observed-removed-excluded-unsupported-or-external' if source not in observed
                          else 'hash-unavailable' if not item.get('content_hash')
                          else 'matches-observed-hash' if item['content_hash'] == observed[source]
                          else 'stale-content-hash')
                missing = (isinstance(source, str) and safe_relative(source)
                    and source not in observed
                    and not any(entry['path'] == source for entry in extraction['scan']['sources'])
                    and not any(source == entry['path'] or source.startswith(entry['path'] + '/')
                                for entry in extraction['scan']['skipped']))
                freshness.append({'evidence_id': item['id'], 'source': source,
                                  'evidence_status': item['status'], 'observation': status,
                                  'missing_from_current_inventory': missing})
            result = {'command': 'report', 'report_version': 'derived-report-v1', 'ok': True,
                'canonical': {'authority': canonical['authority'],
                    'claims': {'total': len(records['claims']), 'by_type': distribution(records['claims'], 'type'),
                               'by_status': distribution(records['claims'], 'status')},
                    'evidence': {'total': len(records['evidence']), 'by_type': distribution(records['evidence'], 'type'),
                                 'by_status': distribution(records['evidence'], 'status')},
                    'claims_without_sufficient_verification': sorted(insufficient),
                    'explicit_unresolved_conflicts': [e for e in canonical['edges'] if e['kind'] == 'conflicts_with'],
                    'source_evidence_observations': sorted(freshness, key=lambda e: e['evidence_id']),
                    'connectivity': connectivity(canonical), 'claim_connectivity': connectivity(canonical, {'claim'})},
                'technical_observations': {'authority': preview['authority'],
                    'interpretation': preview['dependency_interpretation'],
                    'project_count': sum(n['kind'] == 'observed_project' for n in preview['nodes']),
                    'solution_count': sum(n['kind'] == 'observed_solution' for n in preview['nodes']),
                    'declared_direct_project_dependencies': dependencies,
                    'conditional_dependencies': [e['id'] for e in dependencies if e['metadata']['conditions']],
                    'unresolved_dependencies': [e['id'] for e in dependencies if e['metadata']['resolution'] != 'discovered'
                        or EXPRESSION.search(canonical_json(e['metadata']['declared_value']))],
                    'discovered_sources': extraction['scan']['sources'], 'skipped_inputs': extraction['scan']['skipped'],
                    'diagnostics': extraction['diagnostics'], 'extracted_facts': extraction['counts']['candidates'],
                    'connectivity': connectivity(preview),
                    'project_connectivity': connectivity(preview, {'observed_project'})},
                'comparison': {'proposals_only': True, 'change_set': normalized['change_set'],
                    'classification_counts': distribution(normalized['change_set'], 'classification'),
                    'diagnostics': normalized['diagnostics'],
                    'acceptance': 'No review decisions are inferred; candidates are neither accepted nor rejected by reporting.'},
                'validation': {'canonical': data['validation'], 'normalization': normalized['validation']},
                'warnings': ['Structural validation does not establish semantic truth or evidence freshness.',
                    'Technical dependencies are declared, never evaluated or confirmed runtime dependencies.',
                    'Missing observations can be excluded, unsupported or external; no source is fetched.',
                    'Natural-language canonical claims are not interpreted; discrepancy detection is limited to normalization comparisons.'],
                'errors': []}
            self._unchanged(data)
            return result


def human_report(report):
    canonical, technical = report['canonical'], report['technical_observations']
    return '\n'.join([
        'Canonical knowledge (structurally validated; semantic truth not established)',
        f"Claims: {canonical['claims']['total']}; by type: {canonical['claims']['by_type']}; by status: {canonical['claims']['by_status']}",
        f"Evidence: {canonical['evidence']['total']}; by status: {canonical['evidence']['by_status']}",
        f"Claims needing verification: {len(canonical['claims_without_sufficient_verification'])}; explicit conflicts: {len(canonical['explicit_unresolved_conflicts'])}",
        f"Source evidence observations: {dict(Counter(e['observation'] for e in canonical['source_evidence_observations']))}",
        f"Canonical claim components: {len(canonical['claim_connectivity']['weak_components'])}; isolated claims: {len(canonical['claim_connectivity']['isolated_node_ids'])}",
        'Technical observations (NONCANONICAL PREVIEW; declared, not evaluated)',
        f"Solutions: {technical['solution_count']}; projects: {technical['project_count']}; declared direct project references: {len(technical['declared_direct_project_dependencies'])}",
        f"Conditional references: {len(technical['conditional_dependencies'])}; unresolved references: {len(technical['unresolved_dependencies'])}; skipped inputs: {len(technical['skipped_inputs'])}",
        f"Comparison classifications (proposals only): {report['comparison']['classification_counts']}",
        f"Validation: canonical={report['validation']['canonical']['ok']}; normalization={all(v['ok'] for v in report['validation']['normalization'].values())}",
        *['Warning: ' + warning for warning in report['warnings']]]) + '\n'


def save_generated(root, filename, payload):
    """Only fixed disposable filenames; reject links/hardlinks/unexpected objects."""
    require(filename in ['canonical-graph.json', 'technical-preview-graph.json', 'knowledge-report.json'],
            'unsupported-generated-artifact')
    with normal_operation(root):
        store = PopulationStore(root)
        directory = store.base / 'generated'
        if not directory.exists():
            directory.mkdir()
        require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(),
                'unsafe-generated-directory')
        target = directory / filename
        if target.exists() or target.is_symlink():
            regular(target, True)
        data = (canonical_json(payload) + '\n').encode('utf-8')
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.graph-', suffix='.tmp', dir=directory)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists():
                regular(target, True)
            os.replace(temporary, target)
        finally:
            if temporary is not None and Path(temporary).exists():
                Path(temporary).unlink()
    return '.ai/generated/' + filename
