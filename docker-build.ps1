#!/usr/bin/env pwsh
# SolarEdge Docker Multi-Platform Builder for Windows
# Builds Docker containers for Windows, Linux, and Raspberry Pi

param(
    [switch]$Help
)

if ($Help) {
    Write-Host "SolarEdge Docker Multi-Platform Builder" -ForegroundColor Cyan
    Write-Host "Usage: .\docker-build.ps1" -ForegroundColor White
    Write-Host "Builds Docker image for current platform" -ForegroundColor White
    exit 0
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    
    $colorMap = @{
        "Red" = "Red"; "Green" = "Green"; "Yellow" = "Yellow"
        "Blue" = "Blue"; "Magenta" = "Magenta"; "Cyan" = "Cyan"; "White" = "White"
    }
    
    Write-Host $Message -ForegroundColor $colorMap[$Color]
}

Write-ColorOutput "🐳 SolarEdge Multi-Platform Docker Builder" "Cyan"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Detect Windows architecture
$arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
$archReal = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
$realArch = if ($archReal) { $archReal } else { $arch }

switch ($realArch) {
    "AMD64" { 
        $dockerArch = "linux/amd64"
        $archName = "AMD64"
    }
    "ARM64" { 
        $dockerArch = "linux/arm64"
        $archName = "ARM64"
    }
    default { 
        $dockerArch = "linux/amd64"
        $archName = "AMD64 (default)"
    }
}

Write-ColorOutput "🖥️  Detected architecture: $realArch → $archName" "Blue"
Write-ColorOutput "🐳 Docker target: $dockerArch" "Blue"
Write-Host ""

# Check required files
Write-ColorOutput "📋 Checking required files..." "Blue"
$requiredFiles = @("Dockerfile", "docker-compose.yml", "requirements.txt")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-ColorOutput "❌ Missing file: $file" "Red"
        exit 1
    }
}
Write-ColorOutput "✅ All required files present" "Green"
Write-Host ""

# Build Docker image
Write-ColorOutput "🏗️  Building Docker image for $archName..." "Blue"

try {
    # Check if buildx is available
    $buildxAvailable = $false
    try {
        docker buildx version | Out-Null
        $buildxAvailable = $true
    } catch {
        $buildxAvailable = $false
    }
    
    if ($buildxAvailable) {
        Write-ColorOutput "Using Docker Buildx for multi-platform build..." "Blue"
        
        # Create builder if needed
        $builders = docker buildx ls 2>$null
        if (-not ($builders -match "solaredge-builder")) {
            docker buildx create --name solaredge-builder --use --bootstrap 2>$null
        }
        
        # Try buildx build
        try {
            docker buildx build --platform $dockerArch --tag solaredge-scanwriter:latest --load .
            Write-ColorOutput "✅ Multi-platform build completed" "Green"
        } catch {
            Write-ColorOutput "⚠️  Buildx failed, using standard build..." "Yellow"
            docker build -t solaredge-scanwriter:latest .
            Write-ColorOutput "✅ Standard build completed" "Green"
        }
    } else {
        Write-ColorOutput "Using standard Docker build..." "Blue"
        docker build -t solaredge-scanwriter:latest .
        Write-ColorOutput "✅ Build completed" "Green"
    }
} catch {
    Write-ColorOutput "❌ Build failed: $($_.Exception.Message)" "Red"
    exit 1
}

Write-Host ""

# Verify image
Write-ColorOutput "🔍 Verifying built image..." "Blue"
try {
    $images = docker images solaredge-scanwriter:latest --format "{{.Repository}}:{{.Tag}}" 2>$null
    if ($images -match "solaredge-scanwriter:latest") {
        $imageSize = docker images solaredge-scanwriter:latest --format "{{.Size}}" 2>$null
        Write-ColorOutput "✅ Image built successfully - Size: $imageSize" "Green"
    } else {
        Write-ColorOutput "❌ Image not found after build" "Red"
        exit 1
    }
} catch {
    Write-ColorOutput "❌ Error verifying image: $($_.Exception.Message)" "Red"
    exit 1
}

Write-Host ""
Write-ColorOutput "🎉 Docker build completed!" "Green"
Write-Host ""
Write-ColorOutput "📋 Next steps:" "Blue"
Write-Host "   docker compose up -d     # Start services" -ForegroundColor Yellow
Write-Host "   docker compose ps        # Check status" -ForegroundColor Yellow
Write-Host "   docker compose logs -f   # View logs" -ForegroundColor Yellow
Write-Host ""