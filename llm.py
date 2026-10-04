"""The single unified entry point for model generation and health checks."""

from __future__ import annotations

import logging
from typing import Any

from backends import gemini, jsonutil
from config import settings

logger = logging.getLogger("label_reader.llm")


class LLMError(Exception):
    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class BackendUnavailable(LLMError):
    pass


class MissingApiKey(LLMError):
    pass


class ModelNotFound(LLMError):
    pass


class NoVisionSupport(LLMError):
    pass


class ModelTimeout(LLMError):
    pass


class ModelOutputError(LLMError):
    pass


def generate(
    images: list[bytes] | None = None,
    prompt: str = "",
    schema: dict[str, Any] | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> dict[str, Any] | str:
    """The single entry point to the Gemma 4 / Gemini model.
    
    Returns a parsed dict when schema is given, else plain text.
    """
    img_list = images or []

    def _call(p: str) -> str:
        return gemini.run(
            images=img_list,
            prompt=p,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            model=settings.gemini_model,
        )

    # Call backend
    raw_response = _call(prompt)

    if schema is None:
        return raw_response

    # Parse JSON
    try:
        return jsonutil.parse_json(raw_response)
    except Exception as first_err:
        logger.warning("First JSON parse attempt failed: %s. Retrying once with reminder...", first_err)
        retry_prompt = (
            f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON matching the schema. No explanations, no markdown."
        )
        try:
            retry_response = _call(retry_prompt)
            return jsonutil.parse_json(retry_response)
        except Exception as second_err:
            logger.error("Second JSON parse attempt also failed: %s", second_err)
            raise ModelOutputError(
                f"Model failed to produce valid JSON: {second_err}",
                user_message="The model gave an unreadable answer. Please try again.",
            ) from second_err


def health(backend: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """Runs health check for Google AI Studio API and returns structured check results."""
    checks: list[dict[str, Any]] = []
    overall_ok = True

    key = api_key or settings.gemini_api_key
    model = settings.gemini_model

    # 1. Key present
    if not key:
        checks.append({
            "name": "Google AI Studio API key",
            "ok": False,
            "detail": "API key required. Add it to .env or paste it in the custom key box.",
        })
        return {"ok": False, "backend": "gemini", "model": model, "checks": checks}
    else:
        checks.append({
            "name": "Google AI Studio API key",
            "ok": True,
            "detail": "API key configured.",
        })

    # 2. List models & verify Gemma 4
    model_found = False
    gemma_models: list[str] = []
    try:
        from google import genai
        client = genai.Client(api_key=key)
        models_pager = client.models.list()
        for m in models_pager:
            m_name = getattr(m, "name", str(m))
            if "gemma" in m_name.lower():
                gemma_models.append(m_name)
            if model.lower() in m_name.lower():
                model_found = True

        if model_found:
            checks.append({
                "name": f"Gemma 4 model '{model}' available in API",
                "ok": True,
                "detail": f"Model '{model}' verified and active.",
            })
        else:
            top_10 = gemma_models[:10]
            detail_msg = f"Model '{model}' not found in API. Available Gemma models: {', '.join(top_10) if top_10 else 'None'}"
            checks.append({
                "name": f"Gemma 4 model '{model}' available in API",
                "ok": False,
                "detail": detail_msg,
            })
            overall_ok = False

        # 3. Quick test call
        if overall_ok:
            resp = client.models.generate_content(
                model=model,
                contents="Reply with the word OK",
            )
            if resp.text:
                checks.append({
                    "name": "Inference test",
                    "ok": True,
                    "detail": f"Response received: {resp.text.strip()[:30]}",
                })
            else:
                checks.append({
                    "name": "Inference test",
                    "ok": False,
                    "detail": "Model returned empty response.",
                })
                overall_ok = False

    except Exception as exc:
        checks.append({
            "name": "API connection check",
            "ok": False,
            "detail": f"API error: {exc}",
        })
        overall_ok = False

    return {"ok": overall_ok, "backend": "gemini", "model": model, "checks": checks}
