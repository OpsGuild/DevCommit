#!/usr/bin/env python
"""AI provider abstraction layer for multiple AI models"""

import os
import sys
from abc import ABC, abstractmethod
from typing import Optional

# Suppress stderr for all AI imports
_stderr = sys.stderr
_devnull = open(os.devnull, "w")
sys.stderr = _devnull

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import requests
except ImportError:
    requests = None

sys.stderr = _stderr
_devnull.close()


class AIProvider(ABC):
    """Base class for AI providers"""

    @abstractmethod
    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        """Generate commit message from diff"""
        pass


class GeminiProvider(AIProvider):
    """Google Gemini AI provider"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        if not genai:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            )

        # Suppress stderr during configuration
        _stderr = sys.stderr
        _devnull = open(os.devnull, "w")
        sys.stderr = _devnull
        genai.configure(api_key=api_key)
        sys.stderr = _stderr
        _devnull.close()

        self.model_name = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        generation_config = {
            "response_mime_type": "text/plain",
            "max_output_tokens": max_tokens,
            "top_k": 40,
            "top_p": 0.9,
            "temperature": 0.7,
        }

        model = genai.GenerativeModel(
            generation_config=generation_config,
            model_name=self.model_name,
        )

        chat_session = model.start_chat(
            history=[
                {
                    "role": "user",
                    "parts": [prompt],
                },
            ]
        )

        # Suppress stderr during API call
        _stderr = sys.stderr
        _devnull = open(os.devnull, "w")
        sys.stderr = _devnull
        response = chat_session.send_message(diff)
        sys.stderr = _stderr
        _devnull.close()

        if response and hasattr(response, "text"):
            return response.text.strip()
        return "No valid commit message generated."


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        if not openai:
            raise ImportError("openai not installed. Run: pip install openai")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        if not response or not response.choices:
            raise ValueError("OpenAI returned empty response (no choices).")
        return response.choices[0].message.content.strip()


class GroqProvider(AIProvider):
    """Groq AI provider (OpenAI-compatible)"""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        if not openai:
            raise ImportError("openai not installed. Run: pip install openai")
        self.client = openai.OpenAI(
            api_key=api_key, base_url="https://api.groq.com/openai/v1"
        )
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        if not response or not response.choices:
            raise ValueError("Groq returned empty response (no choices).")
        return response.choices[0].message.content.strip()


class OpenRouterProvider(AIProvider):
    """OpenRouter.ai provider (OpenAI-compatible, access to multiple models)"""

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
    ):
        if not openai:
            raise ImportError("openai not installed. Run: pip install openai")
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/opsguild/DevCommit",
                "X-Title": "DevCommit",
            },
        )
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            extra_body={"transforms": ["middle-out"]},
            extra_headers={
                "HTTP-Referer": "https://github.com/hordunlarmy/DevCommit",
                "X-Title": "DevCommit",
            },
        )
        if not response or not response.choices:
            raise ValueError("OpenRouter returned empty response (no choices).")
            
        content = response.choices[0].message.content
        if not content:
            return ""
            
        return content.strip()


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider"""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        if not anthropic:
            raise ImportError(
                "anthropic not installed. Run: pip install anthropic"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=prompt,
            messages=[{"role": "user", "content": diff}],
        )
        return message.content[0].text.strip()


class OllamaProvider(AIProvider):
    """Ollama local model provider"""

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3"
    ):
        if not requests:
            raise ImportError(
                "requests not installed. Run: pip install requests"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": f"{prompt}\n\n{diff}",
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }

        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()["response"].strip()

        # Return raw result - normalization is done centrally in gemini_ai.py
        return result


class CustomProvider(AIProvider):
    """Custom OpenAI-compatible API provider"""

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        model: str = "default",
    ):
        if not openai:
            raise ImportError("openai not installed. Run: pip install openai")

        # Extract base URL (remove /chat/completions if present)
        base_url = api_url.replace("/chat/completions", "").replace(
            "/v1/chat/completions", ""
        )
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        self.client = openai.OpenAI(
            api_key=api_key or "dummy-key", base_url=base_url
        )
        self.model = model

    def generate_commit_message(
        self, diff: str, prompt: str, max_tokens: int
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        if not response or not response.choices:
            raise ValueError("Custom API returned empty response (no choices).")
        return response.choices[0].message.content.strip()


def get_ai_provider(config) -> AIProvider:
    """Factory function to get the appropriate AI provider based on config"""

    provider_name = config("AI_PROVIDER", default="gemini").lower()

    if provider_name == "gemini":
        api_key = config("GEMINI_API_KEY", default=None)
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        # Support legacy MODEL_NAME for backward compatibility
        model = config("GEMINI_MODEL", default=None) or config(
            "MODEL_NAME", default="gemini-2.0-flash-exp"
        )
        return GeminiProvider(api_key, model)

    elif provider_name == "openai":
        api_key = config("OPENAI_API_KEY", default=None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        model = config("OPENAI_MODEL", default=None) or config(
            "MODEL_NAME", default="gpt-4o-mini"
        )
        return OpenAIProvider(api_key, model)

    elif provider_name == "groq":
        api_key = config("GROQ_API_KEY", default=None)
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        model = config("GROQ_MODEL", default=None) or config(
            "MODEL_NAME", default="llama-3.3-70b-versatile"
        )
        return GroqProvider(api_key, model)

    elif provider_name == "openrouter":
        api_key = config("OPENROUTER_API_KEY", default=None)
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        model = config("OPENROUTER_MODEL", default=None) or config(
            "MODEL_NAME", default="meta-llama/llama-3.3-70b-instruct:free"
        )
        return OpenRouterProvider(api_key, model)

    elif provider_name == "anthropic":
        api_key = config("ANTHROPIC_API_KEY", default=None)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        model = config("ANTHROPIC_MODEL", default=None) or config(
            "MODEL_NAME", default="claude-3-haiku-20240307"
        )
        return AnthropicProvider(api_key, model)

    elif provider_name == "ollama":
        base_url = config("OLLAMA_BASE_URL", default="http://localhost:11434")
        model = config("OLLAMA_MODEL", default=None) or config(
            "MODEL_NAME", default="llama3"
        )
        return OllamaProvider(base_url, model)

    elif provider_name == "custom":
        api_url = config("CUSTOM_API_URL", default=None)
        if not api_url:
            raise ValueError("CUSTOM_API_URL not set for custom provider")
        api_key = config("CUSTOM_API_KEY", default=None)
        model = config("CUSTOM_MODEL", default=None) or config(
            "MODEL_NAME", default="default"
        )
        return CustomProvider(api_url, api_key, model)

    else:
        raise ValueError(
            f"Unknown AI provider: {provider_name}. "
            f"Supported: gemini, openai, groq, openrouter, anthropic, ollama, custom"
        )
