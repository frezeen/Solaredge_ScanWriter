#!/usr/bin/env pwsh
# SolarEdge Multi-Platform Docker Setup
# Compatible with: Windows, Linux, macOS, Raspberry Pi

param(
    [string]$Action = "setup",
    [switch]$Clean,
    [switch]$Build,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Logs,
    [switch]$Status,
    [switch]$Grafana
)

# Cross-platform colors
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    
    $colorMap = @{
        "Red" = "Red"
        "Green" = "Green" 
        "Yellow" = "Yellow"
        "Blue" = "Blue"
        "Magenta" = "Magenta"
        "Cyan" = "Cyan"
        "White" = "White"
    }
    
    Write-Host $Message -ForegroundColor $colorMap[$Color]
}

function Test-DockerInstalled {
    try {
        $null = docker --version 2>$null
        return $true
    } catch {
        return $false
    }
}

function Get-DockerComposeCommand {
    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        return "docker-compose"
    } else {
        try {
            docker compose version | Out-Null
            return "docker compose"
        } catch {
            return $null
        }
    }
}

function Install-Docker {
    Write-ColorOutput "🐳 Docker Installation Required" "Yellow"
    
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        Write-ColorOutput "📥 Install Docker Desktop for Windows:" "Cyan"
        Write-ColorOutput "   https://docs.docker.com/desktop/windows/install/" "White"
        Write-ColorOutput "   Then restart this script." "Yellow"
    } elseif ($IsMacOS) {
        Write-ColorOutput "📥 Install Docker Desktop for macOS:" "Cyan"
        Write-ColorOutput "   https://docs.docker.com/desktop/mac/install/" "White"
        Write-ColorOutput "   Or use Homebrew: brew install --cask docker" "White"
    } else {
        Write-ColorOutput "📥 Install Docker for Linux:" "Cyan"
        Write-ColorOutput "   curl -fsSL https://get.docker.com | sh" "White"
        Write-ColorOutput "   sudo usermod -aG docker `$USER" "White"
    }
    
    exit 1
}

function Enable-DockerBuildx {
    Write-ColorOutput "🔧 Configuring Docker Buildx..." "Blue"
    
    try {
        docker buildx create --name solaredge-builder --use --bootstrap 2>$null
        docker buildx inspect --bootstrap | Out-Null
        Write-ColorOutput "✅ Docker Buildx configured" "Green"
    } catch {
        Write-ColorOutput "⚠️ Buildx configuration failed, continuing..." "Yellow"
    }
}

function Clean-Docker {
    Write-ColorOutput "🧹 Cleaning Docker resources..." "Yellow"
    
    $composeCmd = Get-DockerComposeCommand
    if ($composeCmd) {
        if ($composeCmd -eq "docker-compose") {
            docker-compose down --remove-orphans --volumes 2>$null
        } else {
            docker compose down --remove-orphans --volumes 2>$null
        }
    }
    
    # Remove SolarEdge containers and images
    $containers = docker ps -a --filter "name=solaredge" --format "{{.ID}}" 2>$null
    if ($containers) {
        $containers | ForEach-Object { docker rm -f $_ 2>$null }
    }
    
    $images = docker images --filter "reference=*solaredge*" --format "{{.ID}}" 2>$null
    if ($images) {
        $images | ForEach-Object { docker rmi -f $_ 2>$null }
    }
    
    docker system prune -f --volumes 2>$null
    Write-ColorOutput "✅ Cleanup completed" "Green"
}

function Build-MultiArchImage {
    Write-ColorOutput "🏗️ Building multi-platform image..." "Blue"
    
    $platforms = "linux/amd64,linux/arm64,linux/arm/v7"
    Write-ColorOutput "📋 Target platforms: $platforms" "Cyan"
    
    try {
        docker buildx build --platform $platforms --tag solaredge-collector:latest --load .
        Write-ColorOutput "✅ Multi-platform build completed" "Green"
    } catch {
        Write-ColorOutput "❌ Build failed, trying single platform..." "Red"
        docker build -t solaredge-collector:latest .
    }
}

function Start-Services {
    Write-ColorOutput "🚀 Starting SolarEdge services..." "Blue"
    
    $composeCmd = Get-DockerComposeCommand
    if (-not $composeCmd) {
        Write-ColorOutput "❌ Docker Compose not found" "Red"
        exit 1
    }
    
    $composeArgs = @("up", "-d")
    if ($Grafana) {
        $composeArgs += @("--profile", "grafana")
    }
    
    if ($composeCmd -eq "docker-compose") {
        & docker-compose @composeArgs
    } else {
        & docker compose @composeArgs
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✅ Services started successfully" "Green"
        Show-ServiceInfo
    } else {
        Write-ColorOutput "❌ Failed to start services" "Red"
        Show-Logs
        exit 1
    }
}

