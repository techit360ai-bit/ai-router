"""Structured provider output validation with no billing dependencies."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional


class OutputValidationError(ValueError):
    pass


def parse_json_output(text: str) -> Any:
    clean = re.sub(r"```(?:json)?|```", "", text or "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        raise OutputValidationError(f"provider output is not valid JSON: {exc}") from exc


def validate_output(text: str, schema: Optional[Mapping[str, Any]]) -> Any:
    if not schema:
        if not (text or "").strip():
            raise OutputValidationError("provider returned an empty response")
        return text

    value = parse_json_output(text)
    try:
        import jsonschema
        jsonschema.validate(value, dict(schema))
    except ImportError:
        _validate_minimal(value, schema)
    except Exception as exc:
        raise OutputValidationError(f"provider output failed schema validation: {exc}") from exc
    return value


def _validate_minimal(value: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise OutputValidationError(f"{path} must be an object")
        for key in schema.get("required", []):
            if key not in value:
                raise OutputValidationError(f"{path}.{key} is required")
        for key, child in (schema.get("properties") or {}).items():
            if key in value:
                _validate_minimal(value[key], child, f"{path}.{key}")
    elif expected == "array" and not isinstance(value, list):
        raise OutputValidationError(f"{path} must be an array")
    elif expected == "string" and not isinstance(value, str):
        raise OutputValidationError(f"{path} must be a string")
    elif expected == "number" and not isinstance(value, (int, float)):
        raise OutputValidationError(f"{path} must be a number")
    elif expected == "integer" and not isinstance(value, int):
        raise OutputValidationError(f"{path} must be an integer")
    elif expected == "boolean" and not isinstance(value, bool):
        raise OutputValidationError(f"{path} must be a boolean")
