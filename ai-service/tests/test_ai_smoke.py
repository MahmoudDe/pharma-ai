"""Cross-module AI smoke tests (no Qdrant / LLM required)."""
from __future__ import annotations

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.search import structured_search
from app.reasoning.brief import merge_intent_with_brief
from app.reasoning.query_rewrite import rewrite_search_query
from app.retrieval.intent import parse_query_intent
from app.schemas import ChatHistoryMessage, StructuredBrief


def _record(
    name: str,
    ingredients: list[tuple[str, str, float]],
    fid: str = "smoke-1",
) -> FormulationRecord:
    return FormulationRecord(
        id=fid,
        name=name,
        product_types=["shampoo"],
        doc_id="doc",
        pdf_page=1,
        source_text=name,
        ingredients=[
            IngredientLine(
                raw_name=raw,
                normalized_name=norm,
                amount=amt,
                unit="%",
            )
            for raw, norm, amt in ingredients
        ],
    )


def test_merge_intent_with_brief_adds_product_type():
    intent = parse_query_intent("formula with CAPB")
    brief = StructuredBrief(product_type="baby shampoo", target_attributes=["mild"])
    merged = merge_intent_with_brief(intent, brief)
    assert "baby_shampoo" in merged.product_types
    assert merged.wants_formula


def test_rewrite_search_query_heuristic_follow_up():
    history = [
        ChatHistoryMessage(role="user", content="Give me a baby shampoo formula"),
        ChatHistoryMessage(role="assistant", content="Here is a mild baby shampoo…"),
    ]
    query, rewritten = rewrite_search_query("make it sulfate-free", history)
    assert rewritten
    assert "baby shampoo" in query.lower()
    assert "sulfate" in query.lower()


def test_structured_search_filters_cost_brief(monkeypatch):
    cheap = _record(
        "Cheap Shampoo",
        [("Water", "water", 95.0), ("Glycerin", "glycerin", 5.0)],
        "cheap",
    )
    rich = _record(
        "Rich Serum",
        [("Water", "water", 50.0), ("Tocopherol", "tocopherol", 50.0)],
        "rich",
    )

    monkeypatch.setattr(
        "app.formulation.search.list_formulations",
        lambda **kw: [cheap, rich],
    )

    intent = parse_query_intent("shampoo formula")
    brief = StructuredBrief(cost_target=1.0)
    result = structured_search("shampoo formula", intent, limit=5, brief=brief)
    names = [m.record.name for m in result.matches]
    assert "Cheap Shampoo" in names
    assert "Rich Serum" not in names


def test_structured_search_filters_eu_markets(monkeypatch):
    clean = _record(
        "Mild Shampoo",
        [("Water", "water", 99.0), ("CAPB", "cocamidopropyl betaine", 1.0)],
        "clean",
    )
    bad = _record(
        "Bad Shampoo",
        [("Formaldehyde", "formaldehyde", 1.0), ("Water", "water", 99.0)],
        "bad",
    )

    monkeypatch.setattr(
        "app.formulation.search.list_formulations",
        lambda **kw: [clean, bad],
    )

    intent = parse_query_intent("shampoo")
    brief = StructuredBrief(markets=["EU"])
    result = structured_search("shampoo", intent, limit=5, brief=brief)
    names = [m.record.name for m in result.matches]
    assert "Mild Shampoo" in names
    assert "Bad Shampoo" not in names
