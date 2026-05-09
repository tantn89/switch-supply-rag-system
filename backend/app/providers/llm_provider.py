"""LLM provider abstraction for chat completion + streaming + tool calling."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class LLMProvider(ABC):
    """Abstract LLM provider with OpenAI-compatible message + tool semantics."""

    name: str
    model: str

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Synchronous completion. Returns the assistant message dict."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Async generator yielding text deltas as they arrive."""


class OpenAIProvider(LLMProvider):
    """OpenAI gpt-4o-mini provider."""

    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import AsyncOpenAI, OpenAI

        self._sync = OpenAI(api_key=api_key)
        self._async = AsyncOpenAI(api_key=api_key)
        self.model = model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(model=self.model, messages=messages, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        resp = self._sync.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        return {
            "role": msg.role,
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (msg.tool_calls or [])
            ],
        }

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        stream = await self._async.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta


class GroqProvider(LLMProvider):
    """Groq llama-3.3-70b-versatile (free tier). OpenAI-compatible API."""

    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        from groq import AsyncGroq, Groq

        self._sync = Groq(api_key=api_key)
        self._async = AsyncGroq(api_key=api_key)
        self.model = model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(model=self.model, messages=messages, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        resp = self._sync.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        return {
            "role": msg.role,
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (msg.tool_calls or [])
            ],
        }

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        stream = await self._async.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta
