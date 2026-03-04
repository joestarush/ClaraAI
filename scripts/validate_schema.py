
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple

from pydantic import ValidationError

from schemas import AccountMemo, AgentSpec

logger = logging.getLogger(__name__)

# Memo validation


def validate_memo(raw: Dict[str, Any]) -> Tuple[bool, AccountMemo | None, str]:
    """
    Validate a dict against AccountMemo schema.

    Returns:
        (is_valid, memo_object_or_None, error_message)
    """
    try:
        memo = AccountMemo(**raw)
        return True, memo, ""
    except ValidationError as exc:
        errors = exc.errors()
        error_summary = "; ".join(
            f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors
        )
        logger.warning("Memo validation failed: %s", error_summary)
        return False, None, error_summary

# Agent spec validation


def validate_agent_spec(raw: Dict[str, Any]) -> Tuple[bool, AgentSpec | None, str]:
    """
    Validate a dict against AgentSpec schema.
    """
    try:
        spec = AgentSpec(**raw)
        return True, spec, ""
    except ValidationError as exc:
        errors = exc.errors()
        error_summary = "; ".join(
            f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors
        )
        logger.warning("AgentSpec validation failed: %s", error_summary)
        return False, None, error_summary


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python validate_schema.py <memo|agent> <json_file>")
        sys.exit(1)

    schema_type = sys.argv[1]
    json_path = sys.argv[2]

    with open(json_path) as f:
        data = json.load(f)

    if schema_type == "memo":
        valid, obj, err = validate_memo(data)
    elif schema_type == "agent":
        valid, obj, err = validate_agent_spec(data)
    else:
        print(f"Unknown schema type: {schema_type}")
        sys.exit(1)

    if valid:
        print(f"✅  Validation passed for {json_path}")
    else:
        print(f"❌  Validation failed: {err}")
        sys.exit(1)
