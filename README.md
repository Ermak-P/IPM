# Synthetic IPM fixture

A fictional in-product marketing platform for local architecture analysis.
All names, domain rules, contracts and data are original synthetic examples.
No corporate implementation is represented. This contains the host application only.

## Build and test offline

Requires .NET SDK **10.0.402** (or a later 10.0.4xx patch), targeting **net10.0**.
Six projects: Domain, Application, Infrastructure, Api, UnitTests, IntegrationTests.
Nullable reference types and compiler warnings-as-errors apply to all projects.

From the repository root in PowerShell:

```powershell
./verify.ps1
```

The script runs locked restore, full build and NUnit tests, failing on any error.
Its environment variables apply to the current process; no machine settings are changed.
NuGet.Config uses only `packages/`, containing 14 unmodified open-source archives
from the pre-existing cache (~27 MB). Packages extract into ignored `.local/nuget`.
There is no dependency on a populated user cache or the internet. SDK and framework
reference packs must already be installed; they are not vendored.

Equivalent commands after setting DOTNET_CLI_HOME to a writable local directory:

```powershell
dotnet restore SyntheticIpm.sln --locked-mode --configfile NuGet.Config
dotnet build SyntheticIpm.sln --no-restore
dotnet test SyntheticIpm.sln --no-build --no-restore
```

## Run

```powershell
$env:DOTNET_CLI_HOME = Join-Path $PWD '.local'
dotnet run --project src/SyntheticIpm.Api --no-build --no-restore -- --urls http://127.0.0.1:5077
```

HTTP binds to loopback in this example. This unauthenticated fixture is intended
for local synthetic data. No Docker, database server, Kafka broker, credentials,
cloud account or other runtime services are needed.

See [HTTP contracts and workflows](docs/architecture-overview.md),
[domain overview](docs/domain-overview.md), [business rules and tests](docs/business-rules.md),
[dependency map](docs/dependency-map.md), and [verification record](docs/verification.md).

## Deliberate limits

All data, event queues and event deduplication are lost on restart. Statistics
consumption is explicit via POST /statistics/process, not a background worker.
The queue is a single-consumer Kafka-like teaching example: no Kafka protocol,
partitions, replay, offsets, retry or durable delivery. Requests are serialized
by the host; application services are intended for sequential fixture use.
There are no distributed transactions, authentication, production storage or CI.
Groups organize content; campaigns associate individual items.
An interaction means a submitted synthetic interaction; prior impression proof
is not required. Repeated publication represents another impression.
External identifiers are case-sensitive and retained for the lifetime of the process;
reimporting a deleted campaign currently reports not found rather than recreating it.
No knowledge-base implementation or agent harness is included.
