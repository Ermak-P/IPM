"""Regenerate Increment E examples using only a disposable synthetic repository.

Usage: python -B .ai/tools/examples/graph_demo.py canonical|technical-preview|report|summary
The fixed captured_at below is synthetic fixture data, not a verification event.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb
from knowledge_graph import GraphBuilder, human_report


def example(mode):
    with tempfile.TemporaryDirectory(prefix='kb-graph-example-') as temporary:
        root = Path(temporary)
        errors = kb.init(root / '.ai')
        if errors:
            raise ValueError('Unable to initialize disposable example fixture')
        source = ('<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>'
                  '<ItemGroup><ProjectReference Include="B.csproj"/>'
                  '<PackageReference Include="Example" Version="1.2.3"/></ItemGroup></Project>')
        (root / 'A.csproj').write_text(source, encoding='utf-8')
        (root / 'B.csproj').write_text('<Project/>', encoding='utf-8')
        (root / 'Demo.slnx').write_text('<Solution><Project Path="A.csproj"/>'
                                     '<Project Path="B.csproj"/></Solution>', encoding='utf-8')
        provenance = {'actor': 'synthetic-fixture', 'method': 'explicit-example-data-not-human-review'}
        claims = []
        for identifier, statement in [('claim.example.project', 'Repository contains A.csproj.'),
                ('claim.example.reference', 'A.csproj declares ProjectReference Include B.csproj.')]:
            claims.append(dict(id=identifier, statement=statement, type='technical_fact',
                status='NEEDS_HUMAN_CONFIRMATION', evidence=['evidence.example'], provenance=provenance,
                last_verified=None, depends_on=[], conflicts_with=[]))
        # Explicit synthetic claim dependency, not an observed project edge conversion.
        claims[1]['depends_on'] = [claims[0]['id']]
        for index, claim in enumerate(claims):
            (root / '.ai/knowledge/claims' / f'{index}.json').write_text(json.dumps(claim), encoding='utf-8')
        evidence = dict(id='evidence.example', type='direct-technical', status='active', source='A.csproj',
            provenance=provenance, captured_at='2026-01-01T00:00:00Z',
            location={'reference': 'A.csproj#/Project[1]'},
            description='Synthetic fixture declaration references; no copied source content.',
            content_hash='sha256:' + hashlib.sha256((root / 'A.csproj').read_bytes()).hexdigest(),
            substantiates=[claim['id'] for claim in claims])
        (root / '.ai/evidence/example.json').write_text(json.dumps(evidence), encoding='utf-8')
        builder = GraphBuilder()
        if mode in ['canonical', 'technical-preview']:
            return builder.build(root, mode)
        report = builder.report(root)
        return human_report(report) if mode == 'summary' else report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['canonical', 'technical-preview', 'report', 'summary'])
    result = example(parser.parse_args().mode)
    print(result if isinstance(result, str) else json.dumps(result, sort_keys=True, indent=2),
          end='' if isinstance(result, str) else '\n')
