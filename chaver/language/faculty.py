"""Language Faculty — Chaver's mouth and ear.

Supports multiple LLM backends, selected by environment variable:

    CHAVER_BACKEND=anthropic   →  Anthropic API (droplet / cloud)
    CHAVER_BACKEND=ollama      →  local Ollama (laptop)
    CHAVER_BACKEND=openai_compat → any OpenAI-compatible endpoint (OpenRouter,
                                   LiteLLM, DeepSeek, ...): CHAVER_BASE_URL,
                                   CHAVER_API_KEY, CHAVER_MODEL (all required)

Within each backend, CHAVER_MODEL selects the specific model:

    # Anthropic
    CHAVER_MODEL=claude-sonnet-5      (default for anthropic)
    CHAVER_MODEL=claude-opus-5
    CHAVER_MODEL=claude-haiku-4-5-20251001

    # Ollama
    CHAVER_MODEL=qwen3                (default for ollama)
    CHAVER_MODEL=llama3.2
    CHAVER_MODEL=mistral
    CHAVER_MODEL=gemma3

Adding a new Ollama model requires no code change — just set CHAVER_MODEL.
Adding a new backend: subclass _Backend, implement generate(), register in
BACKENDS dict.

Design discipline: call sparingly. Track call_count as a discipline metric.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from chaver.archetype.model import Archetype


# ── Environment configuration ───────────────────────────────────────────────

CHAVER_BACKEND = os.environ.get("CHAVER_BACKEND", "anthropic").lower().strip()

# Default models per backend — override with CHAVER_MODEL
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-5",
    "ollama": "qwen3",
    "openai_compat": "",  # no default: CHAVER_MODEL is required (Craig chooses)
}

if CHAVER_BACKEND not in _DEFAULT_MODELS:
    known = ", ".join(_DEFAULT_MODELS)
    raise ValueError(
        f"Unknown CHAVER_BACKEND '{CHAVER_BACKEND}'. Known backends: {known}"
    )

CHAVER_MODEL = os.environ.get("CHAVER_MODEL", _DEFAULT_MODELS[CHAVER_BACKEND])


# ── Request dataclass (shared across all backends) ───────────────────────────

@dataclass
class LanguageRequest:
    """A request for linguistic output.

    Used for genuine linguistic acts: responding to the user, reflection,
    goal revision, strategy revision. Not for internal cognitive work.
    """

    prompt: str
    wm_context: str = ""      # summary of currently-ringing working memory
    purpose: str = "reflection"
    max_tokens: int = 1024


# ── Backend abstraction ──────────────────────────────────────────────────────

class _Backend(ABC):
    """Abstract base for a language backend.

    Subclasses handle the specific client library and wire format.
    The LanguageFaculty calls generate() without knowing which backend is live.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int,
    ) -> str: ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Short display label, e.g. 'anthropic/claude-sonnet-5'."""
        ...


class _AnthropicBackend(_Backend):
    """Anthropic API — for droplet / cloud deployment."""

    def __init__(self, model: str) -> None:
        from anthropic import AsyncAnthropic  # optional dep

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "CHAVER_BACKEND=anthropic but ANTHROPIC_API_KEY is not set.\n"
                "Set it in your .env file or environment before starting Chaver."
            )
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def label(self) -> str:
        return f"anthropic/{self._model}"

    async def generate(self, system_prompt: str, user_content: str, max_tokens: int) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return "\n".join(
            block.text for block in response.content if hasattr(block, "text")
        ).strip()


class _OllamaBackend(_Backend):
    """Local Ollama — for laptop deployment.

    Any model pulled via `ollama pull <model>` can be used:
        qwen3, llama3.2, mistral, gemma3, phi4, deepseek-r1, ...
    Change CHAVER_MODEL in .env — no code change required.
    """

    def __init__(self, model: str) -> None:
        import ollama  # optional dep

        self._client = ollama.AsyncClient()   # connects to localhost:11434
        self._model = model

    @property
    def label(self) -> str:
        return f"ollama/{self._model}"

    async def generate(self, system_prompt: str, user_content: str, max_tokens: int) -> str:
        response = await self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            options={"num_predict": max_tokens},
        )
        return response["message"]["content"].strip()


class _OpenAICompatBackend(_Backend):
    """Any OpenAI-compatible chat-completions endpoint (another developer's model).

    Covers OpenRouter, LiteLLM, DeepSeek and others. Configured only by environment:
        CHAVER_BASE_URL   e.g. https://openrouter.ai/api/v1  (".../chat/completions" is appended)
        CHAVER_API_KEY    bearer token (never logged)
        CHAVER_MODEL      the provider's model id
    """

    def __init__(self, model: str) -> None:
        import httpx  # optional dep (extra: openai_compat)

        base_url = os.environ.get("CHAVER_BASE_URL", "").strip().rstrip("/")
        api_key = os.environ.get("CHAVER_API_KEY", "").strip()
        missing = [n for n, v in (("CHAVER_BASE_URL", base_url),
                                  ("CHAVER_API_KEY", api_key),
                                  ("CHAVER_MODEL", model)) if not v]
        if missing:
            raise RuntimeError(
                "CHAVER_BACKEND=openai_compat but these are not set: "
                + ", ".join(missing) + ". Set them in .env before starting Chaver."
            )
        self._httpx = httpx
        self._url = f"{base_url}/chat/completions"
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        self._model = model

    @property
    def label(self) -> str:
        return f"openai_compat/{self._model}"

    async def generate(self, system_prompt: str, user_content: str, max_tokens: int) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        try:
            response = await self._client.post(self._url, json=payload)
        except self._httpx.HTTPError as exc:
            raise RuntimeError(f"openai_compat: request failed: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"openai_compat: HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("openai_compat: unexpected response shape") from exc
        return (content or "").strip()


# Registry — add new backends here as the project grows
BACKENDS: dict[str, type[_Backend]] = {
    "anthropic":     _AnthropicBackend,
    "ollama":        _OllamaBackend,
    "openai_compat": _OpenAICompatBackend,
}


# ── Public interface ─────────────────────────────────────────────────────────

class LanguageFaculty:
    """Chaver's language faculty.

    Instantiates the backend selected by CHAVER_BACKEND and delegates all
    generation to it. The rest of the codebase never sees which backend is live.

    Design discipline: call sparingly. call_count is a discipline metric —
    the cognitive stack should do most of its work without touching language.
    """

    def __init__(
        self,
        archetype: Archetype,
        backend_name: str = CHAVER_BACKEND,
        model: str = CHAVER_MODEL,
    ) -> None:
        if backend_name not in BACKENDS:
            known = ", ".join(BACKENDS)
            raise ValueError(
                f"Unknown CHAVER_BACKEND '{backend_name}'. "
                f"Known backends: {known}"
            )
        self._backend: _Backend = BACKENDS[backend_name](model)
        self.archetype = archetype
        self.call_count = 0

    @property
    def backend_label(self) -> str:
        """Display label for logging, e.g. 'ollama/qwen3'."""
        return self._backend.label

    async def generate(self, request: LanguageRequest) -> str:
        """Produce linguistic output for a genuine linguistic need."""
        self.call_count += 1

        user_content = request.prompt
        if request.wm_context:
            user_content = (
                f"[Currently-ringing working memory]\n"
                f"{request.wm_context}\n\n"
                f"[Purpose of this speech]\n"
                f"{request.purpose}\n\n"
                f"[Prompt]\n"
                f"{request.prompt}"
            )

        return await self._backend.generate(
            system_prompt=self.archetype.system_context,
            user_content=user_content,
            max_tokens=request.max_tokens,
        )
