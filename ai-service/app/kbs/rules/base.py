from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.kbs.facts import FactContext
from app.kbs.schemas import RuleFamily, RuleFinding


@runtime_checkable
class Rule(Protocol):
    rule_id: str
    family: RuleFamily

    def check(self, facts: FactContext) -> list[RuleFinding]: ...
