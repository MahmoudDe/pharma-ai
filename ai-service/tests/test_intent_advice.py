from app.retrieval.intent import classify_query
from app.retrieval.query_signals import extract_query_signals


def test_cream_suitability_is_reasoning_not_lookup():
    q = "Is this cream suitable for use on all body parts?"
    result = classify_query(q)
    assert result.route == "reasoning"
    assert extract_query_signals(q).asks_advice


def test_arabic_cream_suitability_is_reasoning():
    q = "هل يصلح هذا الكريم للاستخدام لكل أعضاء الجسم؟"
    result = classify_query(q)
    assert result.route == "reasoning"
    assert extract_query_signals(q).asks_advice


def test_can_i_use_cream_on_face_is_reasoning():
    q = "Can I use this cream on my face?"
    assert classify_query(q).route == "reasoning"


def test_formula_request_with_suitable_for_dry_skin_stays_lookup():
    # Recipe request with a skin claim — not an advice question about "this" product.
    q = "Give me a hand cream formula suitable for dry skin"
    assert classify_query(q).route == "lookup"


def test_plain_cream_formula_stays_lookup():
    assert classify_query("Give me a hand cream formula").route == "lookup"
