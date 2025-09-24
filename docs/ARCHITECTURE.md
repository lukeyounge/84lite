# Buddhist RAG - Architecture Overview

This document provides a technical overview of the Buddhist RAG application architecture, implementation details, and design decisions.

## System Architecture

### High-Level Overview

```
┌─────────────────┐    HTTP/REST    ┌──────────────────────┐
│  Electron App   │ ◄──────────────► │   FastAPI Backend    │
│   (Frontend)    │                 │   (Python Server)    │
└─────────────────┘                 └──────────────────────┘
         │                                      │
         │                                      ▼
         ▼                          ┌──────────────────────┐
┌─────────────────┐                 │    RAG Engine        │
│   File System   │                 │  ┌─────────────────┐ │
│   - PDFs        │                 │  │ PDF Processor   │ │
│   - Vector DB   │ ◄───────────────┼──│ Vector Store    │ │
│   - User Data   │                 │  │ LLM Client      │ │
└─────────────────┘                 │  └─────────────────┘ │
                                    └──────────────────────┘
                                             │
                                             ▼
                                    ┌──────────────────────┐
                                    │   External Services  │
                                    │  ┌─────────────────┐ │
                                    │  │ Ollama Server   │ │
                                    │  │ Qwen 2.5 7B     │ │
                                    │  └─────────────────┘ │
                                    └──────────────────────┘
```

### Component Breakdown

#### 1. Frontend (Electron Application)
- **Technology**: Electron + HTML/CSS/JavaScript
- **Purpose**: Desktop application interface
- **Key Features**:
  - Cross-platform desktop app
  - File upload and drag-and-drop
  - Chat interface with real-time responses
  - Document management
  - System status monitoring

#### 2. Backend (Python FastAPI Server)
- **Technology**: FastAPI + Python 3.8+
- **Purpose**: Core processing engine and API
- **Key Features**:
  - RESTful API for frontend communication
  - PDF processing and text extraction
  - Vector database management
  - LLM integration and prompt management

#### 3. RAG Engine (Core Processing)
- **Technology**: Custom Python modules
- **Purpose**: Retrieval-Augmented Generation pipeline
- **Components**:
  - PDF Processor
  - Vector Store
  - LLM Client
  - Citation Tracking

#### 4. External Services
- **Ollama**: Local LLM server
- **Qwen 2.5 7B**: Language model for responses

## Detailed Component Analysis

### Frontend Architecture

#### Main Process (main.js)
```javascript
// Key responsibilities:
- Application lifecycle management
- Python backend process spawning
- Window management and menus
- IPC communication setup
- File system access
```

**Design Decisions**:
- **Process Management**: Backend starts automatically with frontend
- **Health Monitoring**: Regular backend health checks
- **Resource Cleanup**: Proper backend termination on app close

#### Renderer Process (renderer.js)
```javascript
// Key responsibilities:
- User interface logic
- API communication with backend
- Document library management
- Chat interface and message handling
- Real-time status updates
```

**Design Patterns**:
- **Class-based Architecture**: Single `BuddhistRAGApp` class manages state
- **Event-driven UI**: Responsive interface with loading states
- **Error Handling**: Graceful degradation and user feedback

### Backend Architecture

#### FastAPI Server (main.py)
```python
# Key endpoints:
- POST /upload_pdf: Document processing
- POST /query: Question answering
- GET /documents: Library management
- GET /health: System status
- DELETE /documents/{id}: Document removal
```

**Design Patterns**:
- **Dependency Injection**: RAG engine singleton
- **Async/Await**: Non-blocking operations
- **Error Handling**: Proper HTTP status codes and error responses
- **CORS Configuration**: Frontend-backend communication

#### PDF Processor (pdf_processor.py)

**Buddhist Text-Aware Chunking**:
```python
class BuddhistTextChunk:
    # Represents a semantic unit of Buddhist text
    - content: str          # The actual text
    - page_num: int         # Source page reference
    - chunk_type: str       # Section type (sutta, teaching, etc.)
    - metadata: dict        # Buddhist terminology counts, etc.
```

