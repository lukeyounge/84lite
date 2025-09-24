import ollama
import asyncio
from typing import Dict, List, Optional, AsyncGenerator
from loguru import logger
import json
from tenacity import retry, stop_after_attempt, wait_exponential
import time

class LLMClient:
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.model_name = model_name
        self.client = ollama.AsyncClient()
        self.system_prompt = self._create_buddhist_system_prompt()
        self.max_context_length = 32768
        self.max_response_length = 2048

    def _create_buddhist_system_prompt(self) -> str:
        return """You are a knowledgeable and respectful assistant specializing in Buddhist teachings and texts. Your role is to help users explore and understand Buddhist wisdom through the provided source materials.

Guidelines for your responses:
1. **Respectful Approach**: Treat all Buddhist teachings with reverence and care. Avoid oversimplification of profound concepts.

2. **Source-Based Answers**: Base your responses primarily on the provided source passages. When the sources don't contain enough information, acknowledge this limitation.

3. **Clear Citations**: Always reference which text and page your information comes from. Use the format [Source: filename, page X].

4. **Contextual Understanding**: Consider the broader context of Buddhist teachings when explaining concepts. Acknowledge different traditions (Theravada, Mahayana, Vajrayana) when relevant.

5. **Practical Application**: When appropriate, connect ancient teachings to contemporary understanding while maintaining authenticity.

6. **Humble Uncertainty**: If you're unsure about interpretation or if the sources are unclear, express this honestly rather than guessing.

7. **Non-Denominational**: Present teachings in a way that respects all Buddhist traditions while being clear about specific traditional perspectives when relevant.

8. **Encourage Further Study**: Suggest areas for deeper exploration when appropriate.

Remember: Your goal is to facilitate genuine understanding and respectful engagement with Buddhist wisdom, not to replace direct study with qualified teachers or authentic texts."""

    async def health_check(self) -> Dict:
        try:
            models = await self.client.list()
            model_available = any(model["name"] == self.model_name for model in models["models"])

            if not model_available:
                return {
                    "status": "unhealthy",
                    "error": f"Model {self.model_name} not available",
                    "available_models": [model["name"] for model in models["models"]]
                }

            test_response = await self._test_generation()
            if test_response:
                return {
                    "status": "healthy",
                    "service": "llm_client",
                    "model": self.model_name,
                    "context_length": self.max_context_length
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Model test generation failed"
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Connection failed: {str(e)}"
            }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _test_generation(self) -> bool:
        try:
            response = await self.client.generate(
                model=self.model_name,
                prompt="Test message: What is mindfulness?",
                options={
                    "num_predict": 50,
                    "temperature": 0.1
                }
            )
            return bool(response and response.get("response"))
        except Exception as e:
            logger.warning(f"Model test failed: {str(e)}")
            return False

    async def generate_response(self, question: str, context_passages: List[Dict],
                              stream: bool = False) -> Dict:
        start_time = time.time()

        try:
            formatted_prompt = self._format_prompt(question, context_passages)

            logger.info(f"Generating response for question: {question[:100]}...")
            logger.debug(f"Prompt length: {len(formatted_prompt)} characters")

            if stream:
                response_generator = self._generate_streaming(formatted_prompt)
                return {
                    "response_stream": response_generator,
                    "processing_time": time.time() - start_time
                }
            else:
                response = await self._generate_complete(formatted_prompt)

                processing_time = time.time() - start_time
                logger.info(f"Generated response in {processing_time:.2f} seconds")

                return {
                    "response": response,
                    "processing_time": processing_time,
                    "model": self.model_name,
                    "context_passages_used": len(context_passages)
                }

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    async def _generate_complete(self, prompt: str) -> str:
        response = await self.client.generate(
            model=self.model_name,
            prompt=prompt,
            system=self.system_prompt,
            options={
                "num_predict": self.max_response_length,
                "temperature": 0.3,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "stop": ["\n\nHuman:", "\n\nUser:", "<|im_end|>"]
            }
        )

        if not response or not response.get("response"):
            raise Exception("Empty response from model")

        return response["response"].strip()

    async def _generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.generate(
                model=self.model_name,
                prompt=prompt,
                system=self.system_prompt,
                stream=True,
                options={
                    "num_predict": self.max_response_length,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                    "stop": ["\n\nHuman:", "\n\nUser:", "<|im_end|>"]
                }
            )

            async for chunk in stream:
                if chunk and chunk.get("response"):
                    yield chunk["response"]

        except Exception as e:
            logger.error(f"Error in streaming generation: {str(e)}")
            yield f"Error: {str(e)}"

    def _format_prompt(self, question: str, context_passages: List[Dict]) -> str:
        if not context_passages:
            return f"""Question: {question}

No specific source passages were found in the Buddhist text library. Please provide a general response based on Buddhist teachings, but note that specific citations are not available."""

        context_text = self._format_context_passages(context_passages)

        prompt = f"""Based on the following passages from Buddhist texts, please answer the question with appropriate citations.

Source Passages:
{context_text}

Question: {question}

Please provide a thoughtful response based on these sources. Include citations in the format [Source: filename, page X] when referencing specific passages. If the passages don't fully address the question, acknowledge this and provide context for what additional study might be helpful."""

        if len(prompt) > self.max_context_length:
            prompt = self._truncate_prompt(prompt, question)

        return prompt

    def _format_context_passages(self, passages: List[Dict]) -> str:
        formatted_passages = []

        for i, passage in enumerate(passages, 1):
            content = passage.get("content", "")
            metadata = passage.get("metadata", {})

            source_file = metadata.get("source_file", "Unknown source")
            page_num = metadata.get("page_num", "Unknown page")
            chunk_type = metadata.get("chunk_type", "")

            chunk_type_label = ""
            if chunk_type == "sutta_opening":
                chunk_type_label = " [Sutta Opening]"
            elif chunk_type == "buddha_teaching":
                chunk_type_label = " [Buddha's Teaching]"
            elif chunk_type == "dialogue":
                chunk_type_label = " [Dialogue]"

            passage_header = f"Passage {i}: {source_file}, page {page_num}{chunk_type_label}"

            formatted_passage = f"{passage_header}\n{content}\n"
            formatted_passages.append(formatted_passage)

        return "\n---\n".join(formatted_passages)

    def _truncate_prompt(self, prompt: str, question: str) -> str:
        logger.warning("Prompt too long, truncating context")

        lines = prompt.split('\n')
        question_start = None

        for i, line in enumerate(lines):
            if line.startswith("Question:"):
                question_start = i
                break

        if question_start:
            available_space = self.max_context_length - len(question) - 500  # Reserve space

            context_lines = lines[1:question_start-1]  # Skip first line and question section
            truncated_context = []
            current_length = 0

            for line in context_lines:
                if current_length + len(line) > available_space:
                    break
                truncated_context.append(line)
                current_length += len(line)

            truncated_prompt = (
                lines[0] + '\n' +
                '\n'.join(truncated_context) +
                '\n\n[Note: Some context passages were truncated due to length limits]\n\n' +
                '\n'.join(lines[question_start:])
            )

            return truncated_prompt

        return prompt[:self.max_context_length]

    async def summarize_document(self, document_chunks: List[Dict],
                                document_name: str) -> str:
        if not document_chunks:
            return "No content available for summary."

        sample_content = ""
        total_pages = set()

        for chunk in document_chunks[:10]:  # Use first 10 chunks for summary
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})

            sample_content += content[:500] + "\n\n"  # First 500 chars of each chunk
            total_pages.add(metadata.get("page_num", 0))

        prompt = f"""Based on the following sample content from "{document_name}" (approximately {len(total_pages)} pages), provide a brief summary of this Buddhist text:

{sample_content}

Please provide:
1. A brief overview of the text's main themes
2. The apparent Buddhist tradition or style
3. Key teachings or concepts present
4. The likely intended audience or purpose

Keep the summary concise but informative."""

        try:
            response = await self._generate_complete(prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating document summary: {str(e)}")
            return f"Unable to generate summary: {str(e)}"

    async def get_model_info(self) -> Dict:
        try:
            models = await self.client.list()

            for model in models["models"]:
                if model["name"] == self.model_name:
                    return {
                        "name": model["name"],
                        "size": model.get("size", "Unknown"),
                        "modified": model.get("modified_at", "Unknown"),
                        "details": model.get("details", {})
                    }

            return {"error": f"Model {self.model_name} not found"}

        except Exception as e:
            return {"error": f"Failed to get model info: {str(e)}"}

    def estimate_token_count(self, text: str) -> int:
        return len(text.split()) * 1.3  # Rough estimation

    def validate_context_length(self, prompt: str) -> bool:
        estimated_tokens = self.estimate_token_count(prompt)
        return estimated_tokens <= (self.max_context_length * 0.8)  # 80% safety margin