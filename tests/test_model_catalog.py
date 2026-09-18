import io
import json
import unittest
from unittest.mock import patch

from devcommit.app.model_catalog import ModelCatalogError, fetch_models


def config_with(values):
    def config(key, default=None):
        return values.get(key, default)

    return config


class ModelCatalogTests(unittest.TestCase):
    def test_fetches_every_supported_provider(self):
        calls = []

        def urlopen_response(request, timeout):
            calls.append((request.full_url, request.headers))
            url = request.full_url
            if "openrouter" in url:
                data = {
                    "data": [
                        {"id": "acme/paid", "name": "Paid", "pricing": {"prompt": "0.1", "completion": "0.2"}},
                        {"id": "acme/free:free", "name": "Free", "pricing": {"prompt": "0", "completion": "0"}},
                    ]
                }
            elif "generativelanguage" in url:
                data = {
                    "models": [
                        {"name": "models/gemini-test", "displayName": "Gemini Test", "inputTokenLimit": 1000, "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/embedding-test", "supportedGenerationMethods": ["embedContent"]},
                    ]
                }
            elif "anthropic" in url:
                data = {"data": [{"id": "claude-test", "display_name": "Claude Test", "max_input_tokens": 2000}], "has_more": False}
            elif "api/tags" in url:
                data = {"models": [{"name": "llama:latest", "details": {"parameter_size": "8B"}}]}
            else:
                data = {"data": [{"id": "test-model"}]}
            return io.BytesIO(json.dumps(data).encode())

        config = config_with(
            {
                "OPENROUTER_API_KEY": "router-key",
                "GEMINI_API_KEY": "gemini-key",
                "OPENAI_API_KEY": "openai-key",
                "GROQ_API_KEY": "groq-key",
                "ANTHROPIC_API_KEY": "anthropic-key",
                "OLLAMA_BASE_URL": "http://ollama.example",
                "CUSTOM_API_URL": "https://custom.example/v1",
                "CUSTOM_API_KEY": "custom-key",
            }
        )

        with patch("devcommit.app.model_catalog.urlopen", urlopen_response):
            openrouter = fetch_models("openrouter", config)
            gemini = fetch_models("gemini", config)
            openai = fetch_models("openai", config)
            groq = fetch_models("groq", config)
            anthropic = fetch_models("anthropic", config)
            ollama = fetch_models("ollama", config)
            custom = fetch_models("custom", config)

        self.assertEqual([model["availability"] for model in openrouter], ["Free", "Paid"])
        self.assertEqual(gemini[0]["id"], "gemini-test")
        self.assertEqual(openai[0]["id"], "test-model")
        self.assertEqual(groq[0]["id"], "test-model")
        self.assertEqual(anthropic[0]["id"], "claude-test")
        self.assertEqual(ollama[0]["availability"], "Installed")
        self.assertEqual(custom[0]["id"], "test-model")
        self.assertTrue(any("openai.com/v1/models" in url for url, _ in calls))
        self.assertTrue(any("groq.com/openai/v1/models" in url for url, _ in calls))
        self.assertTrue(
            any(
                "anthropic-version" in {key.lower() for key in headers}
                for _, headers in calls
            )
        )

    def test_requires_a_key_for_authenticated_providers(self):
        with self.assertRaisesRegex(ModelCatalogError, "OPENAI_API_KEY is not set"):
            fetch_models("openai", config_with({}))

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ModelCatalogError, "Unsupported AI_PROVIDER"):
            fetch_models("unknown", config_with({}))

    def test_marks_variable_openrouter_router_prices(self):
        with patch(
            "devcommit.app.model_catalog.urlopen",
            lambda request, timeout: io.BytesIO(
                json.dumps({"data": [{"id": "openrouter/auto", "pricing": {"prompt": "-1", "completion": "-1"}}]}).encode()
            ),
        ):
            models = fetch_models("openrouter", config_with({}))
        self.assertEqual(models[0]["price"], "Variable")


if __name__ == "__main__":
    unittest.main()