**Key Features**:
- **Semantic Boundaries**: Respects sutta structure and paragraph breaks
- **Buddhist Term Recognition**: Identifies Pali, Sanskrit, and English terms
- **Tradition Detection**: Estimates Buddhist tradition (Theravada, Mahayana, etc.)
- **Citation Tracking**: Maintains page and section references

**Chunking Algorithm**:
1. Extract text with page metadata
2. Identify section breaks using Buddhist text patterns
3. Split long sections while preserving semantic meaning
4. Classify chunk types (dialogue, teaching, commentary)
5. Filter meaningful content and calculate Buddhist term density

#### Vector Store (vector_store.py)

**ChromaDB Integration**:
```python
# Collection structure:
- Documents: Actual text chunks
- Metadata: Source, page, type, Buddhist concepts
- Embeddings: Generated via sentence-transformers
- IDs: Unique chunk identifiers
```

**Search Capabilities**:
- **Semantic Search**: Vector similarity matching
- **Hybrid Search**: Combines similarity with Buddhist term boosting
- **Filtered Search**: By document, tradition, or content type
- **Citation Retrieval**: Maintains source tracking through pipeline

**Embedding Model**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Language Support**: Multilingual
- **Performance**: Good balance of speed and quality
- **Size**: ~90MB model download

#### LLM Client (llm_client.py)

**Ollama Integration**:
```python
# Model configuration:
- Model: qwen2.5:7b
- Context Length: 32,768 tokens
- Temperature: 0.3 (balanced creativity/accuracy)
- Response Length: Up to 2048 tokens
```

**Buddhist-Specific Prompting**:
- **System Prompt**: Respectful approach to Buddhist teachings
- **Context Formatting**: Proper citation integration
- **Response Guidelines**: Encourages source-based answers
- **Cultural Sensitivity**: Non-denominational presentation

**Prompt Engineering**:
```python
def _create_buddhist_system_prompt():
    # Guidelines for respectful Buddhist AI responses:
    1. Reverent treatment of teachings
    2. Source-based answers with citations
    3. Acknowledgment of tradition differences
    4. Humble uncertainty when appropriate
    5. Encouragement of further study
```

### RAG Engine (rag_engine.py)

**Pipeline Architecture**:
1. **Document Ingestion**: PDF → Chunks → Embeddings → Storage
2. **Query Processing**: Question → Search → Context → LLM → Response
3. **Citation Tracking**: Source references maintained throughout
4. **Response Enhancement**: Similar passages and related content

**Key Algorithms**:

**Semantic Search Enhancement**:
```python
async def hybrid_search():
    # 1. Vector similarity search
    base_results = vector_search(query)

    # 2. Buddhist term boosting
    for result in base_results:
        term_count = count_buddhist_terms(result.content)
        result.score *= (1 + 0.1 * term_count)

    # 3. Recency boosting (optional)
    if boost_recent:
        boost_by_upload_date(results)

    return sorted_results
```

**Citation Integration**:
```python
def _format_sources_for_response():
    # Creates structured citations:
    {
        "content": "Passage text...",
        "source_file": "majjhima_nikaya.pdf",
        "page_number": 42,
        "citation": "majjhima_nikaya.pdf, page 42",
        "similarity_score": 0.89
    }
```

## Data Flow

### Document Processing Flow

1. **Upload**: User drags PDF to frontend
2. **Transfer**: File sent via multipart form to backend
3. **Processing**: PDF → Text extraction → Buddhist-aware chunking
4. **Vectorization**: Chunks → Embeddings via sentence-transformers
5. **Storage**: ChromaDB stores vectors + metadata
6. **Response**: Success confirmation + document stats

### Query Processing Flow

1. **Question**: User types question in chat interface
2. **Search**: Backend searches vector database for relevant chunks
3. **Enhancement**: Buddhist term boosting + similarity ranking
4. **Context**: Top passages formatted with citations
5. **Generation**: Ollama generates response using context
6. **Citation**: Response includes formatted source references
7. **Display**: Frontend renders answer with clickable citations

