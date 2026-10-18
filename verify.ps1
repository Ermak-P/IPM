param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$env:DOTNET_CLI_HOME = Join-Path $PSScriptRoot '.local'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:TESTINGPLATFORM_TELEMETRY_OPTOUT = '1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
$env:DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = 'false'
$env:NUGET_PACKAGES = Join-Path $PSScriptRoot '.local/nuget'
Push-Location $PSScriptRoot
try {
    dotnet restore SyntheticIpm.sln --locked-mode --configfile NuGet.Config
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed.' }
    dotnet build SyntheticIpm.sln --no-restore -p:UseSharedCompilation=false
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    if (!$SkipTests) {
        dotnet test SyntheticIpm.sln --no-build --no-restore --logger 'trx;LogFilePrefix=synthetic-ipm'
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    }
} finally { Pop-Location }
