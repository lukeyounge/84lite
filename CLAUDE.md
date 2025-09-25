# Buddhist RAG Application

## Overview
A desktop application for querying Buddhist texts using Retrieval-Augmented Generation (RAG) technology. Built with Electron frontend and FastAPI Python backend.

## Current Status: ✅ WORKING
- Backend: FastAPI server running on port 8000
- Frontend: Electron desktop application
- LLM Integration: Qwen 2.5 14B via Ollama + Frontier model support
- Vector Store: ChromaDB with sentence transformers
- Document Processing: PDF ingestion and chunking

## Quick Start

### Backend
```bash
cd python-backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```bash
cd electron-app
npm install
npm start
```

## Architecture

### Backend Components
- **RAGEngine** (`app/rag_engine.py`): Main orchestration class
- **LLMClient** (`app/llm_client.py`): Local Ollama integration
- **FrontierLLMClient** (`app/frontier_llm_client.py`): OpenAI/Anthropic/Google API support
- **VectorStore** (`app/vector_store.py`): ChromaDB with semantic search
- **PDFProcessor** (`app/pdf_processor.py`): Document parsing and chunking
- **Config** (`app/config.py`): Environment and model provider management

### Frontend Components
- **Electron Main** (`main.js`): Desktop app wrapper
- **Renderer** (`renderer.js`): UI logic and API communication
- **Styles** (`styles.css`): Modern UI design
- **HTML** (`index.html`): Single-page application structure

## Key Features

### 🔧 Model Provider Support
- **Local**: Qwen 2.5 14B via Ollama (primary)
- **OpenAI**: GPT-4 Turbo/GPT-3.5 support
- **Anthropic**: Claude 3.5 Sonnet support
- **Google**: Gemini Pro support
- **Fallback**: Automatic fallback to local model if API fails

### 🎛️ Settings Interface
- Accessible via gear icon (⚙️) in top right corner
- API key management for all providers
- Usage statistics and cost tracking
- Privacy settings and data transmission controls
- Real-time model status monitoring

### 📚 Document Management
- PDF upload and processing
- Buddhist text-aware chunking
- Semantic search with similarity scoring
- Source citation tracking
- Document statistics and metadata

### 💬 Query Interface
- Natural language questions
- Context-aware responses with sources
- Processing time metrics
- Example questions for guidance
- Conversation history support

## Configuration

### Environment Variables (.env)
```bash
# Model Provider Selection
MODEL_PROVIDER=local  # local, openai, anthropic, google
ENABLE_FALLBACK=true

# Local Model Settings
LOCAL_MODEL_NAME=qwen2.5:14b
OLLAMA_BASE_URL=http://localhost:11434

# API Keys (optional)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# Model Parameters
MAX_CONTEXT_LENGTH=32768
MAX_RESPONSE_LENGTH=2048
TEMPERATURE=0.3
TOP_P=0.9

# Usage Settings
WARN_ON_API_USAGE=true
MAX_DAILY_API_CALLS=100
ALLOW_DATA_TRANSMISSION=false
```

### Dependencies
**Backend:**
- fastapi, uvicorn
- chromadb, sentence-transformers
- ollama-python
- openai, anthropic, google-generativeai
- pypdf2, python-multipart

**Frontend:**
- electron
- axios (for API communication)

## API Endpoints

### Core Functionality
- `GET /health` - System health check
- `POST /upload_pdf` - Upload Buddhist texts
- `POST /query` - Ask questions about texts
- `GET /documents` - List uploaded documents
- `DELETE /documents/{id}` - Remove documents

### Model Management
- `GET /models/status` - Check all model availability
- `POST /models/config` - Update model settings
- `GET /models/usage` - View API usage statistics
- `POST /models/validate` - Validate API keys

## Troubleshooting

### Common Issues Fixed
1. **Ollama Connection**: Fixed model object access in `llm_client.py`
2. **Electron Installation**: Resolved npm timeout issues
3. **Settings Access**: Added missing gear icon and modal functionality
4. **Model Display**: Fixed hardcoded model version text

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

Expected response shows all services healthy:
```json
{
  "status": "healthy",
  "services": {
    "vector_store": {"status": "healthy"},
    "llm_client": {"status": "healthy", "model": "qwen2.5:14b"},
    "pdf_processor": {"status": "healthy"}
  }
}
```

## Recent Updates
- ✅ Fixed Ollama client integration issues
- ✅ Added comprehensive frontier model support
- ✅ Implemented settings UI with gear icon
- ✅ Added API key management and validation
- ✅ Enhanced privacy controls and usage tracking
- ✅ Improved error handling and fallback mechanisms

## Usage
1. Start both backend and frontend services
2. Upload Buddhist PDF texts via the library section
3. Configure API models via settings gear icon (⚙️)
4. Ask questions about the teachings
5. Explore sources and citations for deeper study

The application is fully functional for Buddhist text analysis and question-answering with multiple AI model options.