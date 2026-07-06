"""Parse Part A/B/C blocks with alternating ingredient name and wt% amount lines."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.parsers.ocr_amounts import normalize_ocr_amount_line
from app.formulation.schemas import IngredientLine

_ING_HEADER = re.compile(
    r"(?:inqredients?|insredients?|ingredients?|puredients?|raw materials|materials)\s*:?",
    re.I,
)
_WT_MARKER = re.compile(r"^\s*(?:Wt[%\$8]|wt%)\s*$", re.I)
_PART_LINE = re.compile(r"^([A-C])\s*:?\s+(.+)$")
_AMOUNT = re.compile(
    r"^\s*("
    r"to\s+100(?:\.\d+)?"
    r"|q\.?\s*s\.?"
    r"|\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?"
    r")\s*\.?\s*$",
    re.I,
)
_SKIP = re.compile(
    r"^(?:procedure|blending|mix\b|fragrances?,?\s*pigments?|formulation)\b",
    re.I,
)


def _parse_amount(raw: str) -> tuple[float | None, str]:
    raw = normalize_ocr_amount_line(raw)
    s = re.sub(r"\s+", "", raw.strip().lower())
    if re.match(r"^q\.?s\.?$", s) or s.startswith("qs"):
        return None, "qs"
    if s.startswith("to100"):
        return 100.0, "wt%"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "wt%"
    return None, "wt%"


def _clean_name(raw: str) -> str:
    return raw.strip().rstrip(",").strip()


def _is_name_line(stripped: str) -> bool:
    if not stripped or _AMOUNT.match(stripped) or _SKIP.match(stripped):
        return False
    return bool(re.match(r"^[A-Za-z]", stripped))


def _pair_names_amounts(
    names: list[str],
    amounts: list[tuple[float | None, str]],
    phase: str | None,
    seen: set[str],
) -> list[IngredientLine]:
    out: list[IngredientLine] = []
    n = min(len(names), len(amounts))
    for name, (amount, unit) in zip(names[:n], amounts[:n]):
        name = _clean_name(name)
        if len(name) < 2:
            continue
        norm = normalize_ingredient_name(name)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(
            IngredientLine(
                raw_name=name,
                normalized_name=norm,
                amount=amount,
                unit=unit,
                phase=phase,
            )
        )
    return out


def _leading_amounts(text: str) -> list[tuple[float | None, str]]:
    """Amount lines between wt% marker and ingredient header (roll-on layouts)."""
    out: list[tuple[float | None, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if _ING_HEADER.search(stripped):
            break
        if _AMOUNT.match(stripped):
            out.append(_parse_amount(stripped))
    return out


def _parse_phase_batches(
    lines: list[str],
    *,
    leading_pool: list[tuple[float | None, str]] | None = None,
) -> list[IngredientLine]:
    """Names listed under Part A/B/C, then amounts (possibly after a blank line)."""
    results: list[IngredientLine] = []
    seen: set[str] = set()
    phase: str | None = None
    pending_names: list[str] = []
    pending_amounts: list[tuple[float | None, str]] = []
    spare_amounts = list(leading_pool or [])

    def flush() -> None:
        nonlocal pending_names, pending_amounts, spare_amounts
        if pending_names and not pending_amounts and spare_amounts:
            take = spare_amounts[: len(pending_names)]
            spare_amounts = spare_amounts[len(take) :]
            pending_amounts = take
        if pending_names and pending_amounts:
            results.extend(_pair_names_amounts(pending_names, pending_amounts, phase, seen))
        pending_names = []
        pending_amounts = []

    for stripped in lines:
        if not stripped:
            if pending_names and pending_amounts:
                flush()
            continue
        part_match = _PART_LINE.match(stripped)
        if part_match:
            flush()
            phase = part_match.group(1).upper()
            rest = _clean_name(part_match.group(2))
            if rest and not _AMOUNT.match(rest):
                pending_names.append(rest)
            continue
        if _AMOUNT.match(stripped):
            pending_amounts.append(_parse_amount(stripped))
            continue
        if _is_name_line(stripped):
            if pending_amounts and pending_names:
                flush()
            pending_names.append(_clean_name(stripped))

    flush()
    return results


def _parse_sequential(lines: list[str]) -> list[IngredientLine]:
    results: list[IngredientLine] = []
    seen: set[str] = set()
    phase: str | None = None
    pending_name: str | None = None

    for stripped in lines:
        if not stripped or _SKIP.match(stripped):
            continue
        part_match = _PART_LINE.match(stripped)
        if part_match:
            phase = part_match.group(1).upper()
            rest = _clean_name(part_match.group(2))
            if rest and not _AMOUNT.match(rest):
                pending_name = rest
            continue
        if _AMOUNT.match(stripped):
            if not pending_name:
                continue
            amount, unit = _parse_amount(stripped)
            norm = normalize_ingredient_name(pending_name)
            if norm not in seen:
                seen.add(norm)
                results.append(
                    IngredientLine(
                        raw_name=pending_name,
                        normalized_name=norm,
                        amount=amount,
                        unit=unit,
                        phase=phase,
                    )
                )
            pending_name = None
            continue
        if _is_name_line(stripped):
            if pending_name and not pending_name.endswith(","):
                pending_name = _clean_name(stripped)
            else:
                pending_name = _clean_name(f"{pending_name or ''} {stripped}")

    return results


def _parse_materials_interleaved(lines: list[str]) -> list[IngredientLine]:
    """Materials: header with name / Wt% / amount per ingredient (roll-on suspensions)."""
    results: list[IngredientLine] = []
    seen: set[str] = set()
    pending_name: str | None = None

    for stripped in lines:
        if not stripped or _SKIP.match(stripped):
            continue
        if _WT_MARKER.match(stripped):
            continue
        if _AMOUNT.match(stripped):
            if not pending_name:
                continue
            amount, unit = _parse_amount(stripped)
            norm = normalize_ingredient_name(pending_name)
            dedup_key = pending_name.lower().strip()
            if dedup_key not in seen:
                seen.add(dedup_key)
                results.append(
                    IngredientLine(
                        raw_name=pending_name,
                        normalized_name=norm,
                        amount=amount,
                        unit=unit,
                    )
                )
            pending_name = None
            continue
        if _is_name_line(stripped):
            pending_name = _clean_name(stripped)

    return results


def parse_phase_inline_wt(text: str) -> list[IngredientLine]:
    if not _ING_HEADER.search(text):
        return []
    if not re.search(r"wt\s*[%\$8]", text, re.I):
        return []
    body_lines: list[str] = []
    in_block = False
    materials_mode = bool(re.search(r"\bmaterials\s*:?", text, re.I))
    if not materials_mode and not re.search(r"^[A-C]\s*:?\s+\S", text, re.MULTILINE | re.I):
        return []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if _ING_HEADER.search(stripped) or _WT_MARKER.match(stripped):
            in_block = True
            continue
        if in_block:
            if re.match(r"^(?:Procedure|Blending)\b", stripped, re.I):
                break
            body_lines.append(stripped)

    if materials_mode:
        materials = _parse_materials_interleaved(body_lines)
        if len(materials) >= 4:
            return materials

    leading = _leading_amounts(text)
    batch = _parse_phase_batches(body_lines, leading_pool=leading)
    if len(batch) >= 6:
        return batch
    sequential = _parse_sequential(body_lines)
    best = batch if len(batch) > len(sequential) else sequential
    if len(best) >= 4:
        return best
    if materials_mode:
        materials = _parse_materials_interleaved(body_lines)
        if len(materials) >= 4:
            return materials
    return []
