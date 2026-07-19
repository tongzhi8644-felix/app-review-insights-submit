"""
OpenAI-compatible chat client for model-driven semantic stages.
Supports providers such as OpenAI, DeepSeek, Silra, etc.
"""
from __future__ import annotations

import json
import re
from typing import Any

from flask import current_app


class LLMError(RuntimeError):
    pass


def llm_configured() -> bool:
    if not current_app.config.get("AI_ENABLED", True):
        return False
    return bool(current_app.config.get("OPENAI_API_KEY"))


def chat_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Call chat completions and parse a JSON object from the response."""
    if not llm_configured():
        raise LLMError("AI is disabled or OPENAI_API_KEY is not configured")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise LLMError("openai package not installed") from exc

    client = OpenAI(
        api_key=current_app.config["OPENAI_API_KEY"],
        base_url=current_app.config.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1",
    )
    model = current_app.config.get("OPENAI_MODEL") or "deepseek-chat"
    if temperature is None:
        temperature = float(current_app.config.get("OPENAI_TEMPERATURE", 0.7))
    max_tokens = int(current_app.config.get("OPENAI_MAX_TOKENS", 3000))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    # Prefer JSON mode when the gateway supports it; fall back if not.
    try:
        resp = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = client.chat.completions.create(**kwargs)

    content = resp.choices[0].message.content or "{}"
    return _parse_json(content)


def model_meta() -> dict[str, Any]:
    return {
        "provider": "openai_compatible",
        "enabled": current_app.config.get("AI_ENABLED", True),
        "base_url": current_app.config.get("OPENAI_BASE_URL"),
        "model": current_app.config.get("OPENAI_MODEL"),
        "temperature": current_app.config.get("OPENAI_TEMPERATURE", 0.7),
        "max_tokens": current_app.config.get("OPENAI_MAX_TOKENS", 3000),
        "response_format": "json_object_preferred",
        "failure_handling": (
            "On API failure, workflow logs error; if ALLOW_CACHED_FALLBACK "
            "and demo app cache exists, load labeled cache; else heuristic fallback."
        ),
        "anti_hallucination": [
            "Require source_review_ids for every finding/requirement/test case",
            "JSON schema prompts forbid inventing review IDs",
            "Post-validation drops unsupported IDs and marks assumptions",
            "Evidence sufficiency gate when sample_count is low",
        ],
    }


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown fences if the gateway wraps JSON
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise LLMError("Model did not return JSON")
        return json.loads(match.group(0))
