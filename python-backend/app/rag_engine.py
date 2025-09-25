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
from .frontier_llm_client import FrontierLLMClient
from .config import get_config, ModelProvider

class RAGEngine:
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.vector_store = VectorStore()
        self.llm_client = LLMClient()  # Local Ollama client (fallback)
        self.frontier_client = FrontierLLMClient()  # Frontier models client
        self.config = get_config()
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return

        logger.info("Initializing RAG Engine...")

        # Initialize vector store
        await self.vector_store.initialize()

        # Initialize frontier client if using API providers
        if self.config.model_provider != ModelProvider.LOCAL:
            try:
                await self.frontier_client.initialize()
                logger.info(f"Initialized frontier client: {self.config.model_provider.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize frontier client: {str(e)}")
                if not self.config.enable_fallback:
                    raise

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

            # Try anchor-aware search first
            search_results = await self._anchor_enhanced_search(
                question, max_results, filter_metadata
            )

            if not search_results:
                return {
                    "answer": "I couldn't find relevant passages in your Buddhist text library to answer this question. Consider uploading more texts or rephrasing your question.",
                    "sources": [],
                    "processing_time": time.time() - start_time,
                    "search_results_count": 0
                }

            enhanced_sources = await self._enhance_sources(search_results, include_similar)

            # Try frontier model first, fallback to local if needed
            llm_response = await self._generate_with_fallback(question, enhanced_sources)

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

    async def _anchor_enhanced_search(self, question: str, max_results: int,
                                     filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """Enhanced search that leverages Buddhist anchors for better results"""

        # Extract potential Buddhist terms from the question
        question_words = question.lower().split()
        buddhist_indicators = [
            "dharma", "dhamma", "buddha", "meditation", "mindfulness", "compassion",
            "wisdom", "suffering", "impermanence", "karma", "nirvana", "samsara",
            "enlightenment", "awakening", "bodhisattva", "sutta", "teaching"
        ]

        detected_terms = [word for word in question_words if word in buddhist_indicators]

        # Start with hybrid search (our existing method)
        search_results = await self.vector_store.hybrid_search(
            query=question,
            max_results=max_results,
            boost_buddhist_terms=True
        )

        # If we detected Buddhist terms, try anchor-specific searches to supplement
        if detected_terms:
            for term in detected_terms[:2]:  # Limit to avoid too many searches
                try:
                    anchor_results = await self.vector_store.search_by_anchor(
                        term, max_results=2
                    )
                    # Add anchor results but avoid duplicates
                    for anchor_result in anchor_results:
                        chunk_id = anchor_result["metadata"].get("chunk_id")
                        if not any(r["metadata"].get("chunk_id") == chunk_id for r in search_results):
                            # Boost similarity score for anchor matches
                            anchor_result["similarity_score"] *= 1.2
                            search_results.append(anchor_result)
                except Exception as e:
                    logger.warning(f"Could not search by anchor '{term}': {str(e)}")

        # Re-sort by similarity score and limit results
        search_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        final_results = search_results[:max_results]

        # Update ranks
        for i, result in enumerate(final_results):
            result["rank"] = i + 1

        logger.info(f"Anchor-enhanced search returned {len(final_results)} results")
        return final_results

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

            # Include anchor information if available
            if source.get("anchors"):
                formatted_anchors = []
                for anchor in source["anchors"]:
                    formatted_anchor = {
                        "term": anchor.get("term", ""),
                        "category": anchor.get("category", ""),
                        "confidence": round(anchor.get("confidence", 0), 2),
                        "definition": anchor.get("definition", "")[:200] + "..." if len(anchor.get("definition", "")) > 200 else anchor.get("definition", "")
                    }
                    formatted_anchors.append(formatted_anchor)
                formatted_source["buddhist_anchors"] = formatted_anchors

            if source.get("similar_passages"):
                formatted_source["similar_passages"] = [
                    {
                        "content": sp["content"][:200] + "..." if len(sp["content"]) > 200 else sp["content"],
                        "source_file": sp["metadata"].get("source_file", "Unknown"),
                        "page_number": sp["metadata"].get("page_num", "Unknown"),
                        "anchors": sp.get("anchors", [])[:3]  # Include top 3 anchors from similar passages
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

    async def _generate_with_fallback(self, question: str, context_passages: List[Dict]) -> Dict:
        """Generate response using frontier model with fallback to local model"""

        # If using local model provider, use local client directly
        if self.config.model_provider == ModelProvider.LOCAL:
            return await self.llm_client.generate_response(
                question=question,
                context_passages=context_passages
            )

        # Try frontier model first
        if self.frontier_client.is_available():
            try:
                logger.info(f"Using frontier model: {self.config.model_provider.value}")
                return await self.frontier_client.generate_response(
                    question=question,
                    context_passages=context_passages
                )
            except Exception as e:
                logger.warning(f"Frontier model failed: {str(e)}")

                # If fallback is disabled, re-raise the error
                if not self.config.enable_fallback:
                    raise

        # Fallback to local model
        logger.info("Falling back to local model")
        response = await self.llm_client.generate_response(
            question=question,
            context_passages=context_passages
        )

        # Add fallback indicator to response
        response["fallback_used"] = True
        response["primary_provider_failed"] = self.config.model_provider.value if self.config.model_provider != ModelProvider.LOCAL else None

        return response

    async def get_model_status(self) -> Dict:
        """Get status of all available models"""
        status = {
            "current_provider": self.config.model_provider.value,
            "local_model": {},
            "frontier_model": {},
            "fallback_enabled": self.config.enable_fallback,
            "privacy_summary": self.config.get_privacy_summary()
        }

        # Check local model
        try:
            status["local_model"] = await self.llm_client.health_check()
        except Exception as e:
            status["local_model"] = {"status": "unhealthy", "error": str(e)}

        # Check frontier model if available
        if self.frontier_client.is_available():
            try:
                frontier_status = await self.frontier_client.health_check()
                frontier_status["usage_summary"] = self.frontier_client.get_usage_summary()
                status["frontier_model"] = frontier_status
            except Exception as e:
                status["frontier_model"] = {"status": "unhealthy", "error": str(e)}
        else:
            status["frontier_model"] = {"status": "unavailable", "reason": "No API key configured"}

        return status

    async def update_model_config(self, provider: str, **kwargs) -> bool:
        """Update model configuration and reinitialize if necessary"""
        try:
            old_provider = self.config.model_provider

            # Update configuration
            success = self.config.update_provider(provider, **kwargs)
            if not success:
                return False

            # Reinitialize if provider changed
            if old_provider != self.config.model_provider:
                logger.info(f"Provider changed from {old_provider.value} to {provider}")

                if self.config.model_provider != ModelProvider.LOCAL:
                    # Reinitialize frontier client
                    self.frontier_client = FrontierLLMClient()
                    await self.frontier_client.initialize()

            return True

        except Exception as e:
            logger.error(f"Failed to update model config: {str(e)}")
            return False