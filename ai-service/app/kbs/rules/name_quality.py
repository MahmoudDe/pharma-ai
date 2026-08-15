from __future__ import annotations

import re

from app.kbs.facts import FactContext
from app.kbs.schemas import RuleFinding

THRESHOLD = 1

_VOWELS = set("aeiouy")  # 'y' counts so 'dry', 'skky' aren't false-flagged
_TOKEN = re.compile(r"[A-Za-z]+")
_CONSONANT_RUN = re.compile(r"[bcdfghjklmnpqrstvwxz]{5,}", re.I)
# 'q' not followed by 'u' is a classic OCR error ('Hiqh', 'Anti-Aqina'), but a
# 'q' next to a digit is usually a trade code ('AQ55S'), so exclude that.
_Q_NOT_U = re.compile(r"q(?![u\s\d]|$)", re.I)
_MIDWORD_CAP = re.compile(r"[a-z][A-Z][a-z]")
_AMOUNT_TAIL = re.compile(r"\s\d+\s+\d+\s*$")
_UNIT_TOKEN = re.compile(r"^(?:wt\s*[%$8]?|w/w|q\.?\s*s\.?|\d+(?:\.\d+)?)$", re.I)


def _vowelless_token(tok: str) -> bool:
    # a real word with no vowel is an OCR artifact ('Drv'), but a short
    # all-caps token is a legitimate acronym ('BSC', 'SCL', 'CDM')
    if len(tok) < 3 or tok.isupper():
        return False
    return not (set(tok.lower()) & _VOWELS)


def score_name(name: str) -> tuple[int, list[str], str | None]:
    """Return (suspicion_points, reasons, cleaned_suggestion)."""
    stripped = name.strip()
    lower = stripped.lower()
    points = 0
    reasons: list[str] = []
    suggestion: str | None = None

    if "|" in stripped:
        points += 3
        reasons.append("contains a table-column separator")
        head = stripped.split("|", 1)[0].strip()
        if len(head) >= 4:
            suggestion = head

    if _AMOUNT_TAIL.search(stripped):
        points += 2
        reasons.append("ends with a stray amount cell")
        if suggestion is None:
            trimmed = _AMOUNT_TAIL.sub("", stripped).strip()
            if len(trimmed) >= 4:
                suggestion = trimmed

    if _UNIT_TOKEN.match(lower):
        points += 3
        reasons.append("is a stray unit or number rather than a name")

    non_space = [c for c in stripped if not c.isspace()]
    if len(stripped) >= 3 and non_space:
        alpha_ratio = sum(c.isalpha() for c in non_space) / len(non_space)
        if alpha_ratio < 0.55:
            points += 2
            reasons.append("is mostly non-letters")

    tokens = _TOKEN.findall(stripped)
    if any(len(t) >= 4 and _CONSONANT_RUN.search(t) for t in tokens):
        points += 1
        reasons.append("has an improbable consonant run")
    if any(_vowelless_token(t) for t in tokens):
        points += 1
        reasons.append("has a word with no vowels")
    if _Q_NOT_U.search(stripped):
        points += 1
        reasons.append("has 'q' not followed by 'u' (common OCR error)")
    if _MIDWORD_CAP.search(stripped):
        points += 1
        reasons.append("has a capital letter mid-word")

    return points, reasons, suggestion


class GarbledNameRule:
    rule_id = "completeness.name-quality"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        name = facts.record.name
        if not name.strip():
            return []  # completeness.has-name already reports an empty name
        points, reasons, suggestion = score_name(name)
        if points < THRESHOLD:
            return []
        message = "Formulation name looks OCR-garbled (" + "; ".join(reasons) + ")"
        if suggestion:
            message += f" — likely meant '{suggestion}'"
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="info",
                message=message,
                field="name",
                observed=name.strip()[:80],
                expected=suggestion,
            )
        ]


def build_rules() -> list:
    return [GarbledNameRule()]
