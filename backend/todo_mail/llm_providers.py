"""Thin LLM provider abstraction.

Each provider exposes:
  chat(system, user, json_mode=False) -> str | None
  chat_with_tool(system, user, tool)  -> dict | None

The `tool` argument uses OpenAI-style schema:
  {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
"""
from __future__ import annotations

import json
import logging
import re
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    def chat(self, system: str, user: str, json_mode: bool = False) -> str | None: ...
    def chat_with_tool(self, system: str, user: str, tool: dict) -> dict | None: ...


class GroqProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self._model = model

    def chat(self, system: str, user: str, json_mode: bool = False) -> str | None:
        from groq import APIError
        from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

        @retry(
            retry=retry_if_exception_type(APIError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        )
        def _call() -> str | None:
            kwargs: dict = {}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
            return resp.choices[0].message.content

        try:
            return _call()
        except Exception:
            logger.exception("Groq chat error")
            return None

    def chat_with_tool(self, system: str, user: str, tool: dict) -> dict | None:
        from groq import APIError, BadRequestError
        from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

        fn_name = tool["function"]["name"]

        @retry(
            retry=retry_if_exception_type(APIError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        )
        def _call() -> dict | None:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": fn_name}},
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                return json.loads(msg.tool_calls[0].function.arguments)
            return None

        try:
            return _call()
        except BadRequestError as e:
            # Groq occasionally embeds the result inside a failed_generation error field
            try:
                body = e.response.json()
                raw = body.get("error", {}).get("failed_generation", "")
                m = re.search(rf"<function={fn_name}>(.*?)</function>", raw, re.DOTALL)
                if m:
                    return json.loads(m.group(1))
            except Exception:
                pass
            logger.exception("Groq bad request, could not recover")
            return None
        except Exception:
            logger.exception("Groq tool call error after retries")
            return None


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package not installed. Run: pip install openai") from exc
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model

    def chat(self, system: str, user: str, json_mode: bool = False) -> str | None:
        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
            return resp.choices[0].message.content
        except Exception:
            logger.exception("OpenAI chat error")
            return None

    def chat_with_tool(self, system: str, user: str, tool: dict) -> dict | None:
        fn_name = tool["function"]["name"]
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": fn_name}},
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                return json.loads(msg.tool_calls[0].function.arguments)
        except Exception:
            logger.exception("OpenAI tool call error")
        return None


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic as _anthropic  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic") from exc
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def chat(self, system: str, user: str, json_mode: bool = False) -> str | None:
        # Anthropic has no JSON mode — inject the constraint into the system prompt
        if json_mode:
            system = system + "\nRespond with ONLY a valid JSON object — no markdown, no extra text."
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text
        except Exception:
            logger.exception("Anthropic chat error")
            return None

    def chat_with_tool(self, system: str, user: str, tool: dict) -> dict | None:
        fn = tool["function"]
        # Convert OpenAI tool schema → Anthropic tool schema
        anthropic_tool = {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn["parameters"],
        }
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[anthropic_tool],
                tool_choice={"type": "tool", "name": fn["name"]},
            )
            for block in resp.content:
                if block.type == "tool_use":
                    return dict(block.input)
        except Exception:
            logger.exception("Anthropic tool call error")
        return None


class LocalProvider(OpenAIProvider):
    """OpenAI-compatible local endpoint (e.g. Ollama).

    Tries native tool use first; falls back to JSON-in-system-prompt when the
    local model doesn't support function calling.
    """

    def __init__(self, model: str, base_url: str) -> None:
        super().__init__(api_key="local", model=model, base_url=base_url)

    def chat_with_tool(self, system: str, user: str, tool: dict) -> dict | None:
        result = super().chat_with_tool(system, user, tool)
        if result is not None:
            return result

        # Fallback: embed the JSON schema in the system prompt
        schema_str = json.dumps(tool["function"]["parameters"], indent=2)
        augmented = (
            f"{system}\n\n"
            f"Respond with ONLY a valid JSON object matching this schema:\n{schema_str}\n"
            "No markdown fences, no extra text."
        )
        raw = self.chat(augmented, user, json_mode=False)
        if not raw:
            return None
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception:
            logger.exception("Local provider JSON parse error")
        return None
