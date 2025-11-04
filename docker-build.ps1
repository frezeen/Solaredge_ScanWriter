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
    
    $finalColor = $colorMap[$Color]
    if (-not $finalColor) {
        $finalColor = "White"
    }
    
    Write-Host $Message -ForegroundColor $finalColor
}

Write-ColorOutput "Docker SolarEdge Multi-Platform Builder" "Cyan"
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

Write-ColorOutput "Detected architecture: $realArch -> $archName" "Blue"
Write-ColorOutput "Docker target: $dockerArch" "Blue"
Write-Host ""

# Check Docker installation
Write-ColorOutput "Checking Docker installation..." "Blue"
try {
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-ColorOutput "Docker found: $dockerVersion" "Green"
    } else {
        Write-ColorOutput "Docker not found or not working" "Red"
        Write-ColorOutput "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/" "Yellow"
        exit 1
    }
} catch {
    Write-ColorOutput "Docker not found or not working" "Red"
    Write-ColorOutput "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/" "Yellow"
    exit 1
}

# Check if Docker daemon is running
try {
    docker info 2>$null | Out-Null
    Write-ColorOutput "Docker daemon is running" "Green"
} catch {
    Write-ColorOutput "Docker daemon is not running" "Red"
    Write-ColorOutput "Please start Docker Desktop" "Yellow"
    exit 1
}

# Check required files
Write-ColorOutput "Checking required files..." "Blue"
$requiredFiles = @("Dockerfile", "docker-compose.yml", "requirements.txt")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-ColorOutput "Missing file: $file" "Red"
        exit 1
    } else {
        Write-ColorOutput "Found: $file" "Green"
    }
}
Write-Host ""

# Build Docker image
Write-ColorOutput "Building Docker image for $archName..." "Blue"

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
            Write-ColorOutput "Running: docker buildx build --platform $dockerArch --tag solaredge-scanwriter:latest --load ." "Blue"
            $buildOutput = docker buildx build --platform $dockerArch --tag solaredge-scanwriter:latest --load . 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Multi-platform build completed" "Green"
            } else {
                Write-ColorOutput "Buildx failed with exit code $LASTEXITCODE" "Yellow"
                Write-ColorOutput "Build output: $buildOutput" "Yellow"
                throw "Buildx failed"
            }
        } catch {
            Write-ColorOutput "Buildx failed, using standard build..." "Yellow"
            Write-ColorOutput "Running: docker build -t solaredge-scanwriter:latest ." "Blue"
            $buildOutput = docker build -t solaredge-scanwriter:latest . 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Standard build completed" "Green"
            } else {
                Write-ColorOutput "Standard build also failed with exit code $LASTEXITCODE" "Red"
                Write-ColorOutput "Build output: $buildOutput" "Red"
                throw "Both buildx and standard build failed"
            }
        }
    } else {
        Write-ColorOutput "Using standard Docker build..." "Blue"
        Write-ColorOutput "Running: docker build -t solaredge-scanwriter:latest ." "Blue"
        $buildOutput = docker build -t solaredge-scanwriter:latest . 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Build completed" "Green"
        } else {
            Write-ColorOutput "Build failed with exit code $LASTEXITCODE" "Red"
            Write-ColorOutput "Build output: $buildOutput" "Red"
            throw "Docker build failed"
        }
    }
} catch {
    Write-ColorOutput "Build failed: $($_.Exception.Message)" "Red"
    exit 1
}

Write-Host ""

# Verify image
Write-ColorOutput "Verifying built image..." "Blue"
try {
    $images = docker images solaredge-scanwriter:latest --format "{{.Repository}}:{{.Tag}}" 2>$null
    if ($images -match "solaredge-scanwriter:latest") {
        $imageSize = docker images solaredge-scanwriter:latest --format "{{.Size}}" 2>$null
        Write-ColorOutput "Image built successfully - Size: $imageSize" "Green"
    } else {
        Write-ColorOutput "Image not found after build" "Red"
        Write-ColorOutput "This usually means the build failed. Check the build output above." "Yellow"
        exit 1
    }
} catch {
    Write-ColorOutput "Error verifying image: $($_.Exception.Message)" "Red"
    exit 1
}

Write-Host ""

# Start services automatically
Write-ColorOutput "Starting Docker services..." "Blue"
try {
    docker compose up -d
    Write-ColorOutput "Services started successfully" "Green"
    
    Write-Host ""
    Write-ColorOutput "Update completed!" "Green"
    Write-Host ""
    Write-ColorOutput "Services available:" "Blue"
    Write-Host "   GUI SolarEdge: http://localhost:8092" -ForegroundColor Yellow
    Write-Host "   InfluxDB:      http://localhost:8086" -ForegroundColor Yellow
    Write-Host "   Grafana:       http://localhost:3000" -ForegroundColor Yellow
    Write-Host ""
    Write-ColorOutput "Configuration files preserved:" "Blue"
    Write-Host "   .env - Your credentials and settings" -ForegroundColor Yellow
    Write-Host "   config/sources/*.yaml - Your custom endpoints" -ForegroundColor Yellow
    Write-Host "   Docker volumes - All your data" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-ColorOutput "Failed to start services: $($_.Exception.Message)" "Red"
    exit 1
}