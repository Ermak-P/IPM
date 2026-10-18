# Universal Architecture Knowledge Base
## Contract v1.0

**Status:** Ready for approval  
**Purpose:** A universal architecture knowledge base scaffold that can be safely added to existing repositories  
**Implementation scope:** Stage 1 — scaffold, schemas, CLI, and automated verification  
**Guiding principle:** The knowledge base is a guest in the host project, not its owner.

---

## 1. Goals and Principles

Create a portable knowledge base for storing verifiable information about architecture, business rules, and technical facts, independently of the programming language, IDE, agent, and build system.

Mandatory principles:

1. `.ai` is the sole canonical source of architectural knowledge.
2. The scaffold does not manage the host project or modify its configuration.
3. Fact extraction, inference, and claim verification are separate operations.
4. Every confirmed claim must have a verifiable basis.
5. Structural validity does not prove the truth of a claim's content.
6. Derived artifacts can be deleted and regenerated without losing knowledge.
7. Initialization is safe, repeatable, and does not overwrite user data.
8. All verification runs locally, without network access or LLM calls.

## 2. Stage 1 Scope

### Included in Stage 1

- Directory structure and baseline files.
- JSON Schema definitions for claims, evidence, and relationships.
- Documentation describing the knowledge lifecycle and verification rules.
- Manifest and format versioning.
- Headless CLI.
- Automated validation and acceptance tests.
- Verification of safe installation in synthetic repositories.

### Excluded from Stage 1

- Source-code scanning and analysis.
- Extraction from `.sln`, `.csproj`, or equivalent files in other languages.
- Automatic construction of an architecture graph.
- RAG, embeddings, and vector databases.
- MCP and agent integrations.
- Automatic confirmation of business rules.
- Automatic modification of CI, IDE, build settings, or host-project files.

These capabilities will be considered separately after the scaffold has been accepted.

## 3. Directory Structure

```text
.ai/
├── README.md
├── manifest.yaml
├── schema/
│   ├── claim.schema.json
│   ├── evidence.schema.json
│   └── relationship.schema.json
├── knowledge/
│   ├── claims/
│   ├── relationships/
│   ├── domains/
│   ├── decisions/
│   └── open-questions/
├── evidence/
├── sources/
├── generated/
├── state/
├── docs/
│   ├── knowledge-lifecycle.md
│   ├── evidence-and-confidence.md
│   └── schema-versioning.md
└── tools/
    └── ...
```

The implementation may refine file formats and CLI implementation locations, provided that the responsibility boundaries defined by this contract are preserved.

### 3.1. `knowledge/`

Canonical knowledge:

- `claims/` — atomic claims.
- `relationships/` — relationships between entities and claims.
- `domains/` — subject areas.
- `decisions/` — architectural decisions and their rationale.
- `open-questions/` — questions that cannot yet be answered with sufficient confidence.

Decisions, conclusions, and substantive cross-session memory belong here, not in `state/`.

### 3.2. `evidence/`

Evidence supporting claims. Records contain provenance metadata, evidence type, status, and a reference to the source.

Copying source code or documents into evidence is not mandatory. Local references and checksums are preferred for sensitive repositories.

### 3.3. `sources/`

Metadata describing sources and rules for accessing or processing them. This directory is not intended to contain copies of the host project's source files.

### 3.4. `generated/`

Fully reproducible derived outputs.

**Invariant:** The entire `generated/` directory can be deleted and recreated without losing canonical knowledge.

If data cannot be reconstructed without loss, it must not be stored exclusively in `generated/`.

### 3.5. `state/`

Technical execution metadata only:

- schema versions;
- input checksums;
- execution timestamps and results;
- technical checkpoints;
- information required to safely resume an operation.

Architectural decisions, claims, explanations, and cross-session knowledge must not be stored in `state/`.

### 3.6. `docs/`

Markdown documentation. It does not require a mandatory data schema: its purpose is to explain rules and processes, not replace machine-validated records.

## 4. Canonical Claim Model

Each claim must contain the following fields:

| Field | Type | Purpose |
|---|---|---|
| `id` | string | Stable unique identifier |
| `statement` | string | Claim expressed in natural language |
| `type` | enum | Claim category |
| `status` | enum | Verification status |
| `evidence` | array of strings | Evidence identifiers |
| `provenance` | object | Claim origin |
| `last_verified` | date or null | Date of the last verification |
| `depends_on` | array of strings | Claims on which this claim depends |
| `conflicts_with` | array of strings | Claims known to conflict with this claim |

Relationship and evidence arrays may be empty when permitted by the claim's status and semantics. All identifiers must be checked for uniqueness and valid references.

### 4.1. Claim Types

