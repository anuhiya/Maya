"""Tests for maya/ai/schemas.py (B1, B2, B9, V3, A2)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from maya.ai.schemas import CompareSection, ExplainFinding, ReadSection, SCHEMAS, groq_json_schema
from maya.models import Category, ChangeType, ExtractedFacts

READ = {
    "section": "3.1",
    "title": "Minimum wage",
    "jurisdiction": "Northvale",
    "effective_date": "January 1, 2027",
    "value": "17.25",
    "unit": "dollars per hour",
    "day_type": None,
    "obligation": "shall",
    "category": "wages",
    "rule_quote": "The minimum wage shall be $17.25 per hour.",
    "date_quote": "Effective January 1, 2027.",
}
COMPARE = {"change_type": "substantive", "facts_changed": ["value"], "reason": "Wage rose from 16.00 to 17.25."}
EXPLAIN = {
    "headline": "Northvale raises its minimum wage",
    "recommended_action": "Review affected hourly staff.",
    "owner": "Payroll",
    "routing_reason": "Wage change needs a person to decide.",
}


def test_read_section_valid():
    r = ReadSection(**READ)
    assert r.category is Category.WAGES


def test_read_section_missing_date_and_nulls_valid():
    r = ReadSection(**{**READ, "effective_date": "missing", "value": None, "unit": None, "date_quote": None})
    assert r.effective_date == "missing"


@pytest.mark.parametrize(
    "change",
    [
        {"category": "taxes"},
        {"unit": "euros"},
        {"day_type": "weekday"},
        {"obligation": "should"},
        {"title": "  "},
        {"rule_quote": ""},
        {"extra": 1},
        {"value": "$17.25"},
        {"value": "3.1%"},
        {"value": "1,000"},
        {"value": "about 20"},
        {"value": 17.25},
    ],
)
def test_read_section_invalid(change):
    with pytest.raises(ValidationError):
        ReadSection(**{**READ, **change})


def test_read_section_missing_field():
    bad = {k: v for k, v in READ.items() if k != "jurisdiction"}
    with pytest.raises(ValidationError):
        ReadSection(**bad)


def test_value_string_becomes_exact_decimal():
    facts = ReadSection(**{**READ, "value": "3.1"}).to_facts()
    assert facts.value == Decimal("3.1")
    assert str(facts.value) == "3.1"


def test_to_facts_maps_one_to_one():
    assert set(ReadSection.model_fields) == set(ExtractedFacts.model_fields)
    facts = ReadSection(**READ).to_facts()
    assert isinstance(facts, ExtractedFacts)
    assert facts.value == Decimal("17.25")
    assert facts.category is Category.WAGES
    assert ReadSection(**{**READ, "value": None}).to_facts().value is None


def test_compare_section_valid():
    c = CompareSection(**COMPARE)
    assert c.change_type is ChangeType.SUBSTANTIVE
    assert CompareSection(change_type="wording_only", facts_changed=[], reason="Reworded.").facts_changed == []


@pytest.mark.parametrize(
    "change",
    [
        {"change_type": "minor"},
        {"reason": ""},
        {"reason": "line one\nline two"},
        {"facts_changed": "value"},
        {"extra": 1},
    ],
)
def test_compare_section_invalid(change):
    with pytest.raises(ValidationError):
        CompareSection(**{**COMPARE, **change})


def test_explain_finding_valid():
    assert ExplainFinding(**EXPLAIN).owner == "Payroll"


@pytest.mark.parametrize("change", [{"headline": ""}, {"owner": "  "}, {"routing_reason": 5}, {"extra": 1}])
def test_explain_finding_invalid(change):
    with pytest.raises(ValidationError):
        ExplainFinding(**{**EXPLAIN, **change})


def test_explain_finding_missing_field():
    with pytest.raises(ValidationError):
        ExplainFinding(**{k: v for k, v in EXPLAIN.items() if k != "owner"})


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_groq_schema_keeps_answer_title_and_is_flat(name):
    model = SCHEMAS[name]
    schema = groq_json_schema(model)
    assert schema["title"] == model.__name__
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"])
    text = str(schema)
    for banned in ("$ref", "$defs", "default", "examples"):
        assert banned not in text


def test_groq_schema_keeps_title_property_and_string_value():
    props = groq_json_schema(ReadSection)["properties"]
    assert "title" in props
    assert props["title"]["type"] == "string"
    assert props["value"]["type"] == ["string", "null"]
    assert props["category"]["enum"] == [c.value for c in Category]
