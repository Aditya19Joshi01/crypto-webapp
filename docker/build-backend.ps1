# Build the backend Docker image from the docker/ folder using the repo root as context.
param(
    [string]$Tag = "aditya19joshi01/crypto-backend:v1"
)

# Move to script directory
Set-Location -Path $PSScriptRoot

Write-Host "Building Docker image with tag: $Tag (context = ..)"

# Use .. as build context so Dockerfile's COPY backend/requirements.txt resolves
docker build -f Dockerfile -t $Tag ..

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Docker image built: $Tag"