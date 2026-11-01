"""Numeric limits must come from the guideline being reviewed, whatever the document is called."""
import pytest

from backend.app.services.verdict_engine import (
    VERDICT_CONTRADICTED,
    VERDICT_SUPPORTED,
    verdict_engine,
)


def _passage(text):
    return {
        "chunk_id": "c1",
        "document_id": "any-uploaded-document",
        "source_filename": "policy.txt",
        "page_number": 1,
        "text": text,
        "similarity_score": 0.8,
        "distance": 0.2,
    }


LOGO_RULE = "Brand logo and corporate emblem must always be positioned in the top-left corner with at least 30px clear buffer margin."
DISCOUNT_RULE = "Pricing discount claims cannot exceed 30% without prior written compliance officer authorization."


@pytest.mark.parametrize(
    "claim, expected",
    [
        ("Brand logo appears in the top-left corner with a 25px clear buffer margin.", VERDICT_CONTRADICTED),
        ("Brand logo appears in the top-left corner with a 35px clear buffer margin.", VERDICT_SUPPORTED),
    ],
)
def test_logo_margin_minimum_is_read_from_the_guideline(claim, expected):
    result = verdict_engine.classify("c", claim, [_passage(LOGO_RULE)])
    assert result.verdict == expected
    assert "30px" in result.explanation


@pytest.mark.parametrize(
    "claim, expected",
    [
        ("Get a pricing discount of 40% off.", VERDICT_CONTRADICTED),
        ("Get a pricing discount of 25% off.", VERDICT_SUPPORTED),
    ],
)
def test_discount_cap_is_read_from_the_guideline(claim, expected):
    result = verdict_engine.classify("c", claim, [_passage(DISCOUNT_RULE)])
    assert result.verdict == expected
    assert "30%" in result.explanation


def test_no_rule_depends_on_a_benchmark_document_id():
    import inspect

    from backend.app.services import verdict_engine as module

    assert "doc-finance" not in inspect.getsource(module)
