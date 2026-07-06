from app.formulation.parsers.column_wt import parse_column_wt_layout
from app.formulation.parsers.part_labeled_wt import parse_part_labeled_wt
from app.formulation.parsers.inline_wt import parse_inline_wt_rows
import re
from app.formulation.parsers.japan_prescription import parse_japan_prescription
from app.formulation.parsers.part_function import parse_part_function_layout
from app.formulation.parsers.phase_inline_wt import parse_phase_inline_wt
from app.formulation.parsers.ingredient_list import parse_ingredient_list
from app.formulation.parsers.numbered_stage import parse_numbered_stage
from app.formulation.parsers.ocr_amounts import repair_spaced_decimals
from app.formulation.parsers.percent_table import parse_percent_table
from app.formulation.parsers.phase_column import parse_phase_column
from app.formulation.parsers.procedure import parse_procedure
from app.formulation.parsers.reference_filter import is_reference_table_block
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

    if is_reference_table_block(text):
        return [], "regex", 0.0

    text = repair_spaced_decimals(text)

    _MIN_WEAK_INGREDIENTS = {
        "list": 3,
        "table": 4,
        "wtg": 3,
        "column_wt": 3,
        "inline_wt": 3,
    }
    _MIN_METHOD_INGREDIENTS = {"phase_inline": 4, "part_labeled": 4}
    _CONTINUED_RX = re.compile(r"\(continued\)", re.I)

    for parser, method, base_conf in (
        (parse_japan_prescription, "japan_rx", 0.9),
        (parse_phase_inline_wt, "phase_inline", 0.88),
        (parse_part_labeled_wt, "part_labeled", 0.89),
        (parse_part_function_layout, "part_function", 0.87),
        (parse_column_wt_layout, "column_wt", 0.88),
        (parse_numbered_stage, "numbered_stage", 0.9),
        (parse_phase_column, "phase_column", 0.87),
        (parse_inline_wt_rows, "inline_wt", 0.86),
        (parse_percent_table, "table", 0.85),
        (parse_wtg_table, "wtg", 0.8),
        (parse_ingredient_list, "list", 0.55),
    ):
        raw_lines: list[IngredientLine] = parser(text)
        lines = filter_ingredient_lines(raw_lines)
        if len(lines) >= 2:
            min_weak = _MIN_WEAK_INGREDIENTS.get(method)
            if min_weak is not None and len(lines) < min_weak:
                continue
            min_method = _MIN_METHOD_INGREDIENTS.get(method)
            if min_method is not None and len(lines) < min_method:
                continue
            if method == "japan_rx" and _CONTINUED_RX.search(text) and len(lines) < 4:
                continue
            return lines, method, confidence_from_ingredients(lines, base_conf)
    return [], "regex", 0.0
