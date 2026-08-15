from __future__ import annotations

import re
from dataclasses import dataclass

from app.reasoning.llm import LLMCitation, LLMResponse
from app.retrieval.search import RetrievedChunk


_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_WTG_AMOUNT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().lower())


def quote_in_chunk(quote: str, chunk_text: str) -> bool:
    if not quote or not chunk_text:
        return False
    nq = _normalize(quote)
    nc = _normalize(chunk_text)
    if nq in nc:
        return True
    if len(nq) >= 40 and nq[:40] in nc:
        return True
    return False


def find_verified_quote(quote: str, chunk_text: str, max_len: int = 280) -> str | None:
    if quote_in_chunk(quote, chunk_text):
        return quote[:max_len]
    nq = _normalize(quote)
    nc = _normalize(chunk_text)
    idx = nc.find(nq[: min(len(nq), 60)])
    if idx < 0:
        return None
    ratio = idx / max(len(nc), 1)
    start = int(ratio * len(chunk_text))
    start = max(0, start - 20)
    snippet = chunk_text[start : start + max_len].strip()
    return snippet if snippet else None


def percentage_in_chunk(percentage: str, chunk_text: str) -> bool:
    if not percentage:
        return False
    if percentage.strip() in chunk_text:
        return True
    num_match = re.match(r"(\d+(?:\.\d+)?)\s*%?", percentage.strip())
    if num_match:
        num = num_match.group(1)
        if re.search(rf"\b{re.escape(num)}\b", chunk_text):
            return True
    return False


def amount_in_chunk(amount: str, unit: str | None, chunk_text: str) -> bool:
    if not amount:
        return False
    if amount.strip() in chunk_text:
        return True
    if unit and unit.lower() in ("wtg", "w/w", "%"):
        if re.search(rf"\b{re.escape(amount)}\b", chunk_text):
            return True
        if unit.lower() == "wtg" and "wtg" in chunk_text.lower():
            return bool(re.search(rf"\b{re.escape(amount)}\b", chunk_text))
    return percentage_in_chunk(f"{amount}%", chunk_text)


def extract_percentages(text: str) -> list[str]:
    return _PERCENT_RE.findall(text)


@dataclass(slots=True)
class ValidatedOutput:
    answer: str
    citations: list[LLMCitation]
    quote_verified: list[bool]
    abstain: bool = False


def validate_response(
    llm: LLMResponse,
    chunks: list[RetrievedChunk],
) -> ValidatedOutput:
    verified_citations: list[LLMCitation] = []
    quote_verified: list[bool] = []

    for citation in llm.citations:
        idx0 = citation.source_index - 1
        if idx0 < 0 or idx0 >= len(chunks):
            continue
        chunk = chunks[idx0]
        if quote_in_chunk(citation.quote, chunk.text):
            verified_citations.append(citation)
            quote_verified.append(True)
            continue
        fixed = find_verified_quote(citation.quote, chunk.text)
        if fixed:
            verified_citations.append(
                LLMCitation(
                    source_index=citation.source_index,
                    quote=fixed,
                    confidence="low" if citation.confidence == "high" else citation.confidence,
                )
            )
            quote_verified.append(True)

    abstain = bool(llm.citations) and not verified_citations

    answer = llm.answer

    for line in llm.formula_lines:
        if not line.percentage:
            continue
        idx0 = line.source_index - 1
        if idx0 < 0 or idx0 >= len(chunks):
            answer += f"\n\n(Note: percentage for {line.ingredient} could not be verified against sources.)"
            continue
        pct = line.percentage
        if not percentage_in_chunk(pct, chunks[idx0].text) and not amount_in_chunk(
            pct.rstrip("%"), "%", chunks[idx0].text
        ):
            answer += (
                f"\n\n(Note: {line.ingredient} percentage was not stated verbatim in source [S{line.source_index}].)"
            )

    cited_text = " ".join(
        chunks[c.source_index - 1].text
        for c in verified_citations
        if 0 < c.source_index <= len(chunks)
    )
    for pct in extract_percentages(answer):
        if pct not in cited_text and not any(
            percentage_in_chunk(pct, chunks[c.source_index - 1].text)
            for c in verified_citations
            if 0 < c.source_index <= len(chunks)
        ):
            if pct in answer:
                answer = answer.replace(
                    pct,
                    f"{pct} (unverified in cited sources)",
                    1,
                )

    if abstain:
        answer = (
            "I found related sources but could not verify citations against them. "
            "Please try a more specific product type or ask for a named formula from the books."
        )

    return ValidatedOutput(
        answer=answer.strip(),
        citations=verified_citations,
        quote_verified=quote_verified,
        abstain=abstain,
    )
