param(
    [string]$ImageName = "rigbridge",
    [string]$Tag = "local-test",
    [string]$TarPath,
    [string]$Platform
)

$ErrorActionPreference = "Stop"

$fullImageTag = "${ImageName}:${Tag}"

if (-not $TarPath) {
    $safeTag = $Tag -replace "[^a-zA-Z0-9._-]", "-"
    $TarPath = Join-Path "docker" "offline\${ImageName}-${safeTag}.tar"
}

$tarDirectory = Split-Path -Parent $TarPath
if ($tarDirectory -and -not (Test-Path $tarDirectory)) {
    New-Item -ItemType Directory -Path $tarDirectory -Force | Out-Null
}

if ($Platform) {
    Write-Host "Building Docker image ${fullImageTag} (target: runtime, platform: ${Platform})..."
    docker build --platform $Platform --target runtime -t $fullImageTag .
}
else {
    Write-Host "Building Docker image ${fullImageTag} (target: runtime)..."
    docker build --target runtime -t $fullImageTag .
}
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Exporting image ${fullImageTag} to ${TarPath}..."
docker save -o $TarPath $fullImageTag
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Done. Offline image package created: ${TarPath}"
Write-Host "Load on target machine with: docker load -i ${TarPath}"
Write-Host "Do not use 'docker import' for this TAR package, otherwise CMD/Entrypoint metadata is lost."
if ($Platform) {
    Write-Host "Built platform: ${Platform}"
}
