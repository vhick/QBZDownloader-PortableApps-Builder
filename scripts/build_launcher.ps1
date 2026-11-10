$ErrorActionPreference = 'Stop'
$source = (Resolve-Path 'launcher').Path
New-Item -ItemType Directory -Path 'work/launcher' -Force | Out-Null
$built = $false
foreach ($generator in @('Visual Studio 17 2022', 'Visual Studio 18 2026')) {
  $build = 'work/launcher/build'
  if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
  & cmake -S $source -B $build -G $generator -A x64
  if ($LASTEXITCODE -ne 0) { Write-Host "CMake generator not available: $generator"; continue }
  & cmake --build $build --config Release --parallel 2
  if ($LASTEXITCODE -ne 0) { throw "Compiled launcher build failed with $generator" }
  $out = Join-Path $build 'Release/QBZDownloaderPortable.exe'
  if (-not (Test-Path -LiteralPath $out)) { throw "Missing compiled launcher $out" }
  Copy-Item -LiteralPath $out -Destination 'work/launcher/QBZDownloaderPortable.exe' -Force
  $built = $true
  break
}
if (-not $built) { throw 'Neither supported MSVC/CMake Windows generator was found' }
