# Schema and CLI versioning

Knowledge-base format universal-architecture-kb 1.0.0 is independent of CLI 1.0.0.
The manifest pins each of the three schemas at 1.0.0, capabilities and storage.
Unknown, missing or incompatible manifest fields/versions fail explicitly.

The manifest capabilities list is the pinned Contract v1.0 core capability set
(init, validate, check-scaffold, version), not an exhaustive CLI command registry.
Optional population-layer extensions (scan and extract) are documented separately
and listed by CLI --help. They do not change the core manifest, canonical schemas
or format version. init includes the extension modules and tests for portability.

Schemas use JSON Schema draft 2020-12. The offline CLI implements only the exact
v1 schema profile: object/array/string/null, required, properties,
additionalProperties, enum, anyOf, items, uniqueItems, minLength, pattern and
date/date-time formats. It is not a general JSON Schema engine. Unsupported
keywords and modified v1 schemas fail rather than being silently ignored.
Dates are YYYY-MM-DD; timestamps require T and an explicit Z or numeric offset.

Breaking schema changes require a new format version, new schema versions and a
documented migration. There is no automatic migration in v1. To migrate in future,
back up .ai, run a separately reviewed migration into a new directory, validate
with the matching CLI, compare canonical records and obtain review before replacing
the original. init never migrates or overwrites an existing installation.
