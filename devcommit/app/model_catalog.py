"""Provider-aware model catalogue helpers."""

import json
from typing import Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


Model = Dict[str, object]
Config = Callable[..., Optional[str]]


class ModelCatalogError(Exception):
    """Raised when a provider's model catalogue cannot be read."""


def _request_json(
    url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10
) -> Dict[str, object]:
    request_headers = {"User-Agent": "DevCommit"}
    if headers:
        request_headers.update(headers)

    try:
        with urlopen(Request(url, headers=request_headers), timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ModelCatalogError(f"Could not fetch models: {error}") from error

    if not isinstance(payload, dict):
        raise ModelCatalogError("The provider returned an unexpected models response.")
    return payload


def _api_key(config: Config, key_name: str) -> str:
    api_key = config(key_name, default=None)
    if not api_key:
        raise ModelCatalogError(f"{key_name} is not set.")
    return api_key


def _model(
    model_id: str,
    name: Optional[str] = None,
    context_length: Optional[object] = None,
    availability: str = "Available",
    price: str = "-",
) -> Model:
    return {
        "id": model_id,
        "name": name or model_id,
        "context_length": context_length,
        "availability": availability,
        "price": price,
    }


def _models_from_openai_response(payload: Dict[str, object]) -> List[Model]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise ModelCatalogError("The provider returned an unexpected models response.")

    models = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(_model(item["id"], item.get("id")))
    return models


def _format_openrouter_price(pricing: object) -> str:
    if not isinstance(pricing, dict):
        return "-"

    try:
        prompt = float(pricing.get("prompt", "0")) * 1_000_000
        completion = float(pricing.get("completion", "0")) * 1_000_000
    except (TypeError, ValueError):
        return "-"
    if prompt < 0 or completion < 0:
        return "Variable"
    return f"${prompt:g} in / ${completion:g} out per M"


def _fetch_openrouter_models(config: Config, timeout: int) -> List[Model]:
    api_key = config("OPENROUTER_API_KEY", default=None)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    payload = _request_json(
        "https://openrouter.ai/api/v1/models", headers, timeout
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise ModelCatalogError("OpenRouter returned an unexpected models response.")

    models = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        is_free = model_id.endswith(":free") or model_id == "openrouter/free"
        models.append(
            _model(
                model_id,
                item.get("name"),
                item.get("context_length"),
                "Free" if is_free else "Paid",
                "Free" if is_free else _format_openrouter_price(item.get("pricing")),
            )
        )
    return models


def _fetch_gemini_models(config: Config, timeout: int) -> List[Model]:
    headers = {"x-goog-api-key": _api_key(config, "GEMINI_API_KEY")}
    page_token = None
    models = []

    while True:
        params = {"pageSize": "1000"}
        if page_token:
            params["pageToken"] = page_token
        payload = _request_json(
            "https://generativelanguage.googleapis.com/v1beta/models?"
            + urlencode(params),
            headers,
            timeout,
        )
        data = payload.get("models")
        if not isinstance(data, list):
            raise ModelCatalogError("Gemini returned an unexpected models response.")

        for item in data:
            if not isinstance(item, dict) or "generateContent" not in item.get(
                "supportedGenerationMethods", []
            ):
                continue
            resource_name = item.get("name")
            if not isinstance(resource_name, str):
                continue
            models.append(
                _model(
                    resource_name.removeprefix("models/"),
                    item.get("displayName"),
                    item.get("inputTokenLimit"),
                )
            )

        page_token = payload.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            return models


def _fetch_anthropic_models(config: Config, timeout: int) -> List[Model]:
    headers = {
        "x-api-key": _api_key(config, "ANTHROPIC_API_KEY"),
        "anthropic-version": "2023-06-01",
    }
    after_id = None
    models = []

    while True:
        params = {"limit": "1000"}
        if after_id:
            params["after_id"] = after_id
        payload = _request_json(
            "https://api.anthropic.com/v1/models?" + urlencode(params),
            headers,
            timeout,
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise ModelCatalogError("Anthropic returned an unexpected models response.")

        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                models.append(
                    _model(
                        item["id"], item.get("display_name"), item.get("max_input_tokens")
                    )
                )

        if not payload.get("has_more"):
            return models
        after_id = payload.get("last_id")
        if not isinstance(after_id, str) or not after_id:
            raise ModelCatalogError("Anthropic returned an invalid pagination cursor.")


def _fetch_ollama_models(config: Config, timeout: int) -> List[Model]:
    base_url = config("OLLAMA_BASE_URL", default="http://localhost:11434")
    payload = _request_json(base_url.rstrip("/") + "/api/tags", timeout=timeout)
    data = payload.get("models")
    if not isinstance(data, list):
        raise ModelCatalogError("Ollama returned an unexpected models response.")

    models = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("model") or item.get("name")
        if isinstance(model_id, str):
            details = item.get("details")
            size = details.get("parameter_size") if isinstance(details, dict) else None
            models.append(_model(model_id, item.get("name"), size, "Installed"))
    return models


def _fetch_custom_models(config: Config, timeout: int) -> List[Model]:
    base_url = config("CUSTOM_API_URL", default=None)
    if not base_url:
        raise ModelCatalogError("CUSTOM_API_URL is not set.")
    api_key = config("CUSTOM_API_KEY", default=None)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    return _models_from_openai_response(
        _request_json(base_url.rstrip("/") + "/models", headers, timeout)
    )


def fetch_models(provider: str, config: Config, timeout: int = 10) -> List[Model]:
    """Fetch the models available from the configured AI provider."""
    provider = provider.lower()
    fetchers = {
        "openrouter": _fetch_openrouter_models,
        "gemini": _fetch_gemini_models,
        "openai": lambda config, timeout: _models_from_openai_response(
            _request_json(
                "https://api.openai.com/v1/models",
                {"Authorization": f"Bearer {_api_key(config, 'OPENAI_API_KEY')}"},
                timeout,
            )
        ),
        "groq": lambda config, timeout: _models_from_openai_response(
            _request_json(
                "https://api.groq.com/openai/v1/models",
                {"Authorization": f"Bearer {_api_key(config, 'GROQ_API_KEY')}"},
                timeout,
            )
        ),
        "anthropic": _fetch_anthropic_models,
        "ollama": _fetch_ollama_models,
        "custom": _fetch_custom_models,
    }
    fetcher = fetchers.get(provider)
    if not fetcher:
        raise ModelCatalogError(f"Unsupported AI_PROVIDER: {provider}")
    return sorted(fetcher(config, timeout), key=lambda model: str(model["id"]).casefold())
