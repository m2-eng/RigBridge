param(
    [Parameter(Mandatory = $true)]
    [string]$TarPath,
    [string]$ImageName = "rigbridge",
    [string]$Tag = "local-test",
    [string]$ContainerName = "rigbridge",
    [int]$HostPort = 8080
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $TarPath)) {
    throw "Tar file not found: $TarPath"
}

$fullImageTag = "${ImageName}:${Tag}"

Write-Host "Loading Docker image from ${TarPath}..."
docker load -i $TarPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$existingContainerId = docker ps -a -q -f "name=^${ContainerName}$"
if ($existingContainerId) {
    Write-Host "Removing existing container ${ContainerName}..."
    docker rm -f $ContainerName | Out-Null
}

$configSource = Join-Path (Get-Location) "config.json"
$themeSource = Join-Path (Get-Location) "theme.css"

if (-not (Test-Path $configSource)) {
    throw "Missing config.json in current directory: $configSource"
}

if (-not (Test-Path $themeSource)) {
    throw "Missing theme.css in current directory: $themeSource"
}

Write-Host "Starting container ${ContainerName} from ${fullImageTag} on 127.0.0.1:${HostPort}..."
docker run -d `
    --name $ContainerName `
    --restart unless-stopped `
    -p "127.0.0.1:${HostPort}:8080" `
    -v "${configSource}:/app/config.json" `
    -v "${themeSource}:/app/src/frontend/assets/theme.css" `
    -e PYTHONUNBUFFERED=1 `
    $fullImageTag
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Container is running. Open: http://127.0.0.1:${HostPort}"
