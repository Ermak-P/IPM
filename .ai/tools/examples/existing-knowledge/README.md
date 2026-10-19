# Synthetic existing-knowledge fixture

`fixture.json` is a bundle of fictional UTF-8 file contents keyed by relative
paths. It describes a pre-existing Harbor Tickets `.ai`, not IPM knowledge or
corporate data. Never install it into a real repository or treat its records as
Contract v1 canonical records.

It includes a business glossary, business/architecture assertions, active-looking
and withdrawn evidence, domain prose, an ADR, a foreign manifest/schema, component
relationships, legacy lifecycle labels, durable notes in conflicting directories,
and a project-owned graph-tool contract/output.

The bundled `tools/knowledge_graph.py` is an **inert ownership sentinel**, not a
new Graph Builder. Its fictional legacy implementation is deliberately absent;
it must never be imported or executed. This lets installer path and ownership
conflicts be demonstrated without implementing or invoking another builder.

Use only a disposable temporary directory to materialize this bundle for
assessment. The Stage 3.1 report documents the exact test cases and outcomes.
There is no migration, mapping adapter, registry, installation hook or change to
the current installer. The framework does not consume this fixture automatically.
