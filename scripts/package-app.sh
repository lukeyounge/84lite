#!/bin/bash

# Package Buddhist RAG App for Distribution
# Creates installer packages for different platforms

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Packaging Buddhist RAG Application for Distribution...${NC}"

# Check if build exists
if [ ! -d "electron-app/dist" ]; then
    echo -e "${RED}Error: No build found. Please run ./scripts/build.sh first${NC}"
    exit 1
fi

cd electron-app

echo -e "${BLUE}Step 1: Preparing distribution assets...${NC}"

# Create app icons if they don't exist
if [ ! -f "assets/icon.png" ]; then
    echo -e "${YELLOW}Warning: No app icon found. Using default.${NC}"
    mkdir -p assets
    # Create a simple placeholder icon (you should replace with actual Buddhist-themed icon)
    echo "🙏" > assets/icon.txt
fi

echo -e "${BLUE}Step 2: Building platform-specific packages...${NC}"

# Detect current platform
PLATFORM="$(uname -s)"

case $PLATFORM in
    "Darwin")
        echo -e "${BLUE}Building macOS package (.dmg)...${NC}"
        npm run build -- --mac
        if [ -f "dist/Buddhist RAG-*.dmg" ]; then
            echo -e "${GREEN}✓ macOS DMG package created${NC}"
        fi
        ;;
    "Linux")
        echo -e "${BLUE}Building Linux package (.AppImage)...${NC}"
        npm run build -- --linux
        if [ -f "dist/Buddhist RAG-*.AppImage" ]; then
            echo -e "${GREEN}✓ Linux AppImage package created${NC}"
        fi
        ;;
    "MINGW"*|"CYGWIN"*|"MSYS"*)
        echo -e "${BLUE}Building Windows package (.exe)...${NC}"
        npm run build -- --win
        if [ -f "dist/Buddhist RAG Setup-*.exe" ]; then
            echo -e "${GREEN}✓ Windows installer created${NC}"
        fi
        ;;
esac

echo -e "${BLUE}Step 3: Creating portable package...${NC}"

# Create portable version with setup instructions
PORTABLE_DIR="dist/buddhist-rag-portable"
mkdir -p "$PORTABLE_DIR"

# Copy the appropriate executable
case $PLATFORM in
    "Darwin")
        if [ -d "dist/mac/Buddhist RAG.app" ]; then
            cp -r "dist/mac/Buddhist RAG.app" "$PORTABLE_DIR/"
        fi
        ;;
    "Linux")
        if [ -f "dist/Buddhist RAG-"*".AppImage" ]; then
            cp "dist/Buddhist RAG-"*".AppImage" "$PORTABLE_DIR/"
        fi
        ;;
esac

# Create setup instructions
cat > "$PORTABLE_DIR/README.txt" << 'EOF'
Buddhist RAG - Portable Version
==============================

Welcome to Buddhist RAG! This application helps you explore Buddhist texts
through semantic search and AI-powered insights.

QUICK START:
1. Install Ollama from https://ollama.ai/download
2. Run: ollama pull qwen2.5:7b
3. Launch Buddhist RAG application
4. Upload your Buddhist PDF texts
5. Start asking questions!

SYSTEM REQUIREMENTS:
- 8GB+ RAM (for running Qwen 2.5 7B model)
- 5GB+ free disk space
- Internet connection for initial setup only

TROUBLESHOOTING:
- If the app won't start, ensure Ollama is running: ollama serve
- If you get connection errors, check that port 11434 is available
- For best results, use well-formatted PDF texts

SUPPORTED FORMATS:
- PDF files containing Buddhist texts (suttas, dharma books, etc.)
- English, Pali, and Sanskrit content is supported

For more information, visit:
https://github.com/your-repo/buddhist-rag-app

May your exploration of the Dharma bring wisdom and peace! 🙏
EOF

# Create platform-specific launcher scripts
case $PLATFORM in
    "Darwin")
        cat > "$PORTABLE_DIR/launch.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
