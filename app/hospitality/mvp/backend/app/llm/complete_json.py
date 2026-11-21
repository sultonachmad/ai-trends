"""Structured-output helper — call the LLM and parse a JSON object from the reply.

Use this instead of ``json.loads(message.content)`` whenever a feature needs
structured output from the model. The model often wraps the object in a ```json
code fence or adds prose before/after it; this helper tolerates both.

When the reply is empty or holds no parseable JSON object, it raises
``LlmJsonError`` rather than returning a default. The caller MUST follow its use
case's error/retry path and MUST NOT store placeholder values (such as a ``0``
score) as a successful result.
"""

import json
import re
from typing import Any

import litellm

from app.config import settings


class LlmJsonError(ValueError):
    """Raised when an LLM reply is empty or contains no parseable JSON object."""


# ```json ... ``` or a bare ``` ... ``` fence (first fence wins).
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str | None) -> dict[str, Any]:
    """Parse the first JSON object out of a raw LLM reply.

    Tolerates a ```json code fence and prose before/after the object. Raises
    ``LlmJsonError`` when ``text`` is empty or holds no parseable JSON object.
    """
    if not text or not text.strip():
        raise LlmJsonError("LLM reply was empty")

    candidates: list[str] = []
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    # The whole reply, for a bare object with no fence or surrounding prose.
    candidates.append(text)
    # The span from the first "{" to the last "}", for prose around the object.
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise LlmJsonError("LLM reply contained no parseable JSON object")


async def complete_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int = 1000,
) -> dict[str, Any]:
    """Send ``messages`` to the LLM and return the parsed JSON object from the reply.

    Uses ``settings.LLM_MODEL`` unless ``model`` is given. Only a JSON *object* is
    returned; prompt the model for an object and wrap a list as
    ``{"items": [...]}``. Pass a higher ``max_tokens`` for large structured
    replies — a truncated reply does not parse and raises, and the retry then
    fails the same way.

    Raises ``LlmJsonError`` when the reply is empty or holds no parseable JSON
    object — never returns a default. Callers must follow their use case's
    error/retry path on that error and must not persist placeholder values as a
    successful result.
    """
    response = await litellm.acompletion(
        model=model or settings.LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    return _extract_json_object(content)
