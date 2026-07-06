"""Template responses for lookup/compare without full LLM."""
from __future__ import annotations

from app.formulation.schemas import FormulationRecord


def _ingredient_table(record: FormulationRecord) -> str:
    lines = [f"## {record.name}", ""]
    if record.product_types:
        lines.append(f"**Product types:** {', '.join(record.product_types)}")
    lines.append("")
    lines.append("| Ingredient | Amount | Phase |")
    lines.append("|------------|--------|-------|")
    for ing in record.ingredients:
        amount = "—"
        if ing.amount is not None:
            amount = f"{ing.amount}"
            if ing.unit:
                amount += f" {ing.unit}"
        lines.append(f"| {ing.raw_name} | {amount} | {ing.phase or '—'} |")
    if record.procedure:
        lines.append("")
        lines.append("**Procedure (excerpt):**")
        for i, step in enumerate(record.procedure[:5], start=1):
            lines.append(f"{i}. {step}")
    src = record.doc_title or record.doc_id
    page = record.printed_page or record.pdf_page
    lines.append("")
    lines.append(f"*Source: {src}, page {page}*")
    return "\n".join(lines)


def format_lookup_response(records: list[FormulationRecord]) -> str:
    if not records:
        return ""
    parts = [_ingredient_table(records[0])]
    if len(records) > 1:
        parts.append("")
        parts.append("**Other matches:**")
        for r in records[1:3]:
            parts.append(f"- {r.name} ({len(r.ingredients)} ingredients)")
    return "\n".join(parts)


def _emulsifier_hint(record: FormulationRecord) -> str:
    emulsifiers = [
        ing.raw_name
        for ing in record.ingredients
        if any(
            kw in (ing.raw_name or "").lower()
            for kw in ("emulsif", "polawax", "stearate", "wax", "peg-", "glyceryl")
        )
    ]
    if emulsifiers:
        return f"**Emulsifiers / structurants:** {', '.join(emulsifiers[:6])}"
    return ""


def format_compare_response(records: list[FormulationRecord]) -> str:
    if len(records) < 2:
        return format_lookup_response(records)
    lines = ["## Formula comparison", ""]
    for rec in records[:3]:
        lines.append(_ingredient_table(rec))
        hint = _emulsifier_hint(rec)
        if hint:
            lines.append(hint)
        lines.append("")
    if len(records) >= 2:
        a_names = {ing.normalized_name or ing.raw_name for ing in records[0].ingredients}
        b_names = {ing.normalized_name or ing.raw_name for ing in records[1].ingredients}
        only_a = [ing.raw_name for ing in records[0].ingredients if (ing.normalized_name or ing.raw_name) not in b_names][:6]
        only_b = [ing.raw_name for ing in records[1].ingredients if (ing.normalized_name or ing.raw_name) not in a_names][:6]
        if only_a or only_b:
            lines.append("**Ingredient differences (from sources):**")
            if only_a:
                lines.append(f"- Only in *{records[0].name}*: {', '.join(only_a)}")
            if only_b:
                lines.append(f"- Only in *{records[1].name}*: {', '.join(only_b)}")
    return "\n".join(lines)


def format_transparent_failure(
    query: str,
    closest_structured: list[FormulationRecord],
    closest_chunk_titles: list[str],
) -> str:
    lines = [
        f"I could not find an exact match in the indexed references for: \"{query}\".",
        "",
    ]
    if closest_structured:
        lines.append("**Closest structured formulations:**")
        for r in closest_structured[:3]:
            types = ", ".join(r.product_types) or "general"
            lines.append(f"- {r.name} ({types}, {len(r.ingredients)} ingredients)")
    if closest_chunk_titles:
        lines.append("")
        lines.append("**Related passages:**")
        for title in closest_chunk_titles[:3]:
            lines.append(f"- {title}")
    lines.append("")
    lines.append("Try rephrasing with a specific product type or ingredient name.")
    return "\n".join(lines)
