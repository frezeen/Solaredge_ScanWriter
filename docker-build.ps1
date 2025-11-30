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

# Check if services are already running
Write-ColorOutput "Checking service status..." "Blue"
$servicesRunning = $false
try {
    $runningServices = docker compose ps --format json 2>$null | ConvertFrom-Json
    if ($runningServices -and ($runningServices | Where-Object { $_.State -eq "running" })) {
        $servicesRunning = $true
        Write-ColorOutput "Services already running, updating..." "Blue"
    } else {
        Write-ColorOutput "Starting Docker services..." "Blue"
    }
} catch {
    Write-ColorOutput "Starting Docker services..." "Blue"
}

try {
    docker compose up -d
    if ($servicesRunning) {
        Write-ColorOutput "Services updated successfully" "Green"
    } else {
        Write-ColorOutput "Services started successfully" "Green"
    }

    # Wait for services to be ready
    Write-ColorOutput "Waiting for services to be ready..." "Blue"
    Start-Sleep -Seconds 15

    # Configure Grafana automatically
    Write-ColorOutput "Configuring Grafana..." "Blue"

    # Wait for Grafana to be ready
    $grafanaReady = $false
    for ($i = 1; $i -le 30; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $grafanaReady = $true
                break
            }
        } catch {
            # Continue waiting
        }
        Start-Sleep -Seconds 2
    }

    if ($grafanaReady) {
        # Configure Sun and Moon data source
        Write-ColorOutput "Configuring Sun and Moon data source..." "Blue"
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

            $credentials = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("admin:admin"))
            $headers = @{
                "Authorization" = "Basic $credentials"
                "Content-Type" = "application/json"
            }

            $sunMoonResponse = Invoke-RestMethod -Uri "http://localhost:3000/api/datasources" -Method Post -Body $sunMoonData -Headers $headers -ErrorAction SilentlyContinue
            if ($sunMoonResponse.id) {
                Write-ColorOutput "Sun and Moon data source configured" "Green"
            }
        } catch {
            Write-ColorOutput "Warning: Could not configure Sun and Moon data source" "Yellow"
        }

        # Get data source UIDs and fix dashboard
        Start-Sleep -Seconds 5

        $dataSourcesList = Invoke-RestMethod -Uri "http://localhost:3000/api/datasources" -Headers $headers -ErrorAction Continue
        $influxUID = ($dataSourcesList | Where-Object { $_.name -eq "Solaredge" }).uid
        $sunMoonUID = ($dataSourcesList | Where-Object { $_.name -eq "Sun and Moon" }).uid

        if ($influxUID) {
                Write-ColorOutput "Importing dashboard with correct UIDs..." "Blue"

                # Replicate EXACTLY what Linux script does using jq in container
                if (Test-Path "grafana/dashboard-solaredge.json") {
                    try {
                        # Create bash script and execute (exactly like Linux script)
                        $bashScript = @"
#!/bin/bash
INFLUX_UID='$influxUID'
SUNMOON_UID='$sunMoonUID'

# Copy dashboard (exactly like Linux script)
TEMP_DASHBOARD='/tmp/dashboard-solaredge-temp.json'
cp /app/grafana/dashboard-solaredge.json `$TEMP_DASHBOARD

# Fix InfluxDB UID using jq (exactly like Linux script)
jq --arg uid "`$INFLUX_UID" 'walk(if type == "object" and .type == "influxdb" then .uid = `$uid else . end)' `$TEMP_DASHBOARD > `${TEMP_DASHBOARD}.tmp && mv `${TEMP_DASHBOARD}.tmp `$TEMP_DASHBOARD

# Fix Sun and Moon UID if available (exactly like Linux script)
if [[ -n "`$SUNMOON_UID" && "`$SUNMOON_UID" != "null" ]]; then
    jq --arg uid "`$SUNMOON_UID" 'walk(if type == "object" and .type == "fetzerch-sunandmoon-datasource" then .uid = `$uid else . end)' `$TEMP_DASHBOARD > `${TEMP_DASHBOARD}.tmp && mv `${TEMP_DASHBOARD}.tmp `$TEMP_DASHBOARD
fi

# Create import payload (exactly like Linux script)
IMPORT_PAYLOAD='/tmp/dashboard-import-payload.json'
jq -n --slurpfile dashboard `$TEMP_DASHBOARD '{dashboard: `$dashboard[0], overwrite: true, message: "Imported by Docker setup"}' > `$IMPORT_PAYLOAD

# Import dashboard using curl (exactly like Linux script)
if [[ -f `$IMPORT_PAYLOAD ]]; then
    IMPORT_RESPONSE=`$(curl -s -X POST http://grafana:3000/api/dashboards/db -u admin:admin -H 'Content-Type: application/json' -d @`$IMPORT_PAYLOAD)

    if echo "`$IMPORT_RESPONSE" | grep -q '"status":"success"'; then
        echo 'SUCCESS'
    else
        echo 'FAILED'
    fi

    rm -f `$IMPORT_PAYLOAD `$TEMP_DASHBOARD
else
    echo 'FAILED'
fi
"@

                        # Write script with Unix line endings and execute
                        $importResult = $bashScript | docker exec -i solaredge-scanwriter bash -c "cat | sed 's/\r$//' | bash"

                        # Cleanup
                        docker exec solaredge-scanwriter rm -f /tmp/import-dashboard.sh 2>$null

                        if ($importResult -match "SUCCESS") {
                            Write-ColorOutput "Dashboard imported successfully" "Green"
                        } else {
                            Write-ColorOutput "Dashboard import failed. Result: $importResult" "Red"
                        }

                    } catch {
                        Write-ColorOutput "Warning: Could not import dashboard - $($_.Exception.Message)" "Yellow"
                    }
                }
            } else {
                Write-ColorOutput "DEBUG: No InfluxDB UID found, skipping dashboard import" "Yellow"
            }
    }

    # Generate web endpoints only if not exists (preserve user customizations)
    if (-not (Test-Path "config/sources/web_endpoints.yaml")) {
        Write-ColorOutput "Generating web endpoints (first time)..." "Blue"
        try {
            docker exec solaredge-scanwriter python main.py --scan 2>$null | Out-Null
            Write-ColorOutput "Web endpoints generated" "Green"
        } catch {
            Write-ColorOutput "Warning: Could not generate web endpoints" "Yellow"
        }
    } else {
        Write-ColorOutput "Web endpoints already exist (preserved)" "Green"
    }

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
    Write-Host "   Docker volumes - All your data (InfluxDB, Grafana, logs)" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-ColorOutput "Failed to start services: $($_.Exception.Message)" "Red"
    exit 1
}