open "Buddhist RAG.app"
EOF
        chmod +x "$PORTABLE_DIR/launch.command"
        ;;
    "Linux")
        cat > "$PORTABLE_DIR/launch.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./Buddhist\ RAG-*.AppImage
EOF
        chmod +x "$PORTABLE_DIR/launch.sh"
        ;;
esac

echo -e "${GREEN}✓ Portable package created${NC}"

echo -e "${BLUE}Step 4: Creating installation package with dependencies...${NC}"

# Create full installer package
INSTALLER_DIR="dist/buddhist-rag-installer"
mkdir -p "$INSTALLER_DIR"

# Copy the main application
cp -r "$PORTABLE_DIR"/* "$INSTALLER_DIR/"

# Add Ollama setup script
cp ../scripts/setup-ollama.sh "$INSTALLER_DIR/"
chmod +x "$INSTALLER_DIR/setup-ollama.sh"

# Create comprehensive installer script
cat > "$INSTALLER_DIR/install.sh" << 'EOF'
#!/bin/bash

echo "🙏 Buddhist RAG Application Installer"
echo "===================================="
echo ""

echo "This installer will:"
echo "1. Install Ollama (if not present)"
echo "2. Download the Qwen 2.5 7B model"
echo "3. Set up the Buddhist RAG application"
echo ""

read -p "Continue with installation? [Y/n]: " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Installation cancelled."
    exit 1
fi

echo ""
echo "Starting installation..."

# Run Ollama setup
if [ -f "./setup-ollama.sh" ]; then
    ./setup-ollama.sh
else
    echo "Error: setup-ollama.sh not found"
    exit 1
fi

echo ""
echo "🎉 Installation completed!"
echo ""
echo "To start Buddhist RAG:"

case "$(uname -s)" in
    "Darwin")
        echo "  double-click: Buddhist RAG.app"
        echo "  or run: open 'Buddhist RAG.app'"
        ;;
    "Linux")
        echo "  run: ./Buddhist RAG-*.AppImage"
        echo "  or use: ./launch.sh"
        ;;
esac

echo ""
echo "For help and documentation, see README.txt"
echo ""
echo "May your journey through the Dharma be fruitful! 🙏"
EOF

chmod +x "$INSTALLER_DIR/install.sh"

echo -e "${GREEN}✓ Installation package created${NC}"

cd ..

echo -e "${BLUE}Step 5: Creating distribution archive...${NC}"

# Create timestamped archive
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="buddhist-rag-app-$TIMESTAMP"

cd electron-app/dist
tar -czf "$ARCHIVE_NAME.tar.gz" buddhist-rag-installer/
zip -r "$ARCHIVE_NAME.zip" buddhist-rag-installer/

echo -e "${GREEN}✓ Distribution archives created${NC}"

cd ../..

# Summary
echo ""
echo -e "${GREEN}🎉 Packaging completed successfully!${NC}"
echo ""
echo -e "${BLUE}Distribution Files Created:${NC}"
echo "📁 electron-app/dist/"

# List created files
find electron-app/dist -name "*.dmg" -o -name "*.AppImage" -o -name "*.exe" -o -name "*.tar.gz" -o -name "*.zip" | while read file; do
    SIZE=$(du -h "$file" | cut -f1)
    echo "  📦 $(basename "$file") ($SIZE)"
done

echo ""
echo -e "${BLUE}Installation Packages:${NC}"
echo "  📁 electron-app/dist/buddhist-rag-portable/ - Portable version"
echo "  📁 electron-app/dist/buddhist-rag-installer/ - Full installer with dependencies"

echo ""
echo -e "${YELLOW}Next Steps for Distribution:${NC}"
echo "1. Test the packaged application on target systems"
echo "2. Create installation documentation"
echo "3. Set up distribution channels (GitHub releases, website, etc.)"
echo "4. Consider code signing for production releases"
echo ""
echo -e "${BLUE}Installation Requirements for Users:${NC}"
echo "• 8GB+ RAM for optimal performance"
echo "• 5GB+ disk space for models and app"
echo "• Internet connection for initial Ollama/model download"
echo ""
echo -e "${GREEN}Happy distributing Buddhist wisdom! 🙏${NC}"