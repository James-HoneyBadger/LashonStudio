#!/bin/bash
# Lashon IDE Launch Script
# Automatically sets up virtual environment and installs dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_CMD="python3"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Lashon IDE Launcher v4.0.0        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if Python 3 is available
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo -e "${YELLOW}Python 3 not found. Trying 'python'...${NC}"
    PYTHON_CMD="python"
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo "Error: Python 3 is required but not found."
        echo "Please install Python 3.7 or higher."
        exit 1
    fi
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Found Python $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment exists"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --quiet --upgrade pip

# Install Lashon in development mode
echo -e "${BLUE}Installing Lashon and dependencies...${NC}"
pip install --quiet -e "$SCRIPT_DIR"

# Install development dependencies
echo -e "${BLUE}Installing development dependencies...${NC}"
pip install --quiet pytest black flake8

echo -e "${GREEN}✓${NC} All dependencies installed"
echo ""

# Launch Lashon IDE
echo -e "${BLUE}Launching Lashon IDE...${NC}"
echo ""

cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
lashon-ide

# Deactivate virtual environment on exit
deactivate