- `business_rule` — a business rule or requirement governing product behavior.
- `architecture` — a claim about structure, boundaries, component responsibilities, or architectural intent.
- `technical_fact` — a directly verifiable technical fact.

Examples:

- "Project A references Project B in its `.csproj` file" — `technical_fact`.
- "Component A is responsible for content delivery" — `architecture` when interpreting structure and responsibilities is necessary.
- "A finished campaign cannot be deleted" — `business_rule`.

The type is determined by the meaning of the claim, not by the file extension of its source.

### 4.2. Claim Statuses

- `CONFIRMED` — sufficient, valid, direct evidence is available.
- `INFERRED` — the claim is derived from other facts or indirect evidence.
- `UNKNOWN` — insufficient information is available for a justified conclusion.
- `NEEDS_HUMAN_CONFIRMATION` — confirmation by an authorized human is required.

Extracting a fact or generating a statement with an LLM does not authorize automatic assignment of `CONFIRMED`.

## 5. Evidence Model

Each evidence record must contain:

| Field | Type | Purpose |
|---|---|---|
| `id` | string | Unique evidence identifier |
| `type` | enum | Evidence type |
| `status` | enum | Current evidence status |
| `source` | string or object | Source identifier or description |
| `provenance` | object | Who or what obtained the evidence and how |
| `captured_at` | date-time | Time the evidence was captured |
| `location` | optional string or object | Reference to a specific location in the source |
| `content_hash` | optional string | Checksum, where applicable |
| `description` | string | What the evidence can be used to verify |

### 5.1. Evidence Types

- `direct-authoritative` — a direct authoritative source, such as an approved business requirement.
- `direct-technical` — a directly verifiable technical source.
- `supporting` — indirect evidence that supports a claim.
- `derived` — evidence produced by inference from other information.

### 5.2. Evidence Statuses

- `active` — currently valid.
- `retracted` — withdrawn.
- `superseded` — replaced by more current evidence.

Evidence with status `retracted` or `superseded` is retained for audit purposes but cannot independently serve as a current basis for `CONFIRMED`.

## 6. Validation and Verification Rules

The `validate` command checks data structure and explicitly defined invariants. It does not guarantee the semantic truth of the claim text.

### 6.1. Mandatory Checks

The validator must detect:

- missing required fields;
- values outside defined enumerations;
- duplicate identifiers;
- references to nonexistent claims or evidence;
- invalid cycles and malformed relationships where prohibited by the contract;
- invalid date and version values;
- inconsistent `conflicts_with` relationships;
- `CONFIRMED` claims without valid supporting evidence.

### 6.2. Requirements for `CONFIRMED`

A claim with status `CONFIRMED` must have at least one evidence record that simultaneously:

1. Exists and passes structural validation.
2. Has status `active`.
3. Has an appropriate direct evidence type.
4. Contains sufficient information to verify its relationship to the specific claim.

If a claim references multiple evidence records, withdrawn or superseded evidence does not automatically invalidate the claim when another sufficient, active, direct piece of evidence remains.

The validator must not treat every piece of direct evidence as sufficient merely because of its type. It checks available structural indicators and explicitly defined rules, but does not claim to have automatically proven the truth of arbitrary natural-language statements.

### 6.3. Restrictions by Claim Type

- `business_rule` requires `direct-authoritative` evidence or an explicitly recorded confirmation by an authorized human. `direct-technical` evidence alone is insufficient.
- `technical_fact` may be supported by `direct-technical` evidence when the evidence directly substantiates the claim.
- `architecture` may be supported by direct technical or authoritative evidence when that evidence substantiates the architectural claim itself. An interpretive conclusion without sufficient direct support remains `INFERRED`.

### 6.4. Evidence Freshness

`last_verified` must not automatically downgrade a claim solely because time has passed.

Evidence is unsuitable for confirmation if it has been retracted, superseded, or can no longer substantiate the claim under explicitly defined rules. If freshness cannot be checked automatically, the validator reports the limitation instead of making an unsupported conclusion.

Reverification policies based on age may be introduced later for specific knowledge categories. They are not a universal automatic rule in v1.

### 6.5. Conflicts

`conflicts_with` records known conflicts between claims.

The validator must:

- verify that referenced claims exist;
- prohibit self-references;
- detect malformed and inconsistent relationships;
- provide diagnostics identifying both sides of a conflict.

The validator must not automatically select the true claim, delete conflicting records, or change their statuses without a separate conflict-resolution process.

## 7. Manifest and Versioning

`manifest.yaml` must contain at least:

- the knowledge-base format identifier;
- the format version;
- schema versions;
- supported capabilities;
- descriptions of record storage formats.

The knowledge-base format version is independent of the CLI version.

A breaking schema change requires a format-version change and a documented migration path. The validator must not silently accept an incompatible format or ignore an unknown version.

