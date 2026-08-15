from __future__ import annotations

import json
import sys
from pathlib import Path

from app.formulation.schemas import FormulationRecord
from app.kbs.service import validate_record


GOLDEN_PATH = Path(__file__).resolve().parent / "golden_kbs.json"


def evaluate() -> dict:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    tp = fp = fn = tn = 0
    misses: list[str] = []
    for entry in data["entries"]:
        record = FormulationRecord.model_validate(entry["record"])
        report = validate_record(record, markets=[], persist=False)
        predicted_good = report.status == "verified"
        actually_good = entry["label"] == "good"
        if predicted_good and actually_good:
            tp += 1
        elif predicted_good and not actually_good:
            fp += 1
            misses.append(f"FP {record.name[:50]!r} score={report.precision_score}")
        elif not predicted_good and actually_good:
            fn += 1
            misses.append(
                f"FN {record.name[:50]!r} score={report.precision_score} "
                f"errors={[f.rule_id for f in report.errors()][:3]}"
            )
        else:
            tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": tp + fp + fn + tn,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "misses": misses,
    }


def main() -> int:
    metrics = evaluate()
    print(f"golden set: {metrics['n']} records")
    print(
        f"verified badge — precision: {metrics['precision']} "
        f"recall: {metrics['recall']} f1: {metrics['f1']} "
        f"(tp={metrics['tp']} fp={metrics['fp']} fn={metrics['fn']} tn={metrics['tn']})"
    )
    for miss in metrics["misses"]:
        print(" ", miss)
    return 0


if __name__ == "__main__":
    sys.exit(main())