function Stop-Services {
    Write-ColorOutput "🛑 Stopping services..." "Yellow"
    
    $composeCmd = Get-DockerComposeCommand
    if ($composeCmd) {
        if ($composeCmd -eq "docker-compose") {
            docker-compose down
        } else {
            docker compose down
        }
    }
    
    Write-ColorOutput "✅ Services stopped" "Green"
}

function Show-Logs {
    $composeCmd = Get-DockerComposeCommand
    if ($composeCmd) {
        if ($composeCmd -eq "docker-compose") {
            docker-compose logs -f --tail=50
        } else {
            docker compose logs -f --tail=50
        }
    }
}

function Show-Status {
    Write-ColorOutput "📊 Service Status:" "Blue"
    
    $composeCmd = Get-DockerComposeCommand
    if ($composeCmd) {
        if ($composeCmd -eq "docker-compose") {
            docker-compose ps
        } else {
            docker compose ps
        }
    }
}

function Show-ServiceInfo {
    Write-ColorOutput "" "White"
    Write-ColorOutput "🎉 SolarEdge Data Collector is running!" "Green"
    Write-ColorOutput "" "White"
    Write-ColorOutput "📊 GUI Dashboard: http://localhost:8092" "Cyan"
    Write-ColorOutput "🗄️ InfluxDB: http://localhost:8086" "Cyan"
    if ($Grafana) {
        Write-ColorOutput "📈 Grafana: http://localhost:3000" "Cyan"
    }
    Write-ColorOutput "" "White"
    Write-ColorOutput "📋 Useful commands:" "Blue"
    Write-ColorOutput "   .\docker-setup.ps1 -Logs     # View logs" "White"
    Write-ColorOutput "   .\docker-setup.ps1 -Stop     # Stop services" "White"
    Write-ColorOutput "   .\docker-setup.ps1 -Status   # Service status" "White"
    Write-ColorOutput "   .\docker-setup.ps1 -Clean    # Full cleanup" "White"
    Write-ColorOutput "" "White"
}

function Test-Configuration {
    Write-ColorOutput "🔍 Checking configuration..." "Blue"
    
    $requiredFiles = @("docker-compose.yml", "Dockerfile", ".env.example")
    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-ColorOutput "❌ Missing file: $file" "Red"
            exit 1
        }
    }
    
    if (-not (Test-Path ".env")) {
        Write-ColorOutput "⚠️ .env file not found, copying from .env.example" "Yellow"
        Copy-Item ".env.example" ".env"
        Write-ColorOutput "📝 Please edit .env with your SolarEdge credentials" "Cyan"
    }
    
    Write-ColorOutput "✅ Configuration verified" "Green"
}

function Main {
    Write-ColorOutput "🌍 SolarEdge Multi-Platform Docker Setup" "Magenta"
    Write-ColorOutput "=======================================" "Magenta"
    
    # Rilevamento automatico architettura
    Write-ColorOutput "🔍 Rilevamento automatico sistema..." "Blue"
    $arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $archReal = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
    $realArch = if ($archReal) { $archReal } else { $arch }
    
    Write-ColorOutput "🖥️ Sistema: Windows" "Blue"
    Write-ColorOutput "🏗️ Architettura: $realArch" "Blue"
    
    # Verifica Docker Desktop
    $dockerDesktop = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
    if ($dockerDesktop) {
        Write-ColorOutput "🐳 Docker Desktop: In esecuzione" "Green"
    } else {
        Write-ColorOutput "⚠️ Docker Desktop: Non rilevato" "Yellow"
        Write-ColorOutput "   Assicurati che Docker Desktop sia avviato" "Yellow"
    }
    
    Write-ColorOutput "" "White"
    
    # Handle command line arguments
    if ($Clean) { Clean-Docker; return }
    if ($Build) { Enable-DockerBuildx; Build-MultiArchImage; return }
    if ($Start) { Start-Services; return }
    if ($Stop) { Stop-Services; return }
    if ($Logs) { Show-Logs; return }
    if ($Status) { Show-Status; return }
    
    # Full setup
    if (-not (Test-DockerInstalled)) {
        Install-Docker
        return
    }
    
    if (-not (Get-DockerComposeCommand)) {
        Write-ColorOutput "❌ Docker Compose not found" "Red"
        Write-ColorOutput "   Install Docker Compose or use Docker Desktop" "Cyan"
        exit 1
    }
    
    Test-Configuration
    Enable-DockerBuildx
    Clean-Docker
    Build-MultiArchImage
    Start-Services
    
    Write-ColorOutput "🎯 Multi-platform setup completed!" "Green"
}

# Execute main function
Main