## 8. Headless CLI

The CLI must support at least the following commands.

### `init`

Creates missing scaffold elements.

Requirements:

- safe to run repeatedly;
- does not overwrite existing files;
- requires no interactive input;
- does not modify files outside the permitted scope.

### `validate`

Validates the manifest, schemas, records, references, identifiers, types, statuses, and evidence rules.

### `check-scaffold`

Checks scaffold completeness and compliance with safe-installation requirements. The check must not rely on undocumented assumptions about the host repository.

### `version`

Prints the CLI version and supported knowledge-base format versions.

### 8.1. Exit Codes and Output

- Exit code `0` — verification succeeded.
- Nonzero exit code — an error or contract violation occurred.
- Diagnostics identify the file, issue, and related identifiers where available.
- Results are independent of file traversal order.
- A machine-readable output format, such as JSON, is supported.
- Commands require neither network access nor LLM calls.

CI integration is optional. The CLI may be used in CI, but the scaffold must not modify CI configuration automatically.

## 9. Security and Host-Project Compatibility

Installation must not automatically:

- modify `.sln`, `.csproj`, or equivalent build files;
- modify `.editorconfig` or IDE settings;
- modify CI/CD configuration;
- add mandatory dependencies to the host project;
- install agent configurations or overwrite other tools' instructions;
- send repository contents to external services.

Initialization must be restricted to `.ai/` and explicitly necessary scaffold files. Any additional modifications require a separate, explicit user decision.

An existing `.ai/` directory must not be considered empty merely because it does not match the expected template. If existing data is detected, `init` must preserve it and report a conflict or the need for manual reconciliation.

## 10. Acceptance Tests

The following automated tests are mandatory:

1. Initializing an empty repository creates the complete scaffold.
2. Running `init` again does not change the contents of previously created files.
3. Existing user files are preserved byte-for-byte.
4. Installation does not modify files outside the permitted scope.
5. Build files, `.editorconfig`, CI, and host-tool settings remain unchanged.
6. No mandatory dependencies are added to the host project.
7. All valid built-in schemas and examples pass `validate`.
8. Duplicate IDs and broken references are detected.
9. A `CONFIRMED` claim without acceptable direct evidence is rejected.
10. A business rule without authoritative evidence or explicit human confirmation fails validation.
11. `supporting` and `derived` evidence cannot automatically confirm a claim.
12. Deleting `generated/` does not cause loss of canonical knowledge.
13. Changes to `state/` do not change the contents of `knowledge/`.
14. The scaffold works in synthetic repositories without dependence on a specific programming language.
15. Identical inputs produce identical verification results.
16. A `CONFIRMED` claim with only `retracted` or `superseded` evidence is rejected.
17. A `CONFIRMED` claim with multiple evidence records passes when at least one active, direct piece of evidence is sufficient to substantiate it.
18. Invalid `conflicts_with` relationships, broken references, and self-references are detected.
19. The age of `last_verified` alone does not change a claim's status.
20. Unknown or incompatible format versions are handled explicitly and are never silently accepted.

Tests must run automatically and return an exit code. Manual inspection does not replace acceptance tests.

## 11. Stage 1 Completion Criteria

Stage 1 is complete when:

- the scaffold structure and responsibility boundaries are documented;
- schemas are implemented and validated;
- the CLI implements all required commands;
- all acceptance tests are automated and passing;
- safe installation has been verified in synthetic repositories;
- the absence of changes to existing host-project files and settings has been demonstrated;
- there is no mandatory dependency on network access or LLMs;
- knowledge-extraction tools have not yet been included in the scaffold.

## 12. Next Stage

After v1 is accepted, separate tools for initial knowledge population will be developed.

Proposed Stage 2 commands:

- `scan` — identify the project structure and available sources;
- `extract` — extract technical facts using stack-specific analyzers;
- `build` — construct reproducible derived representations;
- `report` — report new facts, uncertainties, conflicts, and gaps.

Their implementation must remain separate from the universal core. Extracted technical facts must not automatically become confirmed business or architectural claims.

Changes to contract v1 after implementation begins are permitted only when a specific defect or incompatibility is identified, not merely to expand the scope of work.

---

## Implementation Decision

**Approve Contract v1.0 as the baseline implementation specification.**

Implementation must proceed in the following order:

1. Create the directory structure, manifest, schemas, and documentation.
2. Implement `init`, `validate`, `check-scaffold`, and `version`.
3. Add and run all 20 acceptance tests against synthetic repositories.
4. Review the diff and demonstrate that no host-project files have been modified.
5. Submit the verification results for review. Begin Stage 2 — knowledge-population tools — only after Stage 1 has been accepted.

This keeps the first stage bounded and verifiable and prevents the universal core from being prematurely coupled to project-specific analyzers.
