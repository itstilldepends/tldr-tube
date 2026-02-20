#!/bin/bash

# tldr-tube startup script
# Automatically setup environment and launch application

set -e  # Exit immediately on error

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🎬 tldr-tube Startup Script${NC}"
echo "================================"

# 1. Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda not found${NC}"
    echo "Please install Miniconda first: brew install --cask miniconda"
    exit 1
fi

# 2. Check if conda environment exists
if ! conda env list | grep -q "tldr-tube"; then
    echo -e "${YELLOW}⚠️  Conda environment 'tldr-tube' not found, creating...${NC}"
    conda create -n tldr-tube python=3.11 -y
    echo -e "${GREEN}✅ Conda environment created${NC}"
fi

# 3. Activate conda environment
echo -e "${GREEN}🔄 Activating conda environment...${NC}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate tldr-tube

# 4. Check if dependencies are installed
if ! python -c "import streamlit" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Dependencies not installed, installing...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# 5. Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    cp .env.example .env
    echo -e "${YELLOW}📝 Created .env file, please fill in:${NC}"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - APP_PASSWORD"
    echo ""
    read -p "Press Enter to edit .env file..."
    ${EDITOR:-nano} .env
fi

# 6. Create data directory (if not exists)
# Note: Database tables are auto-created on app startup
if [ ! -d data ]; then
    echo -e "${GREEN}📁 Creating data directory...${NC}"
    mkdir -p data
fi

# 7. Launch application
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🚀 Starting Streamlit app...${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "Access at: ${YELLOW}http://localhost:8501${NC}"
echo -e "Press ${RED}Ctrl+C${NC} to stop"
echo ""

# Start streamlit (disable welcome page and usage stats)
STREAMLIT_SERVER_HEADLESS=true \
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
streamlit run app.py
