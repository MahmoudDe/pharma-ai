from app.retrieval.arabic_query import english_search_query, query_has_arabic


def test_query_has_arabic_detects_script():
    assert query_has_arabic("شامبو بدون كبريتات")
    assert not query_has_arabic("sulfate free shampoo")


def test_english_search_query_passthrough_latin():
    q = "Compare CAPB and SLS in baby shampoo"
    assert english_search_query(q) == q
