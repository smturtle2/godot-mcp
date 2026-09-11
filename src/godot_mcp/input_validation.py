"""Concise argument errors from the public input contracts."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .bridge import ToolError


def validate_arguments(validator: Draft202012Validator, arguments: dict[str, Any]) -> None:
    error = next(validator.iter_errors(arguments), None)
    if error is None:
        return
    path = list(error.absolute_path)
    details: dict[str, Any] = {"path": path, "rule": error.validator}
    rule, expected = error.validator, error.validator_value
    if rule == "required" and isinstance(error.instance, dict):
        missing = [name for name in expected if name not in error.instance]
        details["required"] = missing
        path.extend(missing[:1])
        message = "Required field missing: " + ", ".join(missing) + "."
    elif rule == "additionalProperties" and isinstance(error.instance, dict):
        extra = [name for name in error.instance if name not in error.schema.get("properties", {})]
        details["unexpected"] = extra
        path.extend(extra[:1])
        message = "Unexpected field: " + ", ".join(extra) + "."
    elif rule in {"enum", "const", "type"}:
        details["expected"] = expected
        message = {"enum": "Choose a supported value.", "const": "Use the required value.",
                   "type": "Argument has the wrong type."}[rule]
    elif rule in {"minProperties", "maxProperties"} and error.schema.get("minProperties") == error.schema.get("maxProperties") == 1:
        choices = list(error.schema.get("properties", {}))
        provided = list(error.instance) if isinstance(error.instance, dict) else []
        details["choices"] = choices
        details["provided"] = provided
        details["expected"] = 1
        message = "Choose exactly one of: " + ", ".join(choices) + "."
    else:
        details["expected"] = expected
        message = f"Argument does not satisfy {rule}."
    raise ToolError("INVALID_ARGUMENT", message, details)
