
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

from groq import Groq

logger = logging.getLogger(__name__)

MODEL_NAME = "llama-3.3-70b-versatile"


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.IGNORECASE)


def _parse_json_from_response(text: str) -> Dict[str, Any]:
    """
    Extract JSON from an LLM response that may include markdown fences.
    """
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text.strip())


def extract_structured(
    prompt: str,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> Dict[str, Any]:
    """
    Call Groq with a prompt that requests JSON output.
    Retries on failure up to max_retries times.

    Returns parsed JSON dict.
    Raises RuntimeError if all retries fail.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to your .env file.\n"
            "Get a free key at https://console.groq.com"
        )

    client = Groq(api_key=api_key)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Groq extraction attempt %d/%d", attempt, max_retries)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw_text = response.choices[0].message.content
            logger.debug("Raw LLM response:\n%s", raw_text)
            result = _parse_json_from_response(raw_text)
            return result
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error on attempt %d: %s", attempt, exc)
            last_error = exc
        except Exception as exc:
            logger.warning("Groq API error on attempt %d: %s", attempt, exc)
            last_error = exc

        if attempt < max_retries:
            time.sleep(retry_delay)

    raise RuntimeError(
        f"Groq extraction failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
