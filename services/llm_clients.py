from __future__ import annotations

import requests

from config.settings import settings


class LLMUnavailableError(Exception):
    def __init__(self, server: str, detail: str):
        self.server = server
        self.detail = detail
        super().__init__(f"{server} unreachable: {detail}")


def list_ollama_models() -> list[str]:
    """Used by the Settings page to populate the model dropdown with
    whatever's actually pulled locally, instead of a hardcoded list."""
    try:
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException as e:
        raise LLMUnavailableError("Ollama", str(e)) from e


def list_lmstudio_models() -> list[str]:
    try:
        resp = requests.get(f"{settings.lmstudio_base_url}/models", timeout=5)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]
    except requests.RequestException as e:
        raise LLMUnavailableError("LM Studio", str(e)) from e


def call_ollama(model: str, prompt: str, system: str | None = None, timeout: int = 120) -> str:
    """Calls Ollama's /api/generate (non-streaming) and returns the text."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    try:
        resp = requests.post(f"{settings.ollama_base_url}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.RequestException as e:
        raise LLMUnavailableError("Ollama", str(e)) from e


def call_lmstudio(model: str, prompt: str, system: str | None = None, timeout: int = 180) -> str:
    """Calls LM Studio's OpenAI-compatible /chat/completions and returns
    the assistant message text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "temperature": 0.1}
    try:
        resp = requests.post(
            f"{settings.lmstudio_base_url}/chat/completions", json=payload, timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError) as e:
        raise LLMUnavailableError("LM Studio", str(e)) from e
