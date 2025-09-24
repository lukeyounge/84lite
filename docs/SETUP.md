# Buddhist RAG - Setup Guide

This guide will walk you through setting up the Buddhist RAG desktop application on your system.

## System Requirements

### Minimum Requirements
- **RAM**: 8GB (for running Qwen 2.5 7B model locally)
- **Storage**: 5GB free space (for models, app, and texts)
- **OS**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)
- **Internet**: Required for initial setup only

### Recommended
- **RAM**: 16GB+ for optimal performance
- **Storage**: 10GB+ for larger text collections
- **CPU**: Modern multi-core processor

## Quick Installation

### Option 1: Automated Setup (Recommended)

1. **Download** the latest release from [GitHub Releases](https://github.com/your-repo/buddhist-rag-app/releases)

2. **Extract** the installation package:
   ```bash
   tar -xzf buddhist-rag-app-installer.tar.gz
   cd buddhist-rag-installer
   ```

3. **Run the installer**:
   ```bash
   ./install.sh
   ```

   This will automatically:
   - Install Ollama if not present
   - Download the Qwen 2.5 7B model (~4.7GB)
   - Set up the application

4. **Launch** Buddhist RAG and start exploring!

### Option 2: Manual Setup

If you prefer to install components separately:

#### Step 1: Install Ollama

**macOS:**
```bash
# Using Homebrew
brew install ollama

# Or download from https://ollama.ai/download
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
- Download installer from https://ollama.ai/download
- Run the installer and follow prompts

#### Step 2: Start Ollama Service

```bash
ollama serve
```

#### Step 3: Download the AI Model

```bash
ollama pull qwen2.5:7b
```

This downloads the ~4.7GB model file. Ensure you have sufficient bandwidth and storage.

#### Step 4: Install Buddhist RAG

Download the appropriate package for your platform:
- **macOS**: `Buddhist-RAG-x.x.x.dmg`
- **Linux**: `Buddhist-RAG-x.x.x.AppImage`
- **Windows**: `Buddhist-RAG-Setup-x.x.x.exe`

## Configuration

### First Launch

1. **Start the application** - Buddhist RAG will automatically check for Ollama connectivity
2. **Status indicator** in the header will show:
   - 🟡 **Initializing**: Starting up backend services
   - 🟢 **Ready**: All systems operational
   - 🔴 **Error**: Check Ollama status

### Upload Your First Document

1. **Drag & drop** a Buddhist PDF into the library area, or
2. **Click "Choose Files"** to browse for PDFs
3. **Wait for processing** - first documents may take 1-2 minutes
4. **Start asking questions** once processing completes

## Troubleshooting

### Common Issues

#### "Backend not ready" Error

**Problem**: The application can't connect to Ollama
**Solutions**:
1. Ensure Ollama is running: `ollama serve`
2. Check if port 11434 is available
3. Restart the Buddhist RAG application

#### "Model not found" Error

**Problem**: Qwen 2.5 7B model isn't installed
**Solution**:
```bash
ollama pull qwen2.5:7b
```

#### PDF Processing Fails

**Problem**: Document upload or processing errors
**Causes & Solutions**:
- **Corrupted PDF**: Try a different PDF file
- **Scanned images**: Ensure PDF contains extractable text
- **Large files**: Files >100MB may take longer or timeout
- **Memory issues**: Close other applications to free up RAM

#### Slow Performance

**Problem**: Long response times or high CPU usage
**Optimizations**:
1. **Close other applications** to free up RAM
2. **Use smaller documents** for testing
3. **Check system load** - model requires significant resources
4. **Restart Ollama** if it becomes unresponsive

### Getting Help

#### Check System Status

Use the **Help > Check Ollama Status** menu to verify:
- Ollama service status
- Model availability
- Connection health

#### Log Files

Check logs for detailed error information:
- **macOS**: `~/Library/Logs/Buddhist RAG/`
- **Linux**: `~/.config/Buddhist RAG/logs/`
- **Windows**: `%APPDATA%/Buddhist RAG/logs/`

#### Reset Application

If the application becomes unstable:
1. **Close** Buddhist RAG
2. **Stop Ollama**: `pkill ollama` or close from system tray
3. **Clear cache**: Delete vector database in user data folder
4. **Restart** both services

## Advanced Configuration

### Custom Model Settings

For advanced users, you can modify model parameters by editing the backend configuration. This requires technical knowledge and is not recommended for casual users.

### Resource Allocation

The application automatically manages resources, but you can optimize for your system:

- **High RAM systems (16GB+)**: Can handle larger document collections
- **Limited RAM (8GB)**: Process documents in smaller batches
- **SSD storage**: Significantly improves performance over HDD

### Network Configuration

Buddhist RAG operates entirely locally, but initial setup requires internet:
- **Ollama download**: ~50MB installer
- **Model download**: ~4.7GB for Qwen 2.5 7B
- **Updates**: Check GitHub for new releases

## Security & Privacy

### Local Processing
- **All data stays on your computer** - no cloud services used
- **AI processing** happens locally via Ollama
- **Network access** only required for initial setup

### Data Storage
- **PDFs**: Stored in local user data folder
- **Vector database**: ChromaDB files in user data folder
- **Chat history**: Not permanently stored (session only)

### Permissions
The application requires:
- **File system access**: To read/write PDFs and databases
- **Network access**: Only for Ollama communication (localhost)
- **No external network**: After initial setup

## Next Steps

Once setup is complete:
1. Read the [User Guide](USER_GUIDE.md) for usage instructions
2. Check the [Architecture Guide](ARCHITECTURE.md) for technical details
3. Join the community discussions for tips and Buddhist text recommendations

---

*May your exploration of the Dharma through technology bring wisdom and understanding.* 🙏