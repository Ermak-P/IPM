# Implementation plan
Use the supplied task as the specification. Six projects keep domain rules, orchestration,
in-memory adapters, HTTP transport and two test scopes separate. All data is fictional.
1. Lifecycle and targeting: NUnit tests first, implement domain, verify unit suite.
2. Distribution, import, events and synchronization: integration tests first, implement application and adapters, verify.
3. HTTP host and documentation: build solution, run all tests, inspect references and final files.
Environment: Windows x64, SDK 10.0.402, net10.0. dotnet --info hits a Service Control
Manager permission error after reporting SDK/runtime inventory; ordinary commands will be checked independently.
Test dependencies were copied unmodified from the existing cache into packages/; NuGet.Config now uses only this local offline feed. All 14 archives declare MIT licenses.
No global configuration, commits, external runtime services, knowledge base or CI.

