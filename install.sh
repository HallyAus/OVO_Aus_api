#!/bin/bash

# OVO Energy Australia - Home Assistant Installation Script
# This script automatically installs the OVO Energy Australia integration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default Home Assistant config directory
HA_CONFIG="${HA_CONFIG:-/config}"

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   OVO Energy Australia Installation Script        ║${NC}"
echo -e "${BLUE}║   Home Assistant Custom Component                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to detect Home Assistant config directory
detect_ha_config() {
    local possible_paths=(
        "/config"
        "$HOME/.homeassistant"
        "/usr/share/hassio/homeassistant"
        "/home/homeassistant/.homeassistant"
    )

    for path in "${possible_paths[@]}"; do
        if [ -f "$path/configuration.yaml" ]; then
            echo "$path"
            return 0
        fi
    done

    return 1
}

# Detect or ask for config directory
if [ ! -f "$HA_CONFIG/configuration.yaml" ]; then
    echo -e "${YELLOW}Home Assistant config not found at: $HA_CONFIG${NC}"

    detected=$(detect_ha_config)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Found Home Assistant at: $detected${NC}"
        HA_CONFIG="$detected"
    else
        echo -e "${YELLOW}Could not auto-detect Home Assistant config directory${NC}"
        echo -n "Enter your Home Assistant config directory path: "
        read -r HA_CONFIG

        if [ ! -f "$HA_CONFIG/configuration.yaml" ]; then
            echo -e "${RED}Error: configuration.yaml not found at $HA_CONFIG${NC}"
            exit 1
        fi
    fi
fi

echo -e "${GREEN}✓ Using Home Assistant config: $HA_CONFIG${NC}"
echo ""

# Create custom_components directory if it doesn't exist
CUSTOM_DIR="$HA_CONFIG/custom_components"
if [ ! -d "$CUSTOM_DIR" ]; then
    echo -e "${YELLOW}Creating custom_components directory...${NC}"
    mkdir -p "$CUSTOM_DIR"
    echo -e "${GREEN}✓ Created $CUSTOM_DIR${NC}"
fi

# Check if already installed
COMPONENT_DIR="$CUSTOM_DIR/ovo_energy_au"
if [ -d "$COMPONENT_DIR" ]; then
    echo -e "${YELLOW}⚠ OVO Energy Australia is already installed${NC}"
    echo -n "Do you want to reinstall/update? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Installation cancelled${NC}"
        exit 0
    fi
    echo -e "${YELLOW}Removing old installation...${NC}"
    rm -rf "$COMPONENT_DIR"
fi

# Determine installation method
echo ""
echo -e "${BLUE}Choose installation method:${NC}"
echo "1. Clone from GitHub (recommended - allows updates)"
echo "2. Copy from current directory (if already cloned)"
echo ""
echo -n "Enter choice (1 or 2): "
read -r method

if [ "$method" = "1" ]; then
    # Clone from GitHub
    echo -e "${YELLOW}Cloning from GitHub...${NC}"

    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    if ! git clone https://github.com/HallyAus/OVO_Aus_api.git; then
        echo -e "${RED}Error: Failed to clone repository${NC}"
        echo -e "${YELLOW}Make sure git is installed: apt-get install git${NC}"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    echo -e "${YELLOW}Installing component...${NC}"
    cp -r OVO_Aus_api/custom_components/ovo_energy_au "$COMPONENT_DIR"

    cd - > /dev/null
    rm -rf "$TEMP_DIR"

elif [ "$method" = "2" ]; then
    # Copy from current directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

    if [ ! -d "$SCRIPT_DIR/custom_components/ovo_energy_au" ]; then
        echo -e "${RED}Error: custom_components/ovo_energy_au not found in current directory${NC}"
        echo -e "${YELLOW}Please run this script from the repository root${NC}"
        exit 1
    fi

    echo -e "${YELLOW}Copying from current directory...${NC}"
    cp -r "$SCRIPT_DIR/custom_components/ovo_energy_au" "$COMPONENT_DIR"

else
    echo -e "${RED}Invalid choice${NC}"
    exit 1
fi

# Verify installation
if [ -f "$COMPONENT_DIR/manifest.json" ]; then
    echo -e "${GREEN}✓ Component files installed successfully${NC}"
else
    echo -e "${RED}Error: Installation verification failed${NC}"
    exit 1
fi

# Show next steps
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Installation Complete! ✓                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo -e "${YELLOW}1. Get your tokens from OVO website:${NC}"
echo "   • Go to https://my.ovoenergy.com.au"
echo "   • Open DevTools (F12) → Network tab"
echo "   • Log in and click 'Usage'"
echo "   • Filter by 'graphql' and copy tokens from request headers"
echo ""
echo -e "${YELLOW}2. Add to configuration.yaml:${NC}"
echo ""
echo "   ovo_energy_au:"
echo "     access_token: \"Bearer eyJ...\""
echo "     id_token: \"eyJ...\""
echo "     account_id: \"30264061\""
echo ""
echo -e "${YELLOW}3. Restart Home Assistant${NC}"
echo ""
echo -e "${BLUE}Installed to:${NC} $COMPONENT_DIR"
echo ""
echo -e "${BLUE}Documentation:${NC} https://github.com/HallyAus/OVO_Aus_api"
echo -e "${BLUE}Support:${NC} https://github.com/HallyAus/OVO_Aus_api/issues"
echo ""
echo -e "${GREEN}Happy solar tracking! ☀️${NC}"
