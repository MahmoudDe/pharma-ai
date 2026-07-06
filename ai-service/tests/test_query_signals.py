"""Tests for query signal extraction."""
from app.retrieval.query_signals import extract_query_signals, fuzzy_name_match


def test_compare_targets_extracted():
    signals = extract_query_signals(
        "Compare the emulsifiers used in the Anti-Acne Cream and the Moisturizing Facial Lotion."
    )
    assert len(signals.compare_targets) >= 2
    assert any("anti" in t.lower() for t in signals.compare_targets)
    assert any("lotion" in t.lower() for t in signals.compare_targets)


def test_required_ingredients_extracted():
    signals = extract_query_signals(
        "Identify a lotion that contains both Octyl Salicylate and Benzophenone-3."
    )
    assert any("octyl" in i.lower() for i in signals.required_ingredients)
    assert any("benzophenone" in i.lower() for i in signals.required_ingredients)
    assert signals.asks_identify_with_ingredients


def test_role_question_flag():
    signals = extract_query_signals(
        "What is the role of Propylene Glycol in the Moisturizing Facial Lotion?"
    )
    assert signals.asks_ingredient_role


def test_fuzzy_name_match():
    assert fuzzy_name_match("Anti-Acne Cream", "Moisturisins Anti-Acne Cream")
    assert fuzzy_name_match("Velvet Body Lotion", "Velvety Body Lotion")
