# Verification record

Executed locally on 2026-10-19 (Europe/Moscow).

| Check | Result |
|---|---|
| SDK / framework | .NET SDK 10.0.402, net10.0, Windows x64; installed runtime 10.0.13 |
| Projects | 6 (4 application projects, 2 NUnit test projects) |
| Offline locked restore | Passed using only vendored packages and newly populated `.local/nuget` |
| Full build | Passed, 0 warnings, 0 errors |
| Unit tests | 12 passed, 0 failed, 0 skipped |
| Service integration tests | 15 passed, 0 failed, 0 skipped |
| HTTP smoke | Passed: import, content association, transitions, publish, consume impression/interaction, Finished deletion 409, invalid import 400 |
| Project graph | Parsed all 6 csproj files; DFS found no cycles in 5 explicit edges |
| Dependency licenses | All 14 package archives declare MIT in their original nuspec metadata |
| External runtime services | None required or configured; in-memory implementations used throughout |
| Documentation | Checked against routes, transitions, DI registration, event and state flows |

`verify.ps1` is the repeatable restore/build/test entry point. TRX output is generated
under each test project's ignored TestResults directory. The HTTP smoke started a
loopback host for this check and stopped that process afterward.

## Environment constraints and scope of evidence

`dotnet --info` reported the installed SDK/runtime inventory but returned an access
error while inspecting Windows Service Control Manager. `dotnet --version` succeeded.
The sandbox prevented testhost connectivity and some MSBuild child operations;
final verification ran with approved execution outside that sandbox. No global tools,
workloads, certificates or machine settings were installed or changed.

No Git repository existed at the supplied location. New source/configuration/docs were
reviewed as additions against an empty baseline; no commits, pushes or staging occurred.
No real Kafka integration, durable storage, distributed concurrency, authentication,
performance/load tests or corporate behavior validation was attempted. No external
vulnerability database was queried. The limitations in README are deliberate fixture
constraints, not production guarantees.
