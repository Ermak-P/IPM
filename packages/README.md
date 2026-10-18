# Offline test packages
These unmodified open-source NuGet archives were copied from the existing local
NuGet cache, not downloaded. They are the direct and transitive dependencies of
the NUnit test projects, pinned with content hashes in packages.lock.json.
They make restore possible without network access or a pre-populated user cache.
No application project uses third-party packages.
Original package metadata, license declarations and bundled notices are retained
inside each .nupkg (a ZIP archive). These third-party works retain their respective
licenses. SDK/framework reference packs are supplied by the installed .NET SDK.
