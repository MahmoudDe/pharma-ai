from app.retrieval.bm25_index import Bm25Index, _tokenize


def test_tokenize_splits_terms():
    tokens = _tokenize("Sulfate-free baby shampoo 2.5% CAPB")
    assert "shampoo" in tokens
    assert "2.5" in tokens
    assert "%" in tokens


def test_bm25_search_ranks_relevant_doc():
    index = Bm25Index()
    index.records = []
    from app.retrieval.bm25_index import Bm25Record

    index.records = [
        Bm25Record(
            point_id="a",
            doc_id="doc_a",
            doc_title="Book A",
            pdf_page=1,
            printed_page=None,
            chunk_index=0,
            text="Baby shampoo with CAPB and gentle surfactants",
        ),
        Bm25Record(
            point_id="b",
            doc_id="doc_b",
            doc_title="Book B",
            pdf_page=2,
            printed_page=None,
            chunk_index=0,
            text="Industrial floor cleaner degreaser formulation",
        ),
    ]
    index._rebuild()
    hits = index.search("baby shampoo CAPB", top_k=2)
    assert hits
    assert hits[0][0].doc_id == "doc_a"