## Security & Privacy

### Local-First Architecture
- **No Cloud Services**: All processing happens locally
- **Data Ownership**: User controls all data
- **Network Isolation**: Only localhost communication after setup

### File System Security
```
user_data/
├── pdfs/              # Original PDF files
├── vector_store/      # ChromaDB files
├── document_registry.json  # Document metadata
└── logs/              # Application logs
```

### API Security
- **CORS**: Restricted to localhost
- **Input Validation**: Pydantic models for all requests
- **File Type Validation**: Only PDF files accepted
- **Resource Limits**: Timeouts and size restrictions

## Performance Considerations

### Memory Management
- **Model Loading**: Qwen 2.5 7B requires ~8GB RAM
- **Vector Storage**: ChromaDB optimized for local usage
- **Chunk Processing**: Batched operations to prevent memory spikes
- **Embedding Cache**: Reuses embeddings when possible

### Processing Optimization
- **Async Operations**: Non-blocking PDF processing
- **Streaming Responses**: Real-time LLM output
- **Connection Pooling**: Efficient database operations
- **Caching**: Document metadata and statistics

### Scalability
- **Document Limits**: Tested with hundreds of documents
- **Search Performance**: Sub-second response for most queries
- **Storage Growth**: Vector database grows linearly with content
- **Resource Monitoring**: Built-in health checks and status reporting

## Technology Stack Rationale

### Frontend: Electron
**Advantages**:
- Cross-platform desktop deployment
- Familiar web technologies (HTML/CSS/JS)
- Strong file system integration
- Native OS integration (menus, notifications)

**Trade-offs**:
- Larger application size vs. native apps
- Memory overhead vs. web application

### Backend: Python + FastAPI
**Advantages**:
- Rich ecosystem for AI/ML libraries
- FastAPI's automatic API documentation
- Async support for concurrent operations
- Easy integration with ML models

**Trade-offs**:
- Startup time vs. compiled languages
- Memory usage vs. lightweight alternatives

### Vector Database: ChromaDB
**Advantages**:
- Local deployment (no external dependencies)
- Simple Python integration
- Good performance for desktop scale
- Automatic embedding management

**Trade-offs**:
- Less optimized vs. enterprise solutions
- Limited clustering vs. distributed databases

### LLM: Qwen 2.5 7B via Ollama
**Advantages**:
- Strong performance for 7B parameter model
- Local deployment preserves privacy
- Ollama provides easy management
- Good multilingual support

**Trade-offs**:
- Resource requirements vs. smaller models
- Response time vs. cloud APIs

## Deployment Architecture

### Development Environment
```bash
# Backend development server
cd python-backend && python -m uvicorn app.main:app --reload

# Frontend development
cd electron-app && npm run dev
```

### Production Build
```bash
# Automated build process
./scripts/build.sh

# Creates:
- Bundled Python backend (PyInstaller)
- Packaged Electron app (electron-builder)
- Platform-specific installers
```

### Distribution Strategy
- **Self-contained packages**: Include all dependencies
- **Automated setup**: Scripts for Ollama installation
- **Cross-platform builds**: Windows, macOS, Linux support
- **Portable versions**: No-install options available

## Future Architecture Considerations

### Planned Enhancements
- **Plugin system**: Custom Buddhist text processors
- **Multi-model support**: Alternative LLM backends
- **Advanced search**: Temporal queries, cross-references
- **Collaborative features**: Shared libraries and annotations

### Scalability Improvements
- **Distributed processing**: For very large text collections
- **Model optimization**: Fine-tuning for Buddhist domain
- **Performance monitoring**: Detailed usage analytics
- **Resource optimization**: Memory and CPU efficiency

---

*This architecture balances performance, privacy, and respectful treatment of Buddhist teachings while maintaining technical excellence.* 🙏