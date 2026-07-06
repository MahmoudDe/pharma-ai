"""Narrated end-to-end walkthrough of the KBS — one command for a live demo.

Picks real records straight from the store, validates them live, and prints
what the knowledge rules found: a clean record that verifies, a broken one
that gets flagged with the exact defect, and a good formula whose only
problem is an OCR-garbled title. Ends with the calibrated accuracy numbers.

    python -m scripts.kbs_demo
"""
from __future__ import annotations

import sys

from app.formulation.store import get_store
from app.formulation.store_base import FormulationSearchFilters
from app.kbs.registry import get_rules
from app.kbs.service import validate_record


BOLD, DIM, GREEN, AMBER, RED, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)
STATUS_COLOR = {"verified": GREEN, "review": AMBER, "low_precision": RED}


def _rule(char: str = "─") -> str:
    return DIM + char * 72 + RESET


def _print_report(record, report) -> None:
    color = STATUS_COLOR.get(report.status, "")
    print(f"{BOLD}{record.name[:60]!r}{RESET}")
    print(
        f"  extraction: {report.extraction_method}  "
        f"→  precision {BOLD}{report.precision_score:.2f}{RESET}  "
        f"[{color}{report.status.upper()}{RESET}]  "
        f"(store confidence {record.confidence:.2f} → rescored {report.rescored_confidence})"
    )
    findings = [f for f in report.findings if f.family != "regulatory"]
    if not findings:
        print(f"  {GREEN}✓ every knowledge rule passed — amounts verified against the source{RESET}")
    for f in findings[:6]:
        mark = {"error": f"{RED}✗", "warning": f"{AMBER}!", "info": f"{DIM}·"}.get(f.severity, " ")
        print(f"  {mark} [{f.severity}] {f.message[:78]}{RESET}")
    if report.compliance_status != "skipped":
        print(f"  {DIM}regulatory compliance: {report.compliance_status}{RESET}")
    print()


def _pick(records, predicate, limit=1):
    out = []
    for r in records:
        rep = validate_record(r, markets=[], persist=False)
        if predicate(r, rep):
            out.append((r, rep))
            if len(out) >= limit:
                break
    return out


def main() -> int:
    store = get_store()
    records = store.search(FormulationSearchFilters(limit=100000))
    if not records:
        print("No formulations in the store — run the ingest first.")
        return 1

    print(_rule("━"))
    print(f"{BOLD}  KBS — Formulation Precision Validation · live demo{RESET}")
    print(f"{DIM}  {len(records)} formulations in the store · {len(get_rules())} knowledge rules{RESET}")
    print(_rule("━"))

    print(f"\n{BOLD}1) A clean extraction — every rule passes, badge is VERIFIED{RESET}\n")
    for r, rep in _pick(records, lambda r, x: x.status == "verified"
                        and not [f for f in x.findings if f.family != "regulatory"]):
        _print_report(r, rep)

    print(f"{BOLD}2) A broken extraction — the KBS names the exact defect{RESET}\n")
    for r, rep in _pick(records, lambda r, x: any(
            f.rule_id == "consistency.percent-sum" and f.severity == "error" for f in x.findings)):
        _print_report(r, rep)

    print(f"{BOLD}3) Good amounts, garbled title — flagged WITHOUT losing the badge{RESET}\n")
    for r, rep in _pick(records, lambda r, x: x.status == "verified" and any(
            f.rule_id == "completeness.name-quality" for f in x.findings)):
        _print_report(r, rep)

    print(f"{BOLD}4) An implausible level the extraction got right — warning, not error{RESET}\n")
    printed = _pick(records, lambda r, x: x.status == "verified" and any(
        f.rule_id == "ranges.ingredient-range" and f.severity == "warning"
        and "matches the source" in f.message for f in x.findings), limit=1)
    if not printed:  # fall back to any verified record carrying a range warning
        printed = _pick(records, lambda r, x: x.status == "verified" and any(
            f.rule_id == "ranges.ingredient-range" and f.severity == "warning" for f in x.findings), limit=1)
    for r, rep in printed:
        _print_report(r, rep)

    print(_rule())
    print(f"{BOLD}Accuracy (verified badge vs. a hand-labeled golden set){RESET}")
    try:
        from scripts.eval_kbs import evaluate

        m = evaluate()
        print(
            f"  {GREEN}precision {m['precision']}  recall {m['recall']}  f1 {m['f1']}{RESET}  "
            f"over {m['n']} labeled records "
            f"(tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']})"
        )
        print(f"  {DIM}locked in CI by tests/test_kbs_calibration.py (floors at 0.90){RESET}")
    except Exception as exc:  # noqa: BLE001
        print(f"  (golden-set eval unavailable: {exc})")
    print(_rule())
    return 0


if __name__ == "__main__":
    sys.exit(main())
