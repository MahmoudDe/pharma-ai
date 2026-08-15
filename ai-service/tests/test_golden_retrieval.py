from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.retrieval.search import RetrievedChunk
from scripts.retrieval_eval import evaluate_retrieval, load_golden_expectations, load_golden_questions


_GOLDEN_PATH = Path(__file__).resolve().parent.parent / "scripts" / "golden_retrieval.json"


def test_golden_retrieval_has_minimum_questions():
    questions = load_golden_questions(_GOLDEN_PATH)
    assert len(questions) >= 50


def test_golden_expectations_parse_for_all_questions():
    expectations = load_golden_expectations(_GOLDEN_PATH)
    questions = load_golden_questions(_GOLDEN_PATH)
    assert len(expectations) == len(questions)


def test_golden_validation_passes_with_synthetic_chunks():
    question = "Give me a baby shampoo formula with ingredient percentages."
    golden = load_golden_expectations(_GOLDEN_PATH)[question]
    chunk = RetrievedChunk(
        doc_id="doc",
        doc_title="Baby shampoo mild formula",
        pdf_page=1,
        printed_page=None,
        chunk_index=0,
        text="Baby shampoo formula with cocamidopropyl betaine 8% glycerin 2% water 90%",
        score=0.9,
        section_title="Baby shampoo",
        product_types=["baby", "shampoo"],
        ingredient_count=8,
    )
    with patch("scripts.retrieval_eval.search", return_value=[chunk]):
        result = evaluate_retrieval(question, top_k=5, golden=golden)
    assert result.errors == []
