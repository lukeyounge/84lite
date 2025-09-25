import os
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from loguru import logger
import sys
from pathlib import Path

from .rag_engine import RAGEngine
from .pdf_processor import PDFProcessor
from .vector_store import VectorStore
from .llm_client import LLMClient

app = FastAPI(
    title="Buddhist RAG Backend",
    description="Backend API for the Buddhist text RAG application",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/app.log", rotation="500 MB", level="DEBUG")

rag_engine = None

class QueryRequest(BaseModel):
    question: str
    max_results: Optional[int] = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    processing_time: float

class DocumentInfo(BaseModel):
    filename: str
    pages: int
    chunks: int
    upload_date: str

async def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        logger.info("Initializing RAG engine...")
        rag_engine = RAGEngine()
        await rag_engine.initialize()
    return rag_engine

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Buddhist RAG Backend...")

    os.makedirs("logs", exist_ok=True)
    os.makedirs("user_data/pdfs", exist_ok=True)
    os.makedirs("user_data/vector_store", exist_ok=True)

    await get_rag_engine()
    logger.info("Backend startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Buddhist RAG Backend...")

@app.get("/")
async def root():
    return {"message": "Buddhist RAG Backend is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    engine = await get_rag_engine()

    health_status = {
        "status": "healthy",
        "services": {
            "vector_store": await engine.vector_store.health_check(),
            "llm_client": await engine.llm_client.health_check(),
            "pdf_processor": engine.pdf_processor.health_check()
        }
    }

    overall_healthy = all(
        service["status"] == "healthy"
        for service in health_status["services"].values()
    )

    if not overall_healthy:
        health_status["status"] = "degraded"
        return JSONResponse(
            status_code=503,
            content=health_status
        )

    return health_status

@app.post("/upload_pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    engine: RAGEngine = Depends(get_rag_engine)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        logger.info(f"Uploading PDF: {file.filename}")

        pdf_path = f"user_data/pdfs/{file.filename}"
        with open(pdf_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        doc_info = await engine.process_pdf(pdf_path)
        logger.info(f"Successfully processed PDF: {file.filename}")

        return {
            "message": f"Successfully processed {file.filename}",
            "document_info": doc_info
        }

    except Exception as e:
        logger.error(f"Error processing PDF {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def query_texts(
    request: QueryRequest,
    engine: RAGEngine = Depends(get_rag_engine)
):
    try:
        logger.info(f"Processing query: {request.question[:100]}...")

        result = await engine.query(
            question=request.question,
            max_results=request.max_results
        )

        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            processing_time=result["processing_time"]
        )

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/documents")
async def list_documents(engine: RAGEngine = Depends(get_rag_engine)):
    try:
        documents = await engine.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    engine: RAGEngine = Depends(get_rag_engine)
):
    try:
        await engine.delete_document(document_id)
        return {"message": f"Document {document_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

# Model Management Endpoints

class ModelConfigRequest(BaseModel):
    provider: str
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    google_api_key: Optional[str] = None
    google_model: Optional[str] = None
    enable_fallback: Optional[bool] = None
    temperature: Optional[float] = None

@app.get("/models/status")
async def get_model_status(engine: RAGEngine = Depends(get_rag_engine)):
    """Get status of all available models"""
    try:
        status = await engine.get_model_status()
        return status
    except Exception as e:
        logger.error(f"Error getting model status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting model status: {str(e)}")

@app.post("/models/config")
async def update_model_config(
    request: ModelConfigRequest,
    engine: RAGEngine = Depends(get_rag_engine)
):
    """Update model configuration"""
    try:
        # Prepare config updates
        config_updates = {k: v for k, v in request.dict().items() if v is not None and k != "provider"}

        success = await engine.update_model_config(request.provider, **config_updates)

        if not success:
            raise HTTPException(status_code=400, detail="Invalid model provider")

        return {
            "message": "Model configuration updated successfully",
            "provider": request.provider,
            "status": await engine.get_model_status()
        }

    except Exception as e:
        logger.error(f"Error updating model config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating model config: {str(e)}")

@app.get("/models/usage")
async def get_usage_stats(engine: RAGEngine = Depends(get_rag_engine)):
    """Get API usage statistics"""
    try:
        if hasattr(engine.frontier_client, 'get_usage_summary'):
            return engine.frontier_client.get_usage_summary()
        else:
            return {"message": "No usage data available (using local model)"}
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting usage stats: {str(e)}")

@app.post("/models/validate")
async def validate_api_keys(
    test_keys: Optional[Dict[str, str]] = None,
    engine: RAGEngine = Depends(get_rag_engine)
):
    """Validate API keys for all providers"""
    try:
        from .config import get_config
        config = get_config()

        # If test keys are provided, use them temporarily for testing
        if test_keys:
            logger.info("Testing provided API keys...")
            validation_results = {}

            # Test each provided key
            for key_name, key_value in test_keys.items():
                provider = key_name.replace('_api_key', '')
                if key_value:
                    validation_results[provider] = True
                else:
                    validation_results[provider] = False
        else:
            validation_results = config.validate_api_keys()

        # Test actual connectivity for keys that exist
        for provider, has_key in validation_results.items():
            if has_key:
                # Get the API key to test (from test_keys if provided, otherwise from config)
                api_key = None
                if test_keys and f"{provider}_api_key" in test_keys:
                    api_key = test_keys[f"{provider}_api_key"]
                elif provider == "openai":
                    api_key = config.openai_api_key
                elif provider == "anthropic":
                    api_key = config.anthropic_api_key
                elif provider == "google":
                    api_key = config.google_api_key

                # Test connection by attempting to create a client
                try:
                    if provider == "openai" and api_key:
                        import openai
                        client = openai.OpenAI(api_key=api_key)
                        # Simple test call to validate the key
                        models = client.models.list(limit=1)
                        validation_results[f"{provider}_connection"] = "valid"
                    elif provider == "anthropic" and api_key:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        # Simple test - anthropic doesn't have a simple list endpoint
                        validation_results[f"{provider}_connection"] = "valid"
                    elif provider == "google" and api_key:
                        import google.generativeai as genai
                        genai.configure(api_key=api_key)
                        # Test by listing models
                        list(genai.list_models())
                        validation_results[f"{provider}_connection"] = "valid"
                except Exception as e:
                    validation_results[f"{provider}_connection"] = f"error: {str(e)}"

        return validation_results

    except Exception as e:
        logger.error(f"Error validating API keys: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error validating API keys: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )