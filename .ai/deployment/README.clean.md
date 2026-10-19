# Universal Architecture Knowledge Base — clean runtime deployment

This is the clean-runtime-v1 distribution, not the synthetic development project.
The canonical Contract v1.0, schemas and validation rules are unchanged. No project
knowledge, source observations, examples, generated graphs, approval receipts,
plans or journals are bundled. Canonical knowledge/evidence/source directories,
generated/ and state/ start empty apart from .gitkeep placeholders.

Runtime tools: init, validate, check-scaffold, version, scan, extract, normalize,
populate (existing safety rules), build, report, inspect-compatibility and
adapt-compatibility. This deployment task does not authorize population. Use
read-only commands; do not run populate apply against real IPM.

The archive's kb.py contains an explicit runtime file/directory registry instead
of the development registry requiring tests/examples. Its function bodies,
validator and canonical manifest/schema bytes are unchanged. init from this
runtime distribution creates the same clean profile. No external store path or
foreign manifest adoption is added. Framework tests/fixtures remain in the
separate development repository and are not deployed as project knowledge.

Start with:

```text
python -B .ai/tools/kb.py version --json
python -B .ai/tools/kb.py validate --json
python -B .ai/tools/kb.py check-scaffold --json
python -B .ai/tools/kb.py populate status --json
```

Read docs/clean-deployment.md for staging beside preserved legacy knowledge,
Windows PowerShell instructions, privacy and read-only reconstruction. Do not
extract this package over an existing .ai. Preserve the original repository and
its legacy .ai unchanged; deploy into a separate evaluation copy first.

Deployment profile metadata is in deployment-profile.json. It is a package
inventory, not canonical project knowledge or runtime/approval state. Package
integrity requires a trusted outer ZIP SHA-256, not trust in a manifest alone.
Development observation/verification sections are omitted from archive copies
of operational docs; original development documents remain untouched. Contract
illustrations describe framework behavior; none is a claim about IPM.
Native Windows/NTFS acceptance remains open until actually executed there.
