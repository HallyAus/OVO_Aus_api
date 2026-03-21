#!/bin/bash
# OVO Energy AU - Quick Deploy Script
# Run this on your Home Assistant machine to update the integration
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/main/scripts/deploy.sh | bash
#   OR
#   ./scripts/deploy.sh

set -e

HA_CONFIG_DIR="${HA_CONFIG_DIR:-/config}"
REPO_URL="https://github.com/HallyAus/OVO_Aus_api"
INTEGRATION_DIR="$HA_CONFIG_DIR/custom_components/ovo_energy_au"
TEMP_DIR=$(mktemp -d)

echo "=== OVO Energy AU Integration Updater ==="
echo ""

# Download latest
echo "Downloading latest version..."
curl -sL "$REPO_URL/archive/refs/heads/main.tar.gz" | tar xz -C "$TEMP_DIR"

# Backup existing
if [ -d "$INTEGRATION_DIR" ]; then
    BACKUP_DIR="$HA_CONFIG_DIR/custom_components/ovo_energy_au.backup.$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing installation to $BACKUP_DIR"
    cp -r "$INTEGRATION_DIR" "$BACKUP_DIR"
fi

# Install new version
echo "Installing new version..."
mkdir -p "$HA_CONFIG_DIR/custom_components"
rm -rf "$INTEGRATION_DIR"
cp -r "$TEMP_DIR"/OVO_Aus_api-main/custom_components/ovo_energy_au "$INTEGRATION_DIR"

# Cleanup
rm -rf "$TEMP_DIR"

# Get version
VERSION=$(grep '"version"' "$INTEGRATION_DIR/manifest.json" | head -1 | grep -o '"[0-9.]*"' | tr -d '"')
echo ""
echo "Successfully installed OVO Energy AU v$VERSION"
echo "Please restart Home Assistant to apply the update."
echo ""

# Try to restart HA if ha command is available
if command -v ha &> /dev/null && [ -t 0 ]; then
    read -p "Restart Home Assistant now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Restarting Home Assistant..."
        ha core restart
    fi
fi
