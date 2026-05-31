"""Extract manufacturing procedure steps from formula block text."""
from __future__ import annotations

import re

_PROCEDURE_HEADER = re.compile(r"^\s*Procedure\s*:", re.I | re.MULTILINE)
_NUMBERED_STEP = re.compile(r"^\s*(\d+)[.)]\s+(.+)$", re.MULTILINE)


def parse_procedure(text: str, *, max_steps: int = 12) -> list[str]:
    if not text or not text.strip():
        return []

    steps: list[str] = []
    proc_match = _PROCEDURE_HEADER.search(text)
    if proc_match:
        tail = text[proc_match.end() :]
        for match in _NUMBERED_STEP.finditer(tail):
            step = match.group(2).strip()
            if len(step) >= 8:
                steps.append(step)
            if len(steps) >= max_steps:
                break
        if steps:
            return steps

    for match in _NUMBERED_STEP.finditer(text):
        step = match.group(2).strip()
        if len(step) >= 12 and any(
            kw in step.lower() for kw in ("heat", "mix", "add", "stir", "cool", "blend", "dissolve")
        ):
            steps.append(step)
        if len(steps) >= max_steps:
            break
    return steps
