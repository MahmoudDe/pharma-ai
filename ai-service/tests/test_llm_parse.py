from app.reasoning.llm import _parse


def test_parse_extracts_answer_from_json_wrapper():
    raw = """{
  "answer": "لا أستطيع المساعدة في هذا الموضوع. يُرجى البقاء في نطاق صياغة مستحضرات التجميل أو الأدوية.",
  "formula_lines": [],
  "citations": []
}"""
    parsed = _parse(raw)
    assert parsed.answer.startswith("لا أستطيع المساعدة")
    assert "formula_lines" not in parsed.answer
    assert parsed.citations == []
    assert parsed.formula_lines == []


def test_parse_strips_markdown_fence():
    raw = """```json
{"answer": "Use 2% glycerin [S1].", "formula_lines": [], "citations": []}
```"""
    parsed = _parse(raw)
    assert parsed.answer == "Use 2% glycerin [S1]."


def test_parse_plain_prose_passthrough():
    raw = "This cream is intended for hands [S1]."
    parsed = _parse(raw)
    assert parsed.answer == raw


def test_parse_citations_and_formula_lines():
    raw = """{
      "answer": "Glycerin is a humectant [S1].",
      "formula_lines": [{"ingredient": "Glycerin", "percentage": "5.0%", "source_index": 1}],
      "citations": [{"source_index": 1, "quote": "glycerin 5.0%", "confidence": "high"}]
    }"""
    parsed = _parse(raw)
    assert parsed.answer == "Glycerin is a humectant [S1]."
    assert len(parsed.formula_lines) == 1
    assert parsed.formula_lines[0].ingredient == "Glycerin"
    assert len(parsed.citations) == 1
    assert parsed.citations[0].source_index == 1
