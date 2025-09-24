import time
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger
import json
from datetime import datetime

from .pdf_processor import PDFProcessor
from .vector_store import VectorStore
from .llm_client import LLMClient

class RAGEngine:
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.vector_store = VectorStore()
        self.llm_client = LLMClient()
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return

        logger.info("Initializing RAG Engine...")

        await self.vector_store.initialize()
        logger.info("RAG Engine initialized successfully")
        self.initialized = True

    async def process_pdf(self, pdf_path: str) -> Dict:
        if not self.initialized:
            await self.initialize()

        logger.info(f"Processing PDF through RAG pipeline: {pdf_path}")
        start_time = time.time()

        try:
            processed_data = self.pdf_processor.process_pdf(pdf_path)
            chunks = processed_data["chunks"]
            document_info = processed_data["document_info"]

            if not chunks:
                return {
                    "status": "warning",
                    "message": "No meaningful content extracted from PDF",
                    "document_info": document_info,
                    "processing_time": time.time() - start_time
                }

            vector_result = await self.vector_store.add_chunks(chunks)

            processing_time = time.time() - start_time
            logger.info(f"PDF processing completed in {processing_time:.2f} seconds")

            await self._update_document_registry(pdf_path, document_info, processing_time)

            return {
                "status": "success",
                "message": f"Successfully processed {document_info['filename']}",
                "document_info": document_info,
                "vector_result": vector_result,
                "processing_time": processing_time,
                "chunks_processed": len(chunks)
            }

        except Exception as e:
            logger.error(f"Error in RAG pipeline for {pdf_path}: {str(e)}")
            raise

    async def query(self, question: str, max_results: int = 5,
                   filter_by_source: Optional[str] = None,
                   include_similar: bool = True) -> Dict:
        if not self.initialized:
            await self.initialize()

        logger.info(f"Processing query: {question[:100]}...")
        start_time = time.time()

        try:
            filter_metadata = None
            if filter_by_source:
                filter_metadata = {"source_file": filter_by_source}

            search_results = await self.vector_store.hybrid_search(
                query=question,
                max_results=max_results,
                boost_buddhist_terms=True
            )

            if not search_results:
                return {
                    "answer": "I couldn't find relevant passages in your Buddhist text library to answer this question. Consider uploading more texts or rephrasing your question.",
                    "sources": [],
                    "processing_time": time.time() - start_time,
                    "search_results_count": 0
                }

            enhanced_sources = await self._enhance_sources(search_results, include_similar)

            llm_response = await self.llm_client.generate_response(
                question=question,
                context_passages=enhanced_sources
            )

            processing_time = time.time() - start_time

            formatted_sources = self._format_sources_for_response(enhanced_sources)

            return {
                "answer": llm_response["response"],
                "sources": formatted_sources,
                "processing_time": processing_time,
                "search_results_count": len(search_results),
                "model_info": {
                    "model": llm_response["model"],
                    "generation_time": llm_response["processing_time"],
                    "context_passages_used": llm_response["context_passages_used"]
                }
            }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise

    async def _enhance_sources(self, search_results: List[Dict],
                              include_similar: bool = True) -> List[Dict]:
        enhanced_sources = []

        for result in search_results:
            enhanced_result = result.copy()

            if include_similar and result["metadata"].get("chunk_id"):
                try:
                    similar_chunks = await self.vector_store.get_similar_chunks(
                        result["metadata"]["chunk_id"],
                        max_results=2
                    )
                    enhanced_result["similar_passages"] = similar_chunks
                except Exception as e:
                    logger.warning(f"Could not find similar chunks: {str(e)}")
                    enhanced_result["similar_passages"] = []

            enhanced_sources.append(enhanced_result)

        return enhanced_sources

    def _format_sources_for_response(self, sources: List[Dict]) -> List[Dict]:
        formatted_sources = []

        for i, source in enumerate(sources):
            metadata = source["metadata"]

            formatted_source = {
                "id": i + 1,
                "content": source["content"],
                "source_file": metadata.get("source_file", "Unknown"),
                "page_number": metadata.get("page_num", "Unknown"),
                "chunk_type": metadata.get("chunk_type", "paragraph"),
                "similarity_score": round(source["similarity_score"], 3),
                "word_count": metadata.get("word_count", 0),
                "citation": f"{metadata.get('source_file', 'Unknown source')}, page {metadata.get('page_num', '?')}"
            }

            if source.get("similar_passages"):
                formatted_source["similar_passages"] = [
                    {
                        "content": sp["content"][:200] + "..." if len(sp["content"]) > 200 else sp["content"],
                        "source_file": sp["metadata"].get("source_file", "Unknown"),
                        "page_number": sp["metadata"].get("page_num", "Unknown")
                    }
                    for sp in source["similar_passages"]
                ]

            formatted_sources.append(formatted_source)

        return formatted_sources

    async def list_documents(self) -> List[Dict]:
        if not self.initialized:
            await self.initialize()

        try:
            stats = await self.vector_store.get_collection_stats()
            documents = stats.get("documents", [])

            enhanced_documents = []
            for doc in documents:
                doc_info = await self._get_document_info(doc["filename"])
                enhanced_doc = {
                    **doc,
                    **doc_info
                }
                enhanced_documents.append(enhanced_doc)

            return enhanced_documents

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            raise

    async def delete_document(self, document_identifier: str):
        if not self.initialized:
            await self.initialize()

        try:
            if document_identifier.endswith('.pdf'):
                source_file = document_identifier
            else:
                docs = await self.list_documents()
                matching_doc = next((doc for doc in docs if doc.get("id") == document_identifier), None)
                if not matching_doc:
                    raise ValueError(f"Document with ID {document_identifier} not found")
                source_file = matching_doc["filename"]

            result = await self.vector_store.delete_document(source_file)

            await self._remove_from_document_registry(source_file)

            logger.info(f"Deleted document: {source_file}")
            return result

        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise

    async def get_document_summary(self, source_file: str) -> str:
        if not self.initialized:
            await self.initialize()

        try:
            chunks = await self.vector_store.get_document_chunks(source_file)
            if not chunks:
                return "No content available for this document."

            summary = await self.llm_client.summarize_document(
                chunks, source_file
            )

            return summary

        except Exception as e:
            logger.error(f"Error generating document summary: {str(e)}")
            return f"Unable to generate summary: {str(e)}"

    async def get_statistics(self) -> Dict:
        if not self.initialized:
            await self.initialize()

        try:
            collection_stats = await self.vector_store.get_collection_stats()

            health_checks = {
                "vector_store": await self.vector_store.health_check(),
                "llm_client": await self.llm_client.health_check()
            }

            model_info = await self.llm_client.get_model_info()

            return {
                "system_status": {
                    "initialized": self.initialized,
                    "services_healthy": all(
                        service["status"] == "healthy"
                        for service in health_checks.values()
                    )
                },
                "collection_stats": collection_stats,
                "health_checks": health_checks,
                "model_info": model_info,
                "capabilities": {
                    "pdf_processing": True,
                    "semantic_search": True,
                    "citation_tracking": True,
                    "buddhist_text_awareness": True,
                    "streaming_responses": True
                }
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            raise

    async def _update_document_registry(self, pdf_path: str, document_info: Dict,
                                       processing_time: float):
        registry_path = Path("user_data/document_registry.json")

        try:
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
            else:
                registry = {"documents": {}}

            registry["documents"][document_info["filename"]] = {
                "path": pdf_path,
                "processing_date": datetime.now().isoformat(),
                "processing_time": processing_time,
                "document_hash": document_info["document_hash"],
                "pages": document_info["pages"],
                "chunks": document_info["meaningful_chunks"],
                "detected_language": document_info["detected_language"],
                "estimated_tradition": document_info["estimated_tradition"]
            }

            registry_path.parent.mkdir(exist_ok=True)
            with open(registry_path, 'w') as f:
                json.dump(registry, f, indent=2)

        except Exception as e:
            logger.warning(f"Could not update document registry: {str(e)}")

    async def _remove_from_document_registry(self, filename: str):
        registry_path = Path("user_data/document_registry.json")

        try:
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)

                if filename in registry.get("documents", {}):
                    del registry["documents"][filename]

                    with open(registry_path, 'w') as f:
                        json.dump(registry, f, indent=2)

        except Exception as e:
            logger.warning(f"Could not update document registry: {str(e)}")

    async def _get_document_info(self, filename: str) -> Dict:
        registry_path = Path("user_data/document_registry.json")

        try:
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)

                doc_info = registry.get("documents", {}).get(filename, {})
                if doc_info:
                    return {
                        "id": filename,
                        "processing_date": doc_info.get("processing_date"),
                        "document_hash": doc_info.get("document_hash"),
                        "detected_language": doc_info.get("detected_language"),
                        "estimated_tradition": doc_info.get("estimated_tradition"),
                        "processing_time": doc_info.get("processing_time")
                    }

        except Exception as e:
            logger.warning(f"Could not read document registry: {str(e)}")

        return {"id": filename}

    async def search_similar_content(self, content: str, max_results: int = 5) -> List[Dict]:
        if not self.initialized:
            await self.initialize()

        try:
            results = await self.vector_store.search(
                query=content,
                max_results=max_results
            )

            return self._format_sources_for_response(results)

        except Exception as e:
            logger.error(f"Error searching similar content: {str(e)}")
            raise

    async def get_conversation_context(self, recent_queries: List[str],
                                     max_context: int = 3) -> List[Dict]:
        if not recent_queries or not self.initialized:
            return []

        try:
            all_context = []

            for query in recent_queries[-max_context:]:
                results = await self.vector_store.search(query, max_results=2)
                all_context.extend(results)

            unique_context = []
            seen_chunks = set()

            for result in all_context:
                chunk_id = result["metadata"].get("chunk_id")
                if chunk_id and chunk_id not in seen_chunks:
                    unique_context.append(result)
                    seen_chunks.add(chunk_id)

            return unique_context[:5]

        except Exception as e:
            logger.warning(f"Could not get conversation context: {str(e)}")
            return []