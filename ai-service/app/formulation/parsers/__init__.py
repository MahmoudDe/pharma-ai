from app.formulation.parsers.column_wt import parse_column_wt_layout
from app.formulation.parsers.inline_wt import parse_inline_wt_rows
from app.formulation.parsers.part_function import parse_part_function_layout
from app.formulation.parsers.ingredient_list import parse_ingredient_list
from app.formulation.parsers.percent_table import parse_percent_table
from app.formulation.parsers.procedure import parse_procedure
from app.formulation.parsers.validate import confidence_from_ingredients, filter_ingredient_lines
from app.formulation.parsers.wtg_table import parse_wtg_table

__all__ = [
    "parse_percent_table",
    "parse_wtg_table",
    "parse_ingredient_list",
    "parse_procedure",
    "parse_formula_block",
]


def parse_formula_block(text: str) -> tuple[list, str, float]:
    """Return (ingredients, method, confidence)."""
    from app.formulation.schemas import IngredientLine

    for parser, method, base_conf in (
        (parse_part_function_layout, "part_function", 0.87),
        (parse_column_wt_layout, "column_wt", 0.88),
        (parse_inline_wt_rows, "inline_wt", 0.86),
        (parse_percent_table, "table", 0.85),
        (parse_wtg_table, "wtg", 0.8),
        (parse_ingredient_list, "list", 0.55),
    ):
        raw_lines: list[IngredientLine] = parser(text)
        lines = filter_ingredient_lines(raw_lines)
        if len(lines) >= 2:
            return lines, method, confidence_from_ingredients(lines, base_conf)
    return [], "regex", 0.0
