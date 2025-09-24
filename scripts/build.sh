#!/bin/bash

# Buddhist RAG App Build Script
# Builds the application for distribution

set -e

echo "🙏 Building Buddhist RAG Application..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "package.json" ] && [ ! -d "electron-app" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Navigate to project root if needed
if [ -f "scripts/build.sh" ]; then
    cd "$(dirname "$0")/.."
fi

echo -e "${BLUE}Step 1: Installing Python backend dependencies...${NC}"
cd python-backend
python -m pip install -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo -e "${BLUE}Step 2: Building Python backend executable...${NC}"
python -m pip install pyinstaller
pyinstaller --onedir --hidden-import=chromadb --hidden-import=sentence_transformers \
    --hidden-import=ollama --hidden-import=fitz --add-data="app:app" \
    --name=buddhist-rag-backend app/main.py

echo -e "${GREEN}✓ Python backend built${NC}"

echo -e "${BLUE}Step 3: Installing Electron dependencies...${NC}"
cd ../electron-app
npm install
echo -e "${GREEN}✓ Electron dependencies installed${NC}"

echo -e "${BLUE}Step 4: Building Electron application...${NC}"

# Create dist directory structure
mkdir -p dist/resources/python-backend
cp -r ../python-backend/dist/buddhist-rag-backend/* dist/resources/python-backend/

# Build for current platform
npm run build

echo -e "${GREEN}✓ Electron application built${NC}"

echo -e "${BLUE}Step 5: Creating distribution packages...${NC}"

# Build for all platforms if requested
if [ "$1" = "all" ]; then
    npm run build-all
    echo -e "${GREEN}✓ Built for all platforms${NC}"
else
    echo -e "${YELLOW}Built for current platform only. Use './build.sh all' for all platforms${NC}"
fi

cd ..

echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${BLUE}Distribution files are in: electron-app/dist/${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the built application"
echo "2. Ensure Ollama is installed on target systems"
echo "3. Download the qwen2.5:7b model: ollama pull qwen2.5:7b"
echo ""
echo -e "${GREEN}Happy exploring Buddhist wisdom! 🙏${NC}"