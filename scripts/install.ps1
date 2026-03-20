# OVO Energy Australia - Home Assistant Installation Script (PowerShell)
# This script automatically installs the OVO Energy Australia integration

# Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# Default Home Assistant config directory
$HA_CONFIG = $env:HA_CONFIG
if (-not $HA_CONFIG) {
    $HA_CONFIG = "C:\config"
}

Write-Host "╔════════════════════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "║   OVO Energy Australia Installation Script        ║" -ForegroundColor Blue
Write-Host "║   Home Assistant Custom Component                 ║" -ForegroundColor Blue
Write-Host "╚════════════════════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# Function to detect Home Assistant config directory
function Find-HAConfig {
    $possiblePaths = @(
        "C:\config",
        "$env:USERPROFILE\.homeassistant",
        "\\wsl$\Ubuntu\config"
    )

    foreach ($path in $possiblePaths) {
        if (Test-Path "$path\configuration.yaml") {
            return $path
        }
    }

    return $null
}

# Detect or ask for config directory
if (-not (Test-Path "$HA_CONFIG\configuration.yaml")) {
    Write-Host "Home Assistant config not found at: $HA_CONFIG" -ForegroundColor Yellow

    $detected = Find-HAConfig
    if ($detected) {
        Write-Host "Found Home Assistant at: $detected" -ForegroundColor Green
        $HA_CONFIG = $detected
    } else {
        Write-Host "Could not auto-detect Home Assistant config directory" -ForegroundColor Yellow
        $HA_CONFIG = Read-Host "Enter your Home Assistant config directory path"

        if (-not (Test-Path "$HA_CONFIG\configuration.yaml")) {
            Write-Host "Error: configuration.yaml not found at $HA_CONFIG" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host "✓ Using Home Assistant config: $HA_CONFIG" -ForegroundColor Green
Write-Host ""

# Create custom_components directory if it doesn't exist
$CUSTOM_DIR = "$HA_CONFIG\custom_components"
if (-not (Test-Path $CUSTOM_DIR)) {
    Write-Host "Creating custom_components directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $CUSTOM_DIR | Out-Null
    Write-Host "✓ Created $CUSTOM_DIR" -ForegroundColor Green
}

# Check if already installed
$COMPONENT_DIR = "$CUSTOM_DIR\ovo_energy_au"
if (Test-Path $COMPONENT_DIR) {
    Write-Host "⚠ OVO Energy Australia is already installed" -ForegroundColor Yellow
    $response = Read-Host "Do you want to reinstall/update? (y/N)"
    if ($response -notmatch '^[Yy]$') {
        Write-Host "Installation cancelled" -ForegroundColor Blue
        exit 0
    }
    Write-Host "Removing old installation..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $COMPONENT_DIR
}

# Determine installation method
Write-Host ""
Write-Host "Choose installation method:" -ForegroundColor Blue
Write-Host "1. Download from GitHub (recommended)"
Write-Host "2. Copy from current directory (if already downloaded)"
Write-Host ""
$method = Read-Host "Enter choice (1 or 2)"

if ($method -eq "1") {
    # Download from GitHub
    Write-Host "Downloading from GitHub..." -ForegroundColor Yellow

    $tempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
    $zipPath = "$tempDir\repo.zip"

    try {
        Invoke-WebRequest -Uri "https://github.com/HallyAus/OVO_Aus_api/archive/refs/heads/claude/create-github-project-rWeUP.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $tempDir

        Write-Host "Installing component..." -ForegroundColor Yellow
        $repoDir = Get-ChildItem -Path $tempDir -Directory | Select-Object -First 1
        Copy-Item -Recurse -Path "$($repoDir.FullName)\custom_components\ovo_energy_au" -Destination $COMPONENT_DIR

        Remove-Item -Recurse -Force $tempDir
    } catch {
        Write-Host "Error: Failed to download from GitHub" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }

} elseif ($method -eq "2") {
    # Copy from current directory
    $SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

    if (-not (Test-Path "$SCRIPT_DIR\custom_components\ovo_energy_au")) {
        Write-Host "Error: custom_components\ovo_energy_au not found in current directory" -ForegroundColor Red
        Write-Host "Please run this script from the repository root" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "Copying from current directory..." -ForegroundColor Yellow
    Copy-Item -Recurse -Path "$SCRIPT_DIR\custom_components\ovo_energy_au" -Destination $COMPONENT_DIR

} else {
    Write-Host "Invalid choice" -ForegroundColor Red
    exit 1
}

# Verify installation
if (Test-Path "$COMPONENT_DIR\manifest.json") {
    Write-Host "✓ Component files installed successfully" -ForegroundColor Green
} else {
    Write-Host "Error: Installation verification failed" -ForegroundColor Red
    exit 1
}

# Show next steps
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║            Installation Complete! ✓                ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Blue
Write-Host ""
Write-Host "1. Get your tokens from OVO website:" -ForegroundColor Yellow
Write-Host "   • Go to https://my.ovoenergy.com.au"
Write-Host "   • Open DevTools (F12) → Network tab"
Write-Host "   • Log in and click 'Usage'"
Write-Host "   • Filter by 'graphql' and copy tokens from request headers"
Write-Host ""
Write-Host "2. Add to configuration.yaml:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   ovo_energy_au:"
Write-Host "     access_token: `"Bearer eyJ...`""
Write-Host "     id_token: `"eyJ...`""
Write-Host "     account_id: `"30264061`""
Write-Host ""
Write-Host "3. Restart Home Assistant" -ForegroundColor Yellow
Write-Host ""
Write-Host "Installed to: $COMPONENT_DIR" -ForegroundColor Blue
Write-Host ""
Write-Host "Documentation: https://github.com/HallyAus/OVO_Aus_api" -ForegroundColor Blue
Write-Host "Support: https://github.com/HallyAus/OVO_Aus_api/issues" -ForegroundColor Blue
Write-Host ""
Write-Host "Happy solar tracking! ☀️" -ForegroundColor Green
