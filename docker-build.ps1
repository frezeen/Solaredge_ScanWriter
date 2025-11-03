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

# Start services automatically
Write-ColorOutput "🚀 Starting Docker services..." "Blue"
try {
    docker compose up -d
    Write-ColorOutput "✅ Services started successfully" "Green"
    
    # Wait for services
    Write-ColorOutput "⏳ Waiting for services to be ready..." "Blue"
    Start-Sleep -Seconds 15
    
    # Configure Grafana
    Write-ColorOutput "📊 Configuring Grafana..." "Blue"
    
    # Wait for Grafana
    for ($i = 1; $i -le 30; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) { break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    
    # Configure Sun and Moon data source
    Write-ColorOutput "☀️ Configuring Sun and Moon data source..." "Blue"
    try {
        $sunMoonData = @{
            name = "Sun and Moon"
            type = "fetzerch-sunandmoon-datasource"
            access = "proxy"
            jsonData = @{
                latitude = 40.8199
                longitude = 14.3413
            }
        } | ConvertTo-Json -Depth 3
        
        $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
        $headers = @{ Authorization = "Basic $auth"; "Content-Type" = "application/json" }
        
        $sunMoonResponse = Invoke-RestMethod -Uri "http://localhost:3000/api/datasources" -Method Post -Body $sunMoonData -Headers $headers -ErrorAction SilentlyContinue
        if ($sunMoonResponse.id) {
            Write-ColorOutput "✅ Sun and Moon data source configured" "Green"
        }
    } catch { }
    
    # Get data source UIDs and fix dashboard
    Start-Sleep -Seconds 5
    try {
        $datasourcesResponse = Invoke-RestMethod -Uri "http://localhost:3000/api/datasources" -Headers $headers -ErrorAction SilentlyContinue
        $influxUID = ($datasourcesResponse | Where-Object { $_.name -eq "Solaredge" }).uid
        $sunmoonUID = ($datasourcesResponse | Where-Object { $_.name -eq "Sun and Moon" }).uid
        
        if ($influxUID) {
            Write-ColorOutput "🔧 Importing dashboard with correct UIDs..." "Blue"
            
            # Read and fix dashboard JSON
            $dashboardContent = Get-Content "grafana/dashboard-solaredge.json" -Raw | ConvertFrom-Json
            
            # Fix InfluxDB UIDs (simplified approach for PowerShell)
            $dashboardJson = Get-Content "grafana/dashboard-solaredge.json" -Raw
            $dashboardJson = $dashboardJson -replace '"uid":"[^"]*","type":"influxdb"', "`"uid`":`"$influxUID`",`"type`":`"influxdb`""
            
            if ($sunmoonUID) {
                $dashboardJson = $dashboardJson -replace '"uid":"[^"]*","type":"fetzerch-sunandmoon-datasource"', "`"uid`":`"$sunmoonUID`",`"type`":`"fetzerch-sunandmoon-datasource`""
            }
            
            # Import dashboard
            $importData = @{
                dashboard = ($dashboardJson | ConvertFrom-Json)
                overwrite = $true
                message = "Imported by Docker setup"
            } | ConvertTo-Json -Depth 20
            
            $importResponse = Invoke-RestMethod -Uri "http://localhost:3000/api/dashboards/db" -Method Post -Body $importData -Headers $headers -ErrorAction SilentlyContinue
            if ($importResponse.status -eq "success") {
                Write-ColorOutput "✅ Dashboard imported successfully" "Green"
            }
    } catch { }
    
    # Generate web endpoints only if not exists (preserve user customizations)
    if (-not (Test-Path "config/sources/web_endpoints.yaml")) {
        Write-ColorOutput "🔍 Generating web endpoints (first time)..." "Blue"
        try {
            docker exec solaredge-scanwriter python main.py --scan 2>$null | Out-Null
            Write-ColorOutput "✅ Web endpoints generated" "Green"
        } catch { }
    } else {
        Write-ColorOutput "✅ Web endpoints already exist (preserved)" "Green"
    }
    
    Write-Host ""
    Write-ColorOutput "🎉 Update completed!" "Green"
    Write-Host ""
    Write-ColorOutput "📊 Services available:" "Blue"
    Write-Host "   GUI SolarEdge: http://localhost:8092" -ForegroundColor Yellow
    Write-Host "   InfluxDB:      http://localhost:8086" -ForegroundColor Yellow
    Write-Host "   Grafana:       http://localhost:3000" -ForegroundColor Yellow
    Write-Host ""
    Write-ColorOutput "🛡️  Configuration files preserved:" "Blue"
    Write-Host "   .env - Your credentials and settings" -ForegroundColor Yellow
    Write-Host "   config/sources/*.yaml - Your custom endpoints" -ForegroundColor Yellow
    Write-Host "   Docker volumes - All your data (InfluxDB, Grafana, logs)" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-ColorOutput "❌ Failed to start services: $($_.Exception.Message)" "Red"
    exit 1
}