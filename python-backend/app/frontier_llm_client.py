import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator, Union
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from abc import ABC, abstractmethod

# Import API clients (with error handling for missing packages)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic package not available")

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google Generative AI package not available")

from .config import get_config, ModelProvider


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, config: Dict):
        self.config = config
        self.system_prompt = self._create_buddhist_system_prompt()

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

    @abstractmethod
    async def health_check(self) -> Dict:
        pass

    @abstractmethod
    async def generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        pass

    @abstractmethod
    async def generate_streaming(self, prompt: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        pass

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for API usage (default: free)"""
        return 0.0


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider"""

    def __init__(self, config: Dict):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed")

        self.client = openai.AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url")
        )
        self.model = config["model"]

    async def health_check(self) -> Dict:
        try:
            response = await self.client.models.retrieve(self.model)
            return {
                "status": "healthy",
                "service": "openai_provider",
                "model": self.model,
                "context_length": 128000 if "gpt-4" in self.model else 16385
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"OpenAI connection failed: {str(e)}"
            }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=get_config().temperature,
                top_p=get_config().top_p
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI generation error: {str(e)}")
            raise

    async def generate_streaming(self, prompt: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=get_config().temperature,
                top_p=get_config().top_p,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            yield f"Error: {str(e)}"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Rough pricing for GPT-4 (as of 2024)
        if "gpt-4" in self.model:
            input_cost = (input_tokens / 1000) * 0.03
            output_cost = (output_tokens / 1000) * 0.06
        else:  # GPT-3.5
            input_cost = (input_tokens / 1000) * 0.0015
            output_cost = (output_tokens / 1000) * 0.002
        return input_cost + output_cost


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider"""

    def __init__(self, config: Dict):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic package not installed")

        self.client = anthropic.AsyncAnthropic(api_key=config["api_key"])
        self.model = config["model"]

    async def health_check(self) -> Dict:
        try:
            # Simple test message to verify connection
            await self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return {
                "status": "healthy",
                "service": "anthropic_provider",
                "model": self.model,
                "context_length": 200000  # Claude 3.5 context window
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Anthropic connection failed: {str(e)}"
            }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=get_config().temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Anthropic generation error: {str(e)}")
            raise

    async def generate_streaming(self, prompt: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        try:
            stream = self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=get_config().temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            async with stream as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            yield f"Error: {str(e)}"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Rough pricing for Claude 3.5 Sonnet (as of 2024)
        input_cost = (input_tokens / 1000) * 0.003
        output_cost = (output_tokens / 1000) * 0.015
        return input_cost + output_cost


class GoogleProvider(BaseLLMProvider):
    """Google Generative AI provider"""

    def __init__(self, config: Dict):
        super().__init__(config)
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google Generative AI package not installed")

        genai.configure(api_key=config["api_key"])
        self.model_name = config["model"]
        self.model = genai.GenerativeModel(self.model_name)

    async def health_check(self) -> Dict:
        try:
            # Test generation to verify connection
            response = await asyncio.to_thread(
                self.model.generate_content,
                "test",
                generation_config=genai.types.GenerationConfig(max_output_tokens=1)
            )
            return {
                "status": "healthy",
                "service": "google_provider",
                "model": self.model_name,
                "context_length": 32768  # Gemini Pro context window
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Google AI connection failed: {str(e)}"
            }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        try:
            full_prompt = f"{self.system_prompt}\n\nUser: {prompt}\n\nAssistant:"

            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=get_config().temperature,
                    top_p=get_config().top_p
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Google AI generation error: {str(e)}")
            raise

    async def generate_streaming(self, prompt: str, max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        try:
            full_prompt = f"{self.system_prompt}\n\nUser: {prompt}\n\nAssistant:"

            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=get_config().temperature,
                    top_p=get_config().top_p
                ),
                stream=True
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Google AI streaming error: {str(e)}")
            yield f"Error: {str(e)}"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Rough pricing for Gemini Pro (as of 2024)
        input_cost = (input_tokens / 1000) * 0.00025
        output_cost = (output_tokens / 1000) * 0.0005
        return input_cost + output_cost


class FrontierLLMClient:
    """Unified client for frontier model providers with fallback support"""

    def __init__(self):
        self.config = get_config()
        self.provider: Optional[BaseLLMProvider] = None
        self.fallback_provider: Optional[BaseLLMProvider] = None
        self.usage_stats = {"requests": 0, "tokens_used": 0, "estimated_cost": 0.0}

    async def initialize(self):
        """Initialize the primary and fallback providers"""
        await self._setup_provider()
        if self.config.enable_fallback:
            await self._setup_fallback()

    async def _setup_provider(self):
        """Setup primary provider based on configuration"""
        try:
            provider_config = self.config.get_provider_config()

            if not provider_config.get("available"):
                logger.warning(f"Primary provider {provider_config['provider']} not available (missing API key)")
                return

            if self.config.model_provider == ModelProvider.OPENAI:
                self.provider = OpenAIProvider(provider_config)
            elif self.config.model_provider == ModelProvider.ANTHROPIC:
                self.provider = AnthropicProvider(provider_config)
            elif self.config.model_provider == ModelProvider.GOOGLE:
                self.provider = GoogleProvider(provider_config)
            else:
                logger.info("Using local provider as primary")
                return  # Will use local LLM client

            logger.info(f"Initialized {provider_config['provider']} provider")

        except Exception as e:
            logger.error(f"Failed to setup primary provider: {str(e)}")
            self.provider = None

    async def _setup_fallback(self):
        """Setup fallback provider (usually local)"""
        # Fallback is typically the local Ollama model
        # This will be handled by the RAG engine using the original LLMClient
        pass

    async def health_check(self) -> Dict:
        """Check health of all available providers"""
        if not self.provider:
            return {
                "status": "unhealthy",
                "error": "No frontier providers available - using local model"
            }

        try:
            health = await self.provider.health_check()
            health["usage_stats"] = self.usage_stats
            health["provider_type"] = "frontier"
            return health
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Provider health check failed: {str(e)}"
            }

    async def generate_response(self, question: str, context_passages: List[Dict], stream: bool = False) -> Dict:
        """Generate response using frontier model"""
        if not self.provider:
            raise Exception("No frontier provider available")

        start_time = time.time()

        try:
            formatted_prompt = self._format_prompt(question, context_passages)

            if stream:
                response_generator = self.provider.generate_streaming(formatted_prompt, self.config.max_response_length)
                return {
                    "response_stream": response_generator,
                    "processing_time": time.time() - start_time,
                    "provider": self.config.model_provider.value
                }
            else:
                response = await self.provider.generate_response(formatted_prompt, self.config.max_response_length)

                # Update usage stats
                input_tokens = len(formatted_prompt.split()) * 1.3  # Rough estimate
                output_tokens = len(response.split()) * 1.3
                cost = self.provider.estimate_cost(int(input_tokens), int(output_tokens))

                self.usage_stats["requests"] += 1
                self.usage_stats["tokens_used"] += int(input_tokens + output_tokens)
                self.usage_stats["estimated_cost"] += cost

                processing_time = time.time() - start_time

                return {
                    "response": response,
                    "processing_time": processing_time,
                    "model": self.config.get_model_display_name(),
                    "provider": self.config.model_provider.value,
                    "context_passages_used": len(context_passages),
                    "estimated_cost": cost,
                    "usage_stats": self.usage_stats.copy()
                }

        except Exception as e:
            logger.error(f"Frontier model generation error: {str(e)}")
            raise

    def _format_prompt(self, question: str, context_passages: List[Dict]) -> str:
        """Format prompt with context passages"""
        if not context_passages:
            return f"""Question: {question}

No specific source passages were found in your Buddhist text library. Please provide a general response based on Buddhist teachings, but note that specific citations are not available."""

        context_text = self._format_context_passages(context_passages)

        prompt = f"""Based on the following passages from Buddhist texts, please answer the question with appropriate citations.

Source Passages:
{context_text}

Question: {question}

Please provide a thoughtful response based on these sources. Include citations in the format [Source: filename, page X] when referencing specific passages. If the passages don't fully address the question, acknowledge this and provide context for what additional study might be helpful."""

        return prompt

    def _format_context_passages(self, passages: List[Dict]) -> str:
        """Format context passages for prompt"""
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

    def get_usage_summary(self) -> Dict:
        """Get usage statistics and cost summary"""
        return {
            **self.usage_stats,
            "provider": self.config.model_provider.value,
            "model": self.config.get_model_display_name(),
            "daily_limit": self.config.max_daily_api_calls,
            "approaching_limit": self.usage_stats["requests"] > (self.config.max_daily_api_calls * 0.8)
        }

    def is_available(self) -> bool:
        """Check if frontier provider is available"""
        return self.provider is not None