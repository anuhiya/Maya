"""Pydantic schemas for every AI answer (B9, V3).

The model answers in a fixed JSON format; anything that does not fit is rejected. These schemas
check shape only. Whether an answer is true (quotes, numbers, dates) is checked in maya/checks.py.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from maya.models import Category, ChangeType, ExtractedFacts

_PLAIN_NUMBER = re.compile(r"-?\d+(\.\d+)?")


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class ReadSection(_Answer):
    """read_section: the facts the AI reads from one section (B1, B2)."""

    section: str
    title: str
    jurisdiction: str
    effective_date: str  # exactly as written, or "missing"
    value: str | None = None  # digits as written, no $ or % sign, for example "17.25"
    unit: Literal["dollars per hour", "percent", "days"] | None = None
    day_type: Literal["calendar", "business"] | None = None
    obligation: Literal["shall", "must", "may"] | None = None
    category: Category
    rule_quote: str
    date_quote: str | None = None

    @field_validator("section", "title", "jurisdiction", "effective_date", "rule_quote")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _not_blank(value)

    @field_validator("value")
    @classmethod
    def _plain_number(cls, value: str | None) -> str | None:
        if value is not None and not _PLAIN_NUMBER.fullmatch(value):
            raise ValueError("value must be a plain number such as 17.25, without signs or commas")
        return value

    def to_facts(self) -> ExtractedFacts:
        """One to one onto models.ExtractedFacts. The value goes string to Decimal, never via float."""
        data = self.model_dump()
        data["value"] = None if self.value is None else Decimal(self.value)
        return ExtractedFacts(**data)


class CompareSection(_Answer):
    """compare_section: how one section changed between the old and the new version (B2)."""

    change_type: ChangeType
    facts_changed: list[str] = Field(default_factory=list)
    reason: str

    @field_validator("reason")
    @classmethod
    def _one_line(cls, value: str) -> str:
        _not_blank(value)
        if "\n" in value or "\r" in value:
            raise ValueError("reason must be one line")
        return value


class ExplainFinding(_Answer):
    """explain_finding: the reviewer-facing wording for one finding (A2, A3)."""

    headline: str
    recommended_action: str
    owner: str
    routing_reason: str

    @field_validator("headline", "recommended_action", "owner", "routing_reason")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _not_blank(value)


SCHEMAS: dict[str, type[_Answer]] = {
    "read_section": ReadSection,
    "compare_section": CompareSection,
    "explain_finding": ExplainFinding,
}

# Annotation keys Groq's schema validator rejects. Nothing else is removed.
_UNSUPPORTED_KEYS = frozenset({"default", "examples"})


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        target = defs[node["$ref"].rsplit("/", 1)[-1]]
        rest = {k: v for k, v in node.items() if k != "$ref"}
        return _inline_refs({**target, **rest}, defs)
    return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}


def _clean(node: Any, *, top: bool = False) -> Any:
    """Strip unsupported keys by position, so a property that is named "title" survives."""
    if isinstance(node, list):
        return [_clean(item) for item in node]
    if not isinstance(node, dict):
        return node
    options = node.get("anyOf")
    if options and all(set(o) == {"type"} for o in options):
        # Optional simple field: anyOf [string, null] becomes "type": ["string", "null"].
        node = {**{k: v for k, v in node.items() if k != "anyOf"}, "type": [o["type"] for o in options]}
    out: dict[str, Any] = {}
    for key, child in node.items():
        if key in _UNSUPPORTED_KEYS:
            continue
        if key == "title" and not top:
            continue  # annotation on a nested schema; the answer's own title is kept at the top
        if key == "properties":
            out[key] = {name: _clean(sub) for name, sub in child.items()}
        else:
            out[key] = _clean(child)
    return out


def groq_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The JSON schema for `model` in the form Groq accepts (strict, no refs, all fields required)."""
    schema = model.model_json_schema()
    schema = _inline_refs(schema, schema.get("$defs", {}))
    schema = _clean(schema, top=True)
    schema["required"] = list(schema["properties"])
    schema["additionalProperties"] = False
    return schema
