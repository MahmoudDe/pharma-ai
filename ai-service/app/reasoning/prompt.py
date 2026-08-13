"""System prompt and context formatting for grounded RAG."""
from __future__ import annotations

from app.ingestion.formula_detect import is_formula_chunk
from app.formulation.schemas import FormulationRecord
from app.retrieval.search import RetrievedChunk


SYSTEM_PROMPT = """\
You are Pharma AI, a cautious assistant for cosmetic and pharmaceutical formulation R&D.

STRICT RULES (apply unconditionally):
1. Answer ONLY using facts that appear in the SOURCES block below. If the sources do not
   contain enough information to answer, say so explicitly. Never invent ingredients,
   percentages, manufacturing steps, or trade names.
2. Every non-trivial factual statement in your answer must reference one of the sources by
   its [S#] tag. Multiple tags are fine, e.g. "Use 1-3% glycerin [S2][S4]".
3. Percentages, temperatures, and pH values must be copied from the sources character-for-
   character if present. If a percentage is not in the source text, use null in formula_lines
   and write "percentage not stated in source" in the answer for that ingredient.
4. If sources conflict, surface the conflict; do not silently pick one.
5. If the user asks something outside cosmetic / pharma formulation, decline briefly and
   suggest staying on topic.
6. When listing a formula, prefer the formula_lines array (see JSON schema below).

You must respond with a single JSON object matching this schema:
{
  "answer": "<markdown string, with [S#] inline citations>",
  "formula_lines": [
    {
      "ingredient": "<name exactly as in source>",
      "percentage": "<e.g. 5.0% copied verbatim from source, or null if not stated>",
      "source_index": <int, 1-based [S#] tag>
    }
  ],
  "citations": [
    {
      "source_index": <int, 1-based, matches [S#] in the answer>,
      "quote": "<short verbatim snippet from that source, max ~200 chars>",
      "confidence": "low" | "medium" | "high"
    }
  ]
}

If sources are weak or absent, "citations" may be empty, "formula_lines" may be empty, and
"answer" should say you cannot answer confidently. Do not output anything outside the JSON object.
"""

PROSE_MAX_CHARS = 1800
FORMULA_MAX_CHARS = 6000


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a numbered SOURCES block consumed by the LLM."""
    if not chunks:
        return "SOURCES:\n(none)"

    lines = ["SOURCES:"]
    for i, chunk in enumerate(chunks, start=1):
        snippet = chunk.text.strip()
        limit = FORMULA_MAX_CHARS if is_formula_chunk(chunk.text) else PROSE_MAX_CHARS
        if len(snippet) > limit:
            snippet = snippet[:limit].rsplit(" ", 1)[0] + " ..."
        page_parts = [f"PDF p.{chunk.pdf_page}"]
        if chunk.printed_page is not None:
            page_parts.append(f"Book p.{chunk.printed_page}")
        page_label = " · ".join(page_parts)
        lines.append(f"[S{i}] {chunk.doc_title} ({page_label})")
        lines.append(snippet)
        lines.append("")
    return "\n".join(lines).rstrip()


def format_structured_formulations(
    records: list[FormulationRecord],
    kbs_annotations: dict[str, tuple[float, str, list[str]]] | None = None,
) -> str:
    if not records:
        return ""
    lines = ["STRUCTURED_FORMULATIONS (verified extracted JSON; prefer for formula_lines when confidence >= 0.7):"]
    if kbs_annotations and any(a[1] != "verified" for a in kbs_annotations.values()):
        lines.append(
            "NOTE: records marked precision=review contain amounts the knowledge-base "
            "validation could not fully verify — say so explicitly when you use them."
        )
    for i, rec in enumerate(records, start=1):
        annotation = (kbs_annotations or {}).get(rec.id)
        kbs_part = ""
        if annotation:
            score, status, _warnings = annotation
            kbs_part = f" precision={status}({score:.2f})"
        lines.append(
            f"[F{i}] id={rec.id} name={rec.name!r} doc={rec.doc_id} pdf_p.{rec.pdf_page} "
            f"confidence={rec.confidence:.2f}{kbs_part}"
        )
        if annotation:
            for warning in annotation[2]:
                lines.append(f"  ! {warning}")
        for ing in rec.ingredients[:25]:
            amt = f"{ing.amount}{ing.unit or ''}" if ing.amount is not None else "amount not stated"
            lines.append(f"  - {ing.raw_name}: {amt}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_conversation_history(
    history: list,
    *,
    max_messages: int = 10,
    max_chars_per_message: int = 600,
) -> str:
    """Render prior turns for the LLM (not used for citation)."""
    if not history:
        return ""
    recent = history[-max_messages:]
    lines = ["CONVERSATION HISTORY (context only; cite SOURCES below, not this block):"]
    for msg in recent:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else "")
        content = getattr(msg, "content", None) or (
            msg.get("content") if isinstance(msg, dict) else ""
        )
        content = str(content).strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message].rsplit(" ", 1)[0] + " …"
        lines.append(f"{label}: {content}")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)
