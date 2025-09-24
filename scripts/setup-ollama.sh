#!/bin/bash

# Ollama Setup Script for Buddhist RAG App
# Downloads and installs Ollama and the required Qwen model

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🙏 Setting up Ollama for Buddhist RAG...${NC}"

# Detect operating system
OS="$(uname -s)"
ARCH="$(uname -m)"

echo -e "${BLUE}Detected: $OS $ARCH${NC}"

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama is already installed$(NC)"
    OLLAMA_VERSION=$(ollama --version | head -n 1 || echo "unknown")
    echo -e "${BLUE}Version: $OLLAMA_VERSION${NC}"
else
    echo -e "${YELLOW}Installing Ollama...${NC}"

    case $OS in
        "Darwin")
            # macOS installation
            echo -e "${BLUE}Installing Ollama for macOS...${NC}"
            if command -v brew &> /dev/null; then
                brew install ollama
            else
                echo -e "${YELLOW}Homebrew not found. Please install Ollama manually:${NC}"
                echo "Visit: https://ollama.ai/download"
                echo "Or run: curl -fsSL https://ollama.ai/install.sh | sh"
                exit 1
            fi
            ;;
        "Linux")
            # Linux installation
            echo -e "${BLUE}Installing Ollama for Linux...${NC}"
            curl -fsSL https://ollama.ai/install.sh | sh
            ;;
        *)
            echo -e "${RED}Unsupported operating system: $OS${NC}"
            echo -e "${YELLOW}Please install Ollama manually from: https://ollama.ai/download${NC}"
            exit 1
            ;;
    esac

    echo -e "${GREEN}✓ Ollama installed successfully${NC}"
fi

# Start Ollama service
echo -e "${BLUE}Starting Ollama service...${NC}"

case $OS in
    "Darwin")
        # macOS - start with launchd
        if ! pgrep -f "ollama serve" > /dev/null; then
            echo -e "${YELLOW}Starting Ollama service...${NC}"
            ollama serve &
            sleep 5
        fi
        ;;
    "Linux")
        # Linux - start with systemd or direct command
        if systemctl is-active --quiet ollama 2>/dev/null; then
            echo -e "${GREEN}✓ Ollama service is already running${NC}"
        elif command -v systemctl &> /dev/null; then
            sudo systemctl start ollama
            sudo systemctl enable ollama
        else
            # Fallback: start directly
            if ! pgrep -f "ollama serve" > /dev/null; then
                ollama serve &
                sleep 5
            fi
        fi
        ;;
esac

# Wait for Ollama to be ready
echo -e "${BLUE}Waiting for Ollama to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:11434/api/version &> /dev/null; then
        echo -e "${GREEN}✓ Ollama is ready${NC}"
        break
    fi

    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Ollama failed to start within 30 seconds${NC}"
        echo -e "${YELLOW}Please check if Ollama is running: ollama serve${NC}"
        exit 1
    fi

    sleep 1
done

# Download the Qwen 2.5 7B model
echo -e "${BLUE}Downloading Qwen 2.5 7B model (this may take several minutes)...${NC}"
echo -e "${YELLOW}Model size: ~4.7GB - ensure you have sufficient disk space${NC}"

if ollama list | grep -q "qwen2.5:7b"; then
    echo -e "${GREEN}✓ Qwen 2.5 7B model already installed${NC}"
else
    echo -e "${BLUE}Pulling qwen2.5:7b model...${NC}"
    ollama pull qwen2.5:7b

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Qwen 2.5 7B model downloaded successfully${NC}"
    else
        echo -e "${RED}✗ Failed to download Qwen 2.5 7B model${NC}"
        echo -e "${YELLOW}You can try downloading it manually: ollama pull qwen2.5:7b${NC}"
        exit 1
    fi
fi

# Test the model
echo -e "${BLUE}Testing the model...${NC}"
TEST_RESPONSE=$(ollama run qwen2.5:7b "What is mindfulness?" --timeout 30s 2>/dev/null || echo "")

if [ -n "$TEST_RESPONSE" ]; then
    echo -e "${GREEN}✓ Model test successful${NC}"
else
    echo -e "${YELLOW}⚠ Model test timed out or failed, but installation appears complete${NC}"
fi

# Show installed models
echo -e "${BLUE}Installed models:${NC}"
ollama list

echo ""
echo -e "${GREEN}🎉 Ollama setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}Setup Summary:${NC}"
echo "• Ollama service is running"
echo "• Qwen 2.5 7B model is installed"
echo "• Ready for Buddhist RAG application"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "• Ollama runs on port 11434 by default"
echo "• The model uses approximately 4.7GB of disk space"
echo "• For best performance, ensure you have at least 8GB RAM"
echo ""
echo -e "${BLUE}To manually start Ollama in the future:${NC}"
echo "  ollama serve"
echo ""
echo -e "${BLUE}To test the model:${NC}"
echo "  ollama run qwen2.5:7b \"What is Buddhism?\""
echo ""
echo -e "${GREEN}You can now run the Buddhist RAG application! 🙏${NC}"