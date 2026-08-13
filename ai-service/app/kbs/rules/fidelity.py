"""Source-fidelity rules: every extracted value must be traceable to the source text.

This is the core precision check against the vector database: the record's
source_text/vector_text is exactly what was chunked and embedded, so a value
that cannot be found there was invented or corrupted during extraction.
"""
from __future__ import annotations

import re

from app.kbs.facts import FactContext
from app.kbs.schemas import RuleFinding, Severity


# LLM extraction can hallucinate values; deterministic parsers at worst misread them.
_STRICT_METHODS = {"llm"}

_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def _amount_variants(amount: float) -> list[str]:
    """Textual forms an extracted number may take in the source ('2', '2.0', '2.50')."""
    variants = {f"{amount:g}"}
    if amount == int(amount):
        variants.add(str(int(amount)))
        variants.add(f"{int(amount)}.0")
        variants.add(f"{int(amount)}.00")
    else:
        text = f"{amount:g}"
        variants.add(text.rstrip("0").rstrip("."))
        variants.add(f"{amount:.2f}")
        variants.add(f"{amount:.1f}")
    return sorted(variants)


def amount_in_source(amount: float, source: str) -> bool:
    for variant in _amount_variants(amount):
        if re.search(rf"(?<![\d.]){re.escape(variant)}(?![\d])", source):
            return True
    return False


def amount_near_name(raw_name: str, amount: float, source: str, window: int = 120) -> bool:
    """Is the amount stated close to the ingredient's name in the source?"""
    tokens = _TOKEN_RE.findall(raw_name.lower())
    if not tokens:
        return amount_in_source(amount, source)
    longest = max(tokens, key=len)
    idx = source.lower().find(longest)
    if idx < 0:
        return False
    # column layouts print the amount before OR after the name
    return amount_in_source(amount, source[max(0, idx - window) : idx + window])


def name_in_source(raw_name: str, source_lower: str) -> bool:
    tokens = _TOKEN_RE.findall(raw_name.lower())
    if not tokens:
        # Names like "TEA" or non-latin script: fall back to a raw substring check.
        cleaned = raw_name.strip().lower()
        return bool(cleaned) and cleaned in source_lower
    # The longest token is the most distinctive one ('hyaluronic' in
    # 'Hyaluronic Acid') — generic tokens like 'acid' match too easily.
    longest = max(tokens, key=len)
    return longest in source_lower


class AmountVerbatimRule:
    rule_id = "fidelity.amount-verbatim"
    family = "fidelity"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        source = facts.combined_source
        if not source.strip():
            return []  # completeness.has-source-text already reports this
        severity: Severity = (
            "error" if facts.record.extraction_method in _STRICT_METHODS else "warning"
        )
        findings: list[RuleFinding] = []
        for ing in facts.dosed_ingredients():
            if ing.amount is None:
                continue
            if amount_in_source(ing.amount, source):
                continue
            label = ing.raw_name.strip() or (ing.normalized_name or "<unnamed>")
            findings.append(
                RuleFinding(
                    rule_id=self.rule_id,
                    family=self.family,
                    severity=severity,
                    message=(
                        f"Amount {ing.amount:g} for '{label}' is not stated verbatim "
                        "in the source text"
                    ),
                    ingredient=label,
                    field="amount",
                    observed=f"{ing.amount:g}",
                )
            )
        return findings


class NameInSourceRule:
    rule_id = "fidelity.name-in-source"
    family = "fidelity"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        source = facts.combined_source
        if not source.strip():
            return []
        source_lower = source.lower()
        findings: list[RuleFinding] = []
        for ing in facts.record.ingredients:
            if not ing.raw_name.strip():
                continue
            if name_in_source(ing.raw_name, source_lower):
                continue
            findings.append(
                RuleFinding(
                    rule_id=self.rule_id,
                    family=self.family,
                    severity="warning",
                    message=(
                        f"Ingredient '{ing.raw_name.strip()}' does not appear "
                        "in the source text"
                    ),
                    ingredient=ing.raw_name.strip(),
                    field="raw_name",
                )
            )
        return findings


class ChunkDriftRule:
    """The record's stored source text must still match its indexed chunks.

    Catches records and vector-store chunks drifting apart (e.g. a partial
    re-ingest updated one but not the other). Skips when the vector store
    was unavailable or holds no chunk for this record.
    """

    rule_id = "fidelity.chunk-drift"
    family = "fidelity"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        chunks = facts.indexed_chunk_texts
        if chunks is None or not chunks:
            return []
        reference = facts.record.vector_text or facts.record.source_text
        if not reference.strip():
            return []
        probe = re.sub(r"\s+", " ", reference.strip().lower())[:80]
        for chunk in chunks:
            if probe in re.sub(r"\s+", " ", chunk.strip().lower()):
                return []
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="warning",
                message=(
                    "Indexed vector-store chunks no longer match this record's "
                    "stored source text — record and index may be out of sync"
                ),
                field="vector_text",
            )
        ]


def build_rules() -> list:
    return [AmountVerbatimRule(), NameInSourceRule(), ChunkDriftRule()]
