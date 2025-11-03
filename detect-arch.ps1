#!/usr/bin/env pwsh
# Script PowerShell per rilevare architettura su Windows

param(
    [switch]$Detailed
)

# Funzioni di output colorato
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

function Detect-SystemArchitecture {
    Write-ColorOutput "🖥️  Sistema Rilevato:" "Cyan"
    
    $os = "Windows"
    $version = [System.Environment]::OSVersion.Version
    $arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $archReal = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
    
    # Determina architettura reale
    $realArch = if ($archReal) { $archReal } else { $arch }
    
    Write-Host "   OS: $os $($version.Major).$($version.Minor)" -ForegroundColor White
    Write-Host "   Architettura: $realArch" -ForegroundColor White
    
    # Rileva Docker Desktop
    $dockerDesktop = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
    if ($dockerDesktop) {
        Write-ColorOutput "   Docker Desktop: In esecuzione" "Green"
    } else {
        Write-ColorOutput "   Docker Desktop: Non rilevato" "Yellow"
    }
    
    # Determina target Docker
    switch ($realArch) {
        "AMD64" {
            Write-ColorOutput "   Tipo: AMD64/Intel 64-bit" "Green"
            Write-Host "   Docker Platform: linux/amd64" -ForegroundColor White
            Write-Host "   Ottimizzazioni: Windows + Linux containers" -ForegroundColor White
        }
        "ARM64" {
            Write-ColorOutput "   Tipo: ARM64 (Windows ARM)" "Green"
            Write-Host "   Docker Platform: linux/arm64" -ForegroundColor White
            Write-Host "   Ottimizzazioni: Windows ARM + Linux containers" -ForegroundColor White
        }
        "x86" {
            Write-ColorOutput "   Tipo: x86 32-bit (Legacy)" "Yellow"
            Write-Host "   Docker Platform: linux/386" -ForegroundColor White
            Write-Host "   Ottimizzazioni: Supporto limitato" -ForegroundColor White
        }
        default {
            Write-ColorOutput "   Tipo: Sconosciuta ($realArch)" "Yellow"
            Write-Host "   Docker Platform: linux/amd64 (fallback)" -ForegroundColor White
        }
    }
}

function Test-DockerCapabilities {
    Write-Host ""
    Write-ColorOutput "🐳 Capacità Docker:" "Cyan"
    
    # Test Docker
    try {
        $dockerVersion = docker --version 2>$null
        if ($dockerVersion) {
            Write-ColorOutput "   Docker: $dockerVersion" "Green"
        } else {
            Write-ColorOutput "   Docker: Non installato" "Red"
            return
        }
    } catch {
        Write-ColorOutput "   Docker: Non disponibile" "Red"
        return
    }
    
    # Test Docker Compose
    try {
        $composeVersion = docker compose version --short 2>$null
        if ($composeVersion) {
            Write-ColorOutput "   Compose: $composeVersion" "Green"
        } else {
            $composeVersion = docker-compose --version 2>$null
            if ($composeVersion) {
                Write-ColorOutput "   Compose: $composeVersion (standalone)" "Green"
            } else {
                Write-ColorOutput "   Compose: Non disponibile" "Yellow"
            }
        }
    } catch {
        Write-ColorOutput "   Compose: Errore nel rilevamento" "Yellow"
    }
    
    # Test Buildx
    try {
        $buildxVersion = docker buildx version 2>$null
        if ($buildxVersion) {
            Write-ColorOutput "   Buildx: $buildxVersion" "Green"
            Write-ColorOutput "   Multi-arch: Supportato" "Green"
        } else {
            Write-ColorOutput "   Buildx: Non disponibile" "Yellow"
        }
    } catch {
        Write-ColorOutput "   Buildx: Non disponibile" "Yellow"
    }
    
    # WSL2 Detection
    try {
        $wslVersion = wsl --version 2>$null
        if ($wslVersion) {
            Write-ColorOutput "   WSL2: Disponibile" "Green"
        } else {
            Write-ColorOutput "   WSL2: Non rilevato" "Yellow"
        }
    } catch {
        Write-ColorOutput "   WSL2: Non disponibile" "Yellow"
    }
}

