import unittest
from unittest.mock import Mock, patch

from devcommit.app.ai_providers import (
    AnthropicProvider,
    OllamaProvider,
    OpenAIProvider,
    reasoning_extra_body,
)


class CompletionClient:
    def __init__(self):
        self.kwargs = None
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]})()


class MessagesClient:
    def __init__(self):
        self.kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"content": [type("Content", (), {"text": "ok"})()]})()


class ReasoningTests(unittest.TestCase):
    def test_openai_compatible_none_is_sent(self):
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.model = "reasoning-model"
        provider.reasoning_effort = "none"
        provider.client = CompletionClient()
        provider.generate_commit_message("diff", "prompt", 10)
        self.assertEqual(provider.client.kwargs["extra_body"], {"reasoning_effort": "none"})

    def test_anthropic_none_disables_thinking(self):
        provider = AnthropicProvider.__new__(AnthropicProvider)
        provider.model = "claude"
        provider.reasoning_effort = "none"
        provider.client = MessagesClient()
        provider.generate_commit_message("diff", "prompt", 10)
        self.assertEqual(provider.client.kwargs["thinking"], {"type": "disabled"})

    def test_ollama_none_uses_false_think_flag(self):
        provider = OllamaProvider.__new__(OllamaProvider)
        provider.model = "local"
        provider.base_url = "http://ollama"
        provider.reasoning_effort = "none"
        response = Mock()
        response.json.return_value = {"response": "ok"}
        with patch("devcommit.app.ai_providers.requests") as requests:
            requests.post.return_value = response
            provider.generate_commit_message("diff", "prompt", 10)
        self.assertEqual(requests.post.call_args.kwargs["json"]["think"], False)
        self.assertEqual(reasoning_extra_body("none"), {"reasoning_effort": "none"})


if __name__ == "__main__":
    unittest.main()
