"""Gemini API online backend implementation using google-genai SDK."""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from pipeline.models import flatten_schema

logger = logging.getLogger("label_reader.gemini")


class GeminiBackend:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model

    def run(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Calls Gemini API using google-genai SDK."""
        from llm import MissingApiKey, ModelNotFound, ModelTimeout

        if not self.api_key:
            raise MissingApiKey(
                "Gemini API key is missing.",
                user_message="Online mode needs a Gemini API key. Add it to .env or paste it in the optional key box.",
            )

        try:
            from google import genai
            from google.genai import types
            from google.genai.errors import APIError
        except ImportError as err:
            logger.error("google-genai package is not installed: %s", err)
            raise

        client = genai.Client(api_key=self.api_key)

        contents: list[Any] = []
        for img_bytes in images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        
        final_prompt = prompt
        effective_max_tokens = max(max_tokens, 3072)
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": effective_max_tokens,
        }

        if schema:
            flat_schema = flatten_schema(schema)
            config_kwargs["response_mime_type"] = "application/json"
            # Gemma 4 via Gemini API supports response_schema natively (tested).
            # Use it unconditionally for all models — gives structured, reliable JSON.
            config_kwargs["response_schema"] = flat_schema

        contents.append(final_prompt)

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            # Try response.text first (returns non-thought text in google-genai)
            if response.text:
                return response.text
            # If thinking model generated answer in thought or last part, extract safely
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                for p in reversed(parts):
                    txt = getattr(p, "text", "") or ""
                    if txt and ("{" in txt or not getattr(p, "thought", False)):
                        return txt
            return ""
        except APIError as exc:
            msg = str(exc).lower()
            code = getattr(exc, "code", None)
            if code in (401, 403) or "api_key" in msg or "permission" in msg or "unauthenticated" in msg:
                from llm import MissingApiKey
                raise MissingApiKey(
                    f"Gemini API key rejected: {exc}",
                    user_message="The API key was rejected. Check it in Google AI Studio.",
                ) from exc
            if code == 404 or "not found" in msg:
                raise ModelNotFound(
                    f"Model '{self.model}' not found in Gemini API.",
                    user_message=f"Model not found. Model '{self.model}' was not found in the Gemini API.",
                ) from exc
            if code == 429 or "resource_exhausted" in msg or "quota" in msg:
                from llm import ModelTimeout
                raise ModelTimeout(
                    f"Gemini rate limit exceeded: {exc}",
                    user_message="Rate limit reached. Wait a minute and try again.",
                ) from exc
            logger.error("Gemini API error (%s): %s", code, exc)
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                raise ModelTimeout(
                    "Gemini API request timed out.",
                    user_message="The model took too long. Try a smaller photo or switch mode.",
                ) from exc
            raise


def run(
    images: list[bytes],
    prompt: str,
    schema: dict[str, Any] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    backend = GeminiBackend(api_key=api_key, model=model)
    return backend.run(
        images=images,
        prompt=prompt,
        schema=schema,
        temperature=temperature,
        max_tokens=max_tokens,
    )