function Show-WindowsRecommendations {
    $arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $archReal = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
    $realArch = if ($archReal) { $archReal } else { $arch }
    
    Write-Host ""
    Write-ColorOutput "💡 Raccomandazioni per Windows:" "Cyan"
    
    Write-ColorOutput "   🪟 Windows con Docker Desktop" "Green"
    Write-Host "   ✅ Assicurati che Docker Desktop sia avviato" -ForegroundColor White
    Write-Host "   ✅ Usa WSL2 backend per performance migliori" -ForegroundColor White
    Write-Host "   ✅ Linux containers supportati nativamente" -ForegroundColor White
    
    Write-Host ""
    Write-ColorOutput "   📋 Prerequisiti Windows:" "Blue"
    Write-Host "      - Docker Desktop 4.0+" -ForegroundColor White
    Write-Host "      - WSL2 abilitato (raccomandato)" -ForegroundColor White
    Write-Host "      - Hyper-V abilitato (alternativa)" -ForegroundColor White
    
    switch ($realArch) {
        "AMD64" {
            Write-Host "      - Memoria Windows: 8GB+ (4GB per Docker)" -ForegroundColor White
            Write-Host "      - CPU: 4+ core (2+ per Docker)" -ForegroundColor White
            Write-Host "      - WSL2: 4GB+ allocati" -ForegroundColor White
            Write-Host "      - Build: Buildx multi-platform supportato" -ForegroundColor White
        }
        "ARM64" {
            Write-Host "      - Memoria Windows: 8GB+ (ARM richiede più risorse)" -ForegroundColor White
            Write-Host "      - CPU: 4+ core ARM" -ForegroundColor White
            Write-Host "      - Build: ARM64 nativo" -ForegroundColor White
            Write-ColorOutput "      - Nota: Supporto ARM64 in sviluppo" "Yellow"
        }
        "x86" {
            Write-ColorOutput "      - Architettura 32-bit non ottimale" "Yellow"
            Write-Host "      - Considera upgrade a sistema 64-bit" -ForegroundColor White
        }
    }
}

function Show-OptimalConfiguration {
    $arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $archReal = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
    $realArch = if ($archReal) { $archReal } else { $arch }
    
    Write-Host ""
    Write-ColorOutput "⚙️  Configurazione Docker Ottimale per Windows:" "Cyan"
    
    switch ($realArch) {
        "AMD64" {
            Write-Host @"
   # docker-compose.yml - Sezione deploy ottimizzata per Windows AMD64
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '2.0'
       reservations:
         memory: 512M
         cpus: '1.0'
"@ -ForegroundColor White
        }
        "ARM64" {
            Write-Host @"
   # docker-compose.yml - Sezione deploy ottimizzata per Windows ARM64
   deploy:
     resources:
       limits:
         memory: 768M
         cpus: '1.5'
       reservations:
         memory: 384M
         cpus: '0.75'
"@ -ForegroundColor White
        }
        "x86" {
            Write-Host @"
   # docker-compose.yml - Sezione deploy ottimizzata per Windows x86
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '1.0'
       reservations:
         memory: 256M
         cpus: '0.5'
"@ -ForegroundColor White
        }
    }
}

function Main {
    Write-ColorOutput "🔍 Rilevamento Automatico Architettura Windows" "Cyan"
    Write-Host "===============================================" -ForegroundColor Cyan
    
    Detect-SystemArchitecture
    Test-DockerCapabilities
    Show-WindowsRecommendations
    
    if ($Detailed) {
        Show-OptimalConfiguration
    }
    
    Write-Host ""
    Write-ColorOutput "✅ Rilevamento completato!" "Green"
    Write-Host ""
    Write-ColorOutput "🚀 Per avviare il build ottimizzato:" "Blue"
    Write-Host "   .\docker-setup.ps1" -ForegroundColor Yellow
    Write-Host "   oppure" -ForegroundColor White
    Write-Host "   .\dev-docker-rebuild.sh (in WSL/Git Bash)" -ForegroundColor Yellow
}

# Esegui funzione principale
Main