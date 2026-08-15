from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.formulation.schemas import FormulationRecord


@dataclass(slots=True)
class FormulationSearchFilters:
    product_types: list[str] | None = None
    product_type: str | None = None
    ingredient: str | None = None
    name_contains: str | None = None
    doc_id: str | None = None
    banned_ingredients: list[str] | None = None
    preferred_ingredients: list[str] | None = None
    limit: int = 20

    def resolved_product_types(self) -> list[str]:
        types = list(self.product_types or [])
        if self.product_type and self.product_type not in types:
            types.append(self.product_type)
        return types


@runtime_checkable
class FormulationStore(Protocol):
    def init_db(self) -> None: ...

    def upsert(self, record: FormulationRecord) -> None: ...

    def get(self, formulation_id: str) -> FormulationRecord | None: ...

    def delete(self, formulation_id: str) -> bool: ...

    def search(self, filters: FormulationSearchFilters) -> list[FormulationRecord]: ...

    def count(self) -> int: ...

    def clear_all(self) -> int: ...

    def backend_name(self) -> str: ...
