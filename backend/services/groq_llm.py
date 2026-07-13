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

        # Load GROQ_LIST from settings/env as backup keys
        backup_keys = []
        try:
            from config import settings
            groq_list_str = getattr(settings, "GROQ_LIST", "") or ""
            if not groq_list_str:
                import os
                groq_list_str = os.getenv("GROQ_LIST", "")
            backup_keys = [k.strip() for k in groq_list_str.split(",") if k.strip()]
        except Exception:
            backup_keys = []

        # Build final rotation pool: start with initial api_key, followed by backup keys
        self.keys = [api_key]
        for k in backup_keys:
            if k not in self.keys:
                self.keys.append(k)

        self.current_key_idx = 0

    def _rotate_client_on_failure(self) -> bool:
        """Rotate to the next API key in the pool and reconfigure client"""
        if len(self.keys) <= 1:
            return False
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        next_key = self.keys[self.current_key_idx]
        logger.warning(
            f"Rotating Groq API Key to key index {self.current_key_idx} due to rate limit/failure."
        )
        self.client = Groq(api_key=next_key)
        return True

    def configure(self):
        """Configure Groq client"""
        try:
            self.client = Groq(api_key=self.keys[self.current_key_idx])
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
        """
        if self.client is None:
            raise RuntimeError("Groq not configured. Call configure() first.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_attempts = len(self.keys)
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "rate_limit" in err_msg or "429" in err_msg or "too many requests" in err_msg

                if is_rate_limit and attempt < max_attempts - 1:
                    if self._rotate_client_on_failure():
                        continue
                logger.error(f"Error generating response from Groq on attempt {attempt+1}: {str(e)}")
                raise

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        """
        Generate streaming response using Groq (Llama 3)
        Yields text chunks as they arrive.
        """
        if self.client is None:
            raise RuntimeError("Groq not configured. Call configure() first.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_attempts = len(self.keys)
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                return
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "rate_limit" in err_msg or "429" in err_msg or "too many requests" in err_msg

                if is_rate_limit and attempt < max_attempts - 1:
                    if self._rotate_client_on_failure():
                        continue
                logger.error(f"Error in streaming response from Groq on attempt {attempt+1}: {str(e)}")
                raise

    def is_configured(self) -> bool:
        """Check if Groq is configured"""
        return self.client is not None

