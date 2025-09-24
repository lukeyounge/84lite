import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Optional, Tuple
from loguru import logger
import os
from pathlib import Path
import json
from datetime import datetime

from .pdf_processor import BuddhistTextChunk

class VectorStore:
    def __init__(self, persist_directory: str = "user_data/vector_store"):
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.embedding_dimension = 384  # all-MiniLM-L6-v2 dimension

    async def initialize(self):
        logger.info("Initializing ChromaDB vector store...")

        os.makedirs(self.persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        try:
            self.collection = self.client.get_collection(
                name="buddhist_texts",
                embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            )
            logger.info("Loaded existing collection 'buddhist_texts'")
        except ValueError:
            self.collection = self.client.create_collection(
                name="buddhist_texts",
                embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                ),
                metadata={"description": "Buddhist text chunks for semantic search"}
            )
            logger.info("Created new collection 'buddhist_texts'")

        logger.info("Loading sentence transformer model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Vector store initialized successfully")

    async def health_check(self) -> Dict:
        try:
            if not self.client or not self.collection:
                return {"status": "unhealthy", "error": "Not initialized"}

            count = self.collection.count()
            return {
                "status": "healthy",
                "service": "vector_store",
                "document_count": count,
                "embedding_model": "all-MiniLM-L6-v2"
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def add_chunks(self, chunks: List[BuddhistTextChunk]) -> Dict:
        if not chunks:
            return {"added": 0, "skipped": 0}

        logger.info(f"Adding {len(chunks)} chunks to vector store...")

        documents = []
        metadatas = []
        ids = []

        for chunk in chunks:
            documents.append(chunk.content)
            ids.append(chunk.chunk_id)

            metadata = {
                "source_file": chunk.source_file,
                "page_num": chunk.page_num,
                "chunk_type": chunk.chunk_type,
                "word_count": chunk.word_count,
                "added_date": datetime.now().isoformat(),
                **chunk.metadata
            }

            metadatas.append(metadata)

        try:
            existing_ids = set(self.collection.get(ids=ids)["ids"])
            new_documents = []
            new_metadatas = []
            new_ids = []

            for doc, meta, chunk_id in zip(documents, metadatas, ids):
                if chunk_id not in existing_ids:
                    new_documents.append(doc)
                    new_metadatas.append(meta)
                    new_ids.append(chunk_id)

            if new_documents:
                self.collection.add(
                    documents=new_documents,
                    metadatas=new_metadatas,
                    ids=new_ids
                )

            logger.info(f"Added {len(new_documents)} new chunks, skipped {len(existing_ids)} existing")

            return {
                "added": len(new_documents),
                "skipped": len(existing_ids),
                "total_in_store": self.collection.count()
            }

        except Exception as e:
            logger.error(f"Error adding chunks to vector store: {str(e)}")
            raise

    async def search(self, query: str, max_results: int = 5,
                    filter_metadata: Optional[Dict] = None) -> List[Dict]:
        logger.info(f"Searching for: {query[:100]}...")

        try:
            where_clause = None
            if filter_metadata:
                where_clause = filter_metadata

            results = self.collection.query(
                query_texts=[query],
                n_results=max_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )

            search_results = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    search_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance,  # Convert distance to similarity
                        "rank": i + 1
                    })

            logger.info(f"Found {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            raise

    async def get_document_chunks(self, source_file: str) -> List[Dict]:
        try:
            results = self.collection.get(
                where={"source_file": source_file},
                include=["documents", "metadatas"]
            )

            chunks = []
            if results["documents"]:
                for doc, metadata in zip(results["documents"], results["metadatas"]):
                    chunks.append({
                        "content": doc,
                        "metadata": metadata
                    })

            return sorted(chunks, key=lambda x: x["metadata"]["page_num"])

        except Exception as e:
            logger.error(f"Error getting document chunks: {str(e)}")
            raise

    async def delete_document(self, source_file: str) -> Dict:
        try:
            existing_chunks = await self.get_document_chunks(source_file)

            if not existing_chunks:
                return {"deleted": 0, "message": "No chunks found for this document"}

            chunk_ids = [chunk["metadata"].get("chunk_id") for chunk in existing_chunks]
            chunk_ids = [cid for cid in chunk_ids if cid]

            if chunk_ids:
                self.collection.delete(ids=chunk_ids)

            logger.info(f"Deleted {len(chunk_ids)} chunks for document {source_file}")

            return {
                "deleted": len(chunk_ids),
                "message": f"Deleted document {source_file}"
            }

        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise

    async def get_collection_stats(self) -> Dict:
        try:
            total_count = self.collection.count()

            if total_count == 0:
                return {
                    "total_chunks": 0,
                    "documents": [],
                    "chunk_types": {},
                    "traditions": {}
                }

            all_metadata = self.collection.get(include=["metadatas"])["metadatas"]

            document_stats = {}
            chunk_type_counts = {}
            tradition_counts = {}

            for metadata in all_metadata:
                source_file = metadata.get("source_file", "unknown")
                chunk_type = metadata.get("chunk_type", "unknown")
                tradition = metadata.get("estimated_tradition", "unknown")

                if source_file not in document_stats:
                    document_stats[source_file] = {
                        "chunk_count": 0,
                        "page_count": set(),
                        "added_date": metadata.get("added_date")
                    }

                document_stats[source_file]["chunk_count"] += 1
                document_stats[source_file]["page_count"].add(metadata.get("page_num", 0))

                chunk_type_counts[chunk_type] = chunk_type_counts.get(chunk_type, 0) + 1
                tradition_counts[tradition] = tradition_counts.get(tradition, 0) + 1

            for source_file in document_stats:
                document_stats[source_file]["page_count"] = len(document_stats[source_file]["page_count"])

            return {
                "total_chunks": total_count,
                "documents": [
                    {
                        "filename": filename,
                        "chunks": stats["chunk_count"],
                        "pages": stats["page_count"],
                        "added_date": stats["added_date"]
                    }
                    for filename, stats in document_stats.items()
                ],
                "chunk_types": chunk_type_counts,
                "traditions": tradition_counts
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            raise

    async def hybrid_search(self, query: str, max_results: int = 5,
                          boost_recent: bool = False,
                          boost_buddhist_terms: bool = True) -> List[Dict]:
        base_results = await self.search(query, max_results * 2)

        if not base_results:
            return []

        if boost_buddhist_terms:
            buddhist_terms = [
                "dharma", "dhamma", "buddha", "meditation", "mindfulness",
                "compassion", "wisdom", "suffering", "impermanence",
                "interdependence", "awakening", "enlightenment"
            ]

            for result in base_results:
                content_lower = result["content"].lower()
                term_count = sum(1 for term in buddhist_terms if term in content_lower)

                if term_count > 0:
                    result["similarity_score"] *= (1 + 0.1 * term_count)

        if boost_recent:
            for result in base_results:
                added_date = result["metadata"].get("added_date")
                if added_date:
                    try:
                        added_dt = datetime.fromisoformat(added_date)
                        days_old = (datetime.now() - added_dt).days
                        if days_old < 7:
                            result["similarity_score"] *= 1.1
                    except:
                        pass

        base_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        for i, result in enumerate(base_results[:max_results]):
            result["rank"] = i + 1

        return base_results[:max_results]

    async def get_similar_chunks(self, chunk_id: str, max_results: int = 3) -> List[Dict]:
        try:
            chunk_data = self.collection.get(
                ids=[chunk_id],
                include=["documents", "metadatas"]
            )

            if not chunk_data["documents"]:
                return []

            original_content = chunk_data["documents"][0]
            original_metadata = chunk_data["metadatas"][0]

            similar_results = await self.search(
                original_content[:500],  # Use first 500 chars as query
                max_results=max_results + 1  # +1 because original will be included
            )

            filtered_results = [
                result for result in similar_results
                if result["metadata"].get("chunk_id") != chunk_id
            ]

            return filtered_results[:max_results]

        except Exception as e:
            logger.error(f"Error finding similar chunks: {str(e)}")
            raise