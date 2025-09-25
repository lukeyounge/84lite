import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from loguru import logger
from enum import Enum

# Load environment variables from .env file
load_dotenv()

class ModelProvider(Enum):
    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"

class Config:
    """Configuration management for Buddhist RAG application"""

    def __init__(self):
        # Model Provider Settings
        self.model_provider = ModelProvider(os.getenv("MODEL_PROVIDER", "local"))
        self.enable_fallback = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"

        # Local Model Settings (Ollama)
        self.local_model_name = os.getenv("LOCAL_MODEL_NAME", "qwen2.5:14b")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # OpenAI Settings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")  # For custom endpoints

        # Anthropic Settings
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

        # Google Settings
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_model = os.getenv("GOOGLE_MODEL", "gemini-pro")

        # Model Parameters
        self.max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "32768"))
        self.max_response_length = int(os.getenv("MAX_RESPONSE_LENGTH", "2048"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.3"))
        self.top_p = float(os.getenv("TOP_P", "0.9"))

        # Usage Settings
        self.warn_on_api_usage = os.getenv("WARN_ON_API_USAGE", "true").lower() == "true"
        self.max_daily_api_calls = int(os.getenv("MAX_DAILY_API_CALLS", "100"))

        # Security Settings
        self.allow_data_transmission = os.getenv("ALLOW_DATA_TRANSMISSION", "false").lower() == "true"

    def get_provider_config(self) -> Dict[str, Any]:
        """Get configuration for the current model provider"""
        if self.model_provider == ModelProvider.OPENAI:
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "base_url": self.openai_base_url,
                "available": bool(self.openai_api_key)
            }
        elif self.model_provider == ModelProvider.ANTHROPIC:
            return {
                "provider": "anthropic",
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "available": bool(self.anthropic_api_key)
            }
        elif self.model_provider == ModelProvider.GOOGLE:
            return {
                "provider": "google",
                "api_key": self.google_api_key,
                "model": self.google_model,
                "available": bool(self.google_api_key)
            }
        else:  # LOCAL
            return {
                "provider": "local",
                "model": self.local_model_name,
                "base_url": self.ollama_base_url,
                "available": True  # Assume local is always available
            }

    def is_api_provider(self) -> bool:
        """Check if current provider is an API-based service"""
        return self.model_provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC, ModelProvider.GOOGLE]

    def get_model_display_name(self) -> str:
        """Get display name for the current model"""
        config = self.get_provider_config()
        if config["provider"] == "local":
            return f"Local {config['model']}"
        elif config["provider"] == "openai":
            return f"OpenAI {config['model']}"
        elif config["provider"] == "anthropic":
            return f"Anthropic {config['model']}"
        elif config["provider"] == "google":
            return f"Google {config['model']}"
        return "Unknown Model"

    def update_provider(self, provider: str, **kwargs) -> bool:
        """Update model provider and related settings"""
        try:
            self.model_provider = ModelProvider(provider)

            # Update specific provider settings
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    logger.info(f"Updated config: {key} = {value}")

            return True
        except ValueError as e:
            logger.error(f"Invalid model provider: {provider}")
            return False

    def validate_api_keys(self) -> Dict[str, bool]:
        """Validate all API keys"""
        return {
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
            "google": bool(self.google_api_key)
        }

    def get_privacy_summary(self) -> Dict[str, Any]:
        """Get privacy and data transmission summary"""
        is_local = self.model_provider == ModelProvider.LOCAL
        return {
            "local_processing": is_local,
            "data_leaves_system": not is_local and self.allow_data_transmission,
            "current_provider": self.model_provider.value,
            "privacy_level": "High" if is_local else "Medium" if self.allow_data_transmission else "Data transmission disabled"
        }

# Global configuration instance
config = Config()

def get_config() -> Config:
    """Get global configuration instance"""
    return config

def reload_config():
    """Reload configuration from environment"""
    global config
    load_dotenv()
    config = Config()
    logger.info("Configuration reloaded")