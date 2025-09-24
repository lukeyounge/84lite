# Buddhist RAG Desktop Application

A desktop application for semantic search and question-answering with Buddhist texts using local AI models.

## Features

- 🏛️ **Local & Private**: Everything runs on your computer, no internet required after setup
- 📚 **PDF Library**: Upload and manage your Buddhist text collection (suttas, dharma books, etc.)
- 🔍 **Semantic Search**: Find relevant passages based on meaning, not just keywords
- 🤖 **Respectful AI**: Generate thoughtful responses about Buddhist teachings using Qwen 2.5 7B
- 📖 **Source Citations**: Always references which text and page the answer comes from
- 🖥️ **Cross-Platform**: Works on Windows, Mac, and Linux

## Quick Start

1. **Install Ollama** and download the Qwen 2.5 7B model:
   ```bash
   # Install Ollama (see https://ollama.ai/download)
   ollama pull qwen2.5:7b
   ```

2. **Download** the latest release for your platform from the releases page

3. **Run** the application and start uploading your Buddhist PDFs

4. **Ask questions** about the teachings and explore the wisdom within your texts

## Technical Stack

- **Desktop**: Electron with clean HTML/CSS/JS interface
- **Backend**: Python with FastAPI for the RAG engine
- **AI Model**: Qwen 2.5 7B via Ollama (local deployment)
- **Vector DB**: ChromaDB for semantic search
- **PDF Processing**: PyMuPDF with Buddhist text-aware chunking
- **Embeddings**: sentence-transformers for high-quality text representation

## System Requirements

- **RAM**: 8GB+ (for running Qwen 2.5 7B locally)
- **Storage**: 5GB+ free space (for models and texts)
- **OS**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [User Guide](docs/USER_GUIDE.md) - How to use the application
- [Architecture](docs/ARCHITECTURE.md) - Technical implementation details

## License

MIT License - See LICENSE file for details

## Contributing

This project welcomes contributions that improve the respectful presentation of Buddhist teachings and enhance the technical implementation.