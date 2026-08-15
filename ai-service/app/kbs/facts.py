from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.kbs.config import get_kbs_config


_QS_RE = re.compile(r"\bq\.?\s?s\.?\b|\bto\s+100\b|\bad\s+100\b", re.IGNORECASE)


def is_qs_line(ing: IngredientLine) -> bool:
    """Quantum satis lines ('q.s. to 100') legitimately carry no fixed amount."""
    for value in (ing.raw_name, ing.unit, ing.phase):
        if value and _QS_RE.search(value):
            return True
    return False


def is_percent_unit(unit: str | None) -> bool:
    if unit is None:
        return False
    return unit.strip().lower() in {u.lower() for u in get_kbs_config()["percent_units"]}


@dataclass(slots=True)
class FactContext:
    record: FormulationRecord
    source_texts: list[str] = field(default_factory=list)
    percent_mode: bool = False
    # texts of this record's chunks in the vector store;
    # None means the store was unavailable (chunk rules skip)
    indexed_chunk_texts: list[str] | None = None

    @property
    def combined_source(self) -> str:
        texts = [t for t in self.source_texts if t]
        if self.indexed_chunk_texts:
            texts.extend(t for t in self.indexed_chunk_texts if t)
        return "\n".join(texts)

    def dosed_ingredients(self) -> list[IngredientLine]:
        """Ingredients expected to carry an explicit amount (q.s. lines excluded)."""
        return [i for i in self.record.ingredients if not is_qs_line(i)]

    def qs_ingredients(self) -> list[IngredientLine]:
        return [i for i in self.record.ingredients if is_qs_line(i)]


def _detect_percent_mode(record: FormulationRecord) -> bool:
    dosed = [i for i in record.ingredients if not is_qs_line(i)]
    with_unit = [i for i in dosed if i.unit]
    if with_unit:
        percent_count = sum(1 for i in with_unit if is_percent_unit(i.unit))
        return percent_count / len(with_unit) >= 0.5
    amounts = [i.amount for i in dosed if i.amount is not None]
    if len(amounts) >= 2:
        total = sum(amounts)
        return 60.0 <= total <= 130.0
    return False


def build_facts(
    record: FormulationRecord,
    extra_source_texts: list[str] | None = None,
    indexed_chunk_texts: list[str] | None = None,
) -> FactContext:
    sources = [record.source_text]
    if record.vector_text and record.vector_text != record.source_text:
        sources.append(record.vector_text)
    if extra_source_texts:
        sources.extend(extra_source_texts)
    return FactContext(
        record=record,
        source_texts=[s for s in sources if s],
        percent_mode=_detect_percent_mode(record),
        indexed_chunk_texts=indexed_chunk_texts,
    )
