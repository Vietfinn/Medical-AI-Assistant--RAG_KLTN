import logging
from typing import Optional

from groq import Groq

logger = logging.getLogger(__name__)


class GroqService:
    """Service for interacting with Groq API (Llama 3)"""

    def __init__(self, api_key: str, model_name: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq service

        Args:
            api_key: Groq API key
            model_name: Model name to use
        """
        self.api_key = api_key
        self.model_name = model_name
        self.client = None

    def configure(self):
        """Configure Groq client"""
        try:
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Groq API configured with model: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Groq API: {str(e)}")
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate response using Groq (Llama 3)

        Args:
            prompt: User prompt
            system_prompt: System prompt for role setting
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            Generated response text
        """
        if self.client is None:
            raise RuntimeError("Groq not configured. Call configure() first.")

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error generating response from Groq: {str(e)}")
            raise

    def is_configured(self) -> bool:
        """Check if Groq is configured"""
        return self.client is not None
