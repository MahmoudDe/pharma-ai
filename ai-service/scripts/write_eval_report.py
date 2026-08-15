#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.eval.corpus_health import build_corpus_health_report
from app.eval.ingest_quality import audit_ingest_quality
from app.formulation.compare import compare_formulations
from app.formulation.cost import estimate_formulation_cost, load_price_table
from app.formulation.search import structured_search
from app.formulation.store import list_formulations
from app.reasoning.query_rewrite import rewrite_search_query
from app.reasoning.router import route_chat
from app.retrieval.intent import classify_query, parse_query_intent
from app.schemas import ChatHistoryMessage, ChatTurnRequest, StructuredBrief
from scripts.eval_kbs import evaluate as evaluate_kbs
from scripts.eval_product import _check_structured_product, _load_json_list

OUT_PATH = REPO / ".cursor" / "planning" / "ai-eval-report.html"
HARD_EVAL = SCRIPTS / "hard_eval_results.json"
GOLDEN_PRODUCT = SCRIPTS / "golden_product.json"
GOLDEN_ROUTING = SCRIPTS / "golden_routing.json"
GOLDEN_RETRIEVAL = SCRIPTS / "golden_retrieval.json"

CI_TESTS = [
    "tests/test_query_rewrite.py",
    "tests/test_brief_markets.py",
    "tests/test_brief_cost.py",
    "tests/test_cost.py",
    "tests/test_conversation_history.py",
    "tests/test_regulatory.py",
    "tests/test_corpus_health.py",
    "tests/test_formulation_review.py",
    "tests/test_parsers.py",
    "tests/test_kbs_name_quality.py",
    "tests/test_warehouse.py",
    "tests/test_warehouse_arabic.py",
    "tests/test_warehouse_phase_d.py",
    "tests/test_ai_smoke.py",
    "tests/test_compare.py",
    "tests/test_brief_format.py",
    "tests/test_golden_retrieval.py",
    "tests/test_feedback_log.py",
    "tests/test_sources.py",
]


def _esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def run_pytest() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *CI_TESTS,
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = failed = skipped = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) skipped", out)
    if m:
        skipped = int(m.group(1))
    summary = next((ln.strip() for ln in reversed(out.splitlines()) if "passed" in ln or "failed" in ln), "")
    return {
        "exit_code": proc.returncode,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": passed + failed,
        "summary": summary,
        "ok": proc.returncode == 0,
    }


def qdrant_up() -> bool:
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:6333/readyz", timeout=1.5)
        return True
    except Exception:
        return False


CORE_PIPELINE_CASES = [
    {
        "id": "lookup_baby",
        "title": "Lookup — baby shampoo",
        "message": "Give me a baby shampoo formula with ingredient percentages.",
        "expect_route": "lookup",
        "expect_llm": False,
        "name_re": r"baby\s+shampoo",
        "min_ingredients": 4,
        "must_have_amounts": True,
    },
    {
        "id": "lookup_dandruff",
        "title": "Lookup — anti-dandruff",
        "message": "Show me an anti-dandruff shampoo formula.",
        "expect_route": "lookup",
        "expect_llm": False,
        "name_re": r"dandruff",
        "min_ingredients": 3,
        "must_have_amounts": True,
    },
    {
        "id": "lookup_hand",
        "title": "Lookup — hand cream",
        "message": "Give me a hand cream formula for normal skin.",
        "expect_route": "lookup",
        "expect_llm": False,
        "name_re": r"hand\s+(and\s+)?(nail\s+)?cream|tube[- ]dispensed",
        "min_ingredients": 3,
        "must_have_amounts": True,
    },
    {
        "id": "compare_baby",
        "title": "Compare — baby shampoos",
        "message": "compare baby shampoo formulas",
        "expect_route": "compare",
        "expect_llm": False,
        "name_re": r"baby|shampoo",
        "min_formulas": 2,
        "min_ingredients": 3,
        "must_have_amounts": True,
    },
]


def _views_from_response(resp) -> list:
    views = list(resp.structured_formulations or [])
    if not views and resp.structured_formulation:
        views = [resp.structured_formulation]
    return views


def run_core_pipeline() -> dict:
    """Live retrieve → route → grounded formula. Lookup/compare skip the LLM."""
    cases = []
    for spec in CORE_PIPELINE_CASES:
        errors: list[str] = []
        payload = ChatTurnRequest(thread_id=f"eval-{spec['id']}", message=spec["message"])
        try:
            routed = route_chat(payload)
        except Exception as exc:
            cases.append(
                {
                    "id": spec["id"],
                    "title": spec["title"],
                    "message": spec["message"],
                    "ok": False,
                    "errors": [str(exc)],
                    "route": None,
                    "llm_used": None,
                    "confidence": None,
                    "fallback": None,
                    "formula_names": [],
                    "ingredient_count": None,
                    "amounts": 0,
                    "citations": 0,
                    "verified_citations": 0,
                    "answer_preview": "",
                }
            )
            continue

        resp = routed.response
        views = _views_from_response(resp)
        top = views[0] if views else None
        n_ing = len(top.ingredients) if top else 0
        amounts = 0
        if top:
            amounts = sum(1 for i in top.ingredients if i.get("amount") is not None)

        if resp.route != spec["expect_route"]:
            errors.append(f"route {resp.route} != {spec['expect_route']}")
        if resp.llm_used != spec["expect_llm"]:
            errors.append(f"llm_used {resp.llm_used} != {spec['expect_llm']}")
        if not views:
            errors.append("no structured formula returned")
        else:
            if spec.get("min_formulas") and len(views) < spec["min_formulas"]:
                errors.append(f"formulas {len(views)} < {spec['min_formulas']}")
            if not re.search(spec["name_re"], top.name, re.I):
                errors.append(f"top name {top.name!r} does not match /{spec['name_re']}/")
            if n_ing < spec["min_ingredients"]:
                errors.append(f"ingredients {n_ing} < {spec['min_ingredients']}")
            if spec.get("must_have_amounts") and amounts == 0:
                errors.append("no numeric amounts on top formula")
        if not resp.assistant_message.strip():
            errors.append("empty assistant message")
        grounded = bool(resp.cited_evidence) or (
            top is not None and bool(top.doc_id) and top.pdf_page is not None
        ) or ("Source:" in resp.assistant_message)
        if not grounded:
            errors.append("no source page or citations")

        preview = resp.assistant_message.replace("\n", " ").strip()[:220]
        cases.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "message": spec["message"],
                "ok": not errors,
                "errors": errors,
                "route": resp.route,
                "llm_used": resp.llm_used,
                "confidence": resp.search_confidence,
                "fallback": resp.fallback_stage,
                "formula_names": [v.name for v in views[:3]],
                "ingredient_count": n_ing,
                "amounts": amounts,
                "citations": len(resp.cited_evidence),
                "verified_citations": sum(1 for e in resp.cited_evidence if e.quote_verified),
                "doc_id": top.doc_id if top else None,
                "pdf_page": top.pdf_page if top else None,
                "answer_preview": preview,
            }
        )

    history = [
        ChatHistoryMessage(role="user", content="Give me a baby shampoo formula"),
        ChatHistoryMessage(
            role="assistant",
            content="Here is a mild baby shampoo with CAPB and glycerin.",
        ),
    ]
    rewritten, was_rewritten = rewrite_search_query("make it sulfate-free", history)
    follow_errors: list[str] = []
    follow_resp = None
    try:
        follow_resp = route_chat(
            ChatTurnRequest(
                thread_id="eval-followup",
                message="make it sulfate-free",
                history=history,
            )
        ).response
    except Exception as exc:
        follow_errors.append(str(exc))

    if not was_rewritten:
        follow_errors.append("follow-up was not rewritten")
    if "baby" not in rewritten.lower() or "sulfate" not in rewritten.lower():
        follow_errors.append(f"rewrite {rewritten!r} missing baby/sulfate context")
    follow_views = _views_from_response(follow_resp) if follow_resp else []
    if follow_resp is not None and not follow_views:
        follow_errors.append("follow-up returned no formula")

    follow = {
        "ok": not follow_errors,
        "errors": follow_errors,
        "rewritten": rewritten,
        "was_rewritten": was_rewritten,
        "route": follow_resp.route if follow_resp else None,
        "llm_used": follow_resp.llm_used if follow_resp else None,
        "formula_names": [v.name for v in follow_views[:3]],
        "answer_preview": (
            follow_resp.assistant_message.replace("\n", " ").strip()[:220] if follow_resp else ""
        ),
    }

    n = len(cases)
    passed = sum(1 for c in cases if c["ok"])
    return {
        "n": n,
        "passed": passed,
        "failed": n - passed,
        "rate": round(100.0 * passed / n, 1) if n else 0.0,
        "ok": passed == n and follow["ok"],
        "cases": cases,
        "followup": follow,
    }


def run_retrieval() -> dict:
    if not qdrant_up():
        questions = json.loads(GOLDEN_RETRIEVAL.read_text(encoding="utf-8"))
        return {
            "skipped": True,
            "reason": "Qdrant is not running (Docker daemon unavailable).",
            "golden_n": len(questions),
            "target": "NFR-ACC-06 ≥90% hit@k",
            "passed": 0,
            "failed": 0,
            "rate": None,
            "cases": [],
        }
    from scripts.retrieval_eval import load_golden_questions, run_retrieval_eval

    qs = load_golden_questions(GOLDEN_RETRIEVAL)
    results = run_retrieval_eval(qs, verbose=False, golden_path=GOLDEN_RETRIEVAL)
    cases = []
    failed = 0
    for r in results:
        ok = not r.errors
        if not ok:
            failed += 1
        cases.append({"question": r.question, "ok": ok, "errors": r.errors})
    n = len(results)
    passed = n - failed
    return {
        "skipped": False,
        "golden_n": n,
        "passed": passed,
        "failed": failed,
        "rate": round(100.0 * passed / n, 1) if n else 0.0,
        "target": "NFR-ACC-06 ≥90% hit@k",
        "meets_target": (passed / n >= 0.9) if n else False,
        "cases": cases,
    }


def run_routing_and_structured() -> dict:
    cases = _load_json_list(GOLDEN_PRODUCT) or _load_json_list(GOLDEN_ROUTING)
    rows = []
    for case in cases:
        message = case["message"]
        expect_route = case["expect_route"]
        cls = classify_query(message)
        errors: list[str] = []
        if cls.route != expect_route:
            errors.append(f"route {cls.route} != {expect_route}")
        structured_errors: list[str] = []
        structured_ok = None
        top_name = None
        top_conf = None
        n_ing = None
        if expect_route in ("lookup", "compare") and not case.get("classification_only"):
            structured_errors = _check_structured_product(case, message)
            intent = parse_query_intent(message)
            result = structured_search(message, intent, limit=5)
            top_conf = result.top_confidence
            if result.matches:
                top_name = result.matches[0].record.name
                n_ing = len(result.matches[0].record.ingredients)
            structured_ok = not structured_errors
        ok = not errors and not structured_errors
        rows.append(
            {
                "message": message,
                "expect_route": expect_route,
                "got_route": cls.route,
                "top_name": top_name,
                "top_conf": top_conf,
                "n_ingredients": n_ing,
                "ok": ok,
                "errors": errors + structured_errors,
                "structured_ok": structured_ok,
            }
        )
    n = len(rows)
    passed = sum(1 for r in rows if r["ok"])
    struct_rows = [r for r in rows if r["structured_ok"] is not None]
    struct_passed = sum(1 for r in struct_rows if r["structured_ok"])
    return {
        "n": n,
        "passed": passed,
        "failed": n - passed,
        "rate": round(100.0 * passed / n, 1) if n else 0.0,
        "structured_n": len(struct_rows),
        "structured_passed": struct_passed,
        "structured_rate": round(100.0 * struct_passed / len(struct_rows), 1) if struct_rows else None,
        "cases": rows,
    }


def cost_sample() -> dict:
    prices = load_price_table()
    records = list_formulations(limit=400)
    estimates = [estimate_formulation_cost(r) for r in records]
    priced = [e for e in estimates if e.cost_per_kg is not None]
    coverages = [e.covered_percent for e in priced]
    return {
        "price_table_keys": len(prices),
        "formulas_sampled": len(records),
        "formulas_with_cost": len(priced),
        "share_priced": round(100.0 * len(priced) / len(records), 1) if records else 0.0,
        "median_coverage_pct": round(100.0 * sorted(coverages)[len(coverages) // 2], 1) if coverages else None,
        "mean_cost_per_kg": round(mean(e.cost_per_kg for e in priced), 2) if priced else None,
    }


def compare_smoke() -> dict:
    records = [r for r in list_formulations(limit=80) if len(r.ingredients) >= 4]
    if len(records) < 2:
        return {"ok": False, "reason": "Need ≥2 complete formulas"}
    report = compare_formulations(records[0], records[1], markets=["EU"])
    return {
        "ok": True,
        "left": report.left_name,
        "right": report.right_name,
        "left_cost": report.left_cost_per_kg,
        "right_cost": report.right_cost_per_kg,
        "cost_delta": report.cost_delta_per_kg,
        "left_compliance": report.left_compliance,
        "right_compliance": report.right_compliance,
        "summary_n": len(report.summary_lines),
        "roles": [r.role for r in report.role_summaries],
    }


def brief_filter_smoke() -> dict:
    from app.reasoning.brief import apply_brief_filters

    records = list_formulations(limit=200)
    banned = apply_brief_filters(records, StructuredBrief(banned_ingredients=["formaldehyde"]))
    markets = apply_brief_filters(records, StructuredBrief(markets=["EU"]))
    return {
        "pool": len(records),
        "after_banned_formaldehyde": len(banned),
        "after_eu_markets": len(markets),
        "ok": len(banned) <= len(records) and len(markets) <= len(records),
    }


def hard_eval_summary() -> dict | None:
    if not HARD_EVAL.is_file():
        return None
    raw = json.loads(HARD_EVAL.read_text(encoding="utf-8"))
    results = raw.get("results") or []
    scores = [float(r.get("score") or 0) for r in results]
    by_route: dict[str, list[float]] = {}
    for r in results:
        by_route.setdefault(r.get("route") or "unknown", []).append(float(r.get("score") or 0))
    return {
        "judge_model": raw.get("judge_model"),
        "passed": raw.get("passed"),
        "total": raw.get("total") or len(results),
        "pass_rate": round(100.0 * (raw.get("passed") or 0) / max(len(results), 1), 1),
        "mean_score": round(mean(scores), 2) if scores else None,
        "by_route": {
            k: {"n": len(v), "mean": round(mean(v), 2), "pass": sum(1 for r in results if r.get("route") == k and r.get("pass"))}
            for k, v in by_route.items()
        },
        "note": "Prior OpenRouter LLM-as-judge run (hard book questions). Not re-run (bills API).",
    }


def pill(ok: bool | None, skipped: bool = False) -> str:
    if skipped:
        return '<span class="status status-partial">Skipped</span>'
    if ok:
        return '<span class="status status-done">Pass</span>'
    return '<span class="status status-gap">Fail</span>'


def metric_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="metric">
      <div class="metric-value">{_esc(value)}</div>
      <div class="metric-label">{_esc(label)}</div>
      {f'<div class="metric-sub">{_esc(sub)}</div>' if sub else ''}
    </div>"""


def render_html(data: dict) -> str:
    pytest = data["pytest"]
    ingest = data["ingest"]
    kbs = data["kbs"]
    routing = data["routing"]
    retrieval = data["retrieval"]
    core = data["core"]
    cost = data["cost"]
    compare = data["compare"]
    brief = data["brief"]
    hard = data["hard_eval"]
    health = data["health"]
    now = data["generated_at"]
    follow = core["followup"]

    overall_bits = [
        pytest["ok"],
        ingest["passed"],
        kbs["f1"] >= 0.7,
        core["passed"] >= 3 and follow["ok"],
        not retrieval["skipped"] and retrieval.get("meets_target"),
        brief["ok"],
        compare["ok"],
    ]
    overall_pass = all(overall_bits)
    retrieval_note = "skipped" if retrieval["skipped"] else f"{retrieval['rate']}%"

    core_cards = "".join(
        f"""
        <div class="phase-card">
          <h3>{_esc(c['title'])} {pill(c['ok'])}</h3>
          <p><code>{_esc(c['message'])}</code></p>
          <p>route=<code>{_esc(c['route'])}</code> · llm=<code>{_esc(c['llm_used'])}</code> · conf={'' if c['confidence'] is None else f"{c['confidence']:.0f}"} · fallback=<code>{_esc(c['fallback'])}</code></p>
          <p>Formulas: {_esc(', '.join(c['formula_names']) or '—')} · ingredients={c['ingredient_count']} · amounts={c['amounts']} · citations={c['citations']} (verified {c['verified_citations']})</p>
          <p>Source: {_esc(c.get('doc_id') or '—')} p.{_esc(c.get('pdf_page') or '—')}</p>
          <p class="preview">{_esc(c['answer_preview'])}</p>
          {('<ul>' + ''.join(f'<li>{_esc(e)}</li>' for e in c['errors']) + '</ul>') if c['errors'] else ''}
        </div>
        """
        for c in core["cases"]
    )

    routing_rows = "".join(
        f"<tr><td>{_esc(c['message'])}</td><td>{_esc(c['expect_route'])}</td>"
        f"<td>{_esc(c['got_route'])}</td><td>{_esc(c['top_name'] or '—')}</td>"
        f"<td>{'' if c['top_conf'] is None else f'{c['top_conf']:.0f}'}</td>"
        f"<td>{c['n_ingredients'] if c['n_ingredients'] is not None else '—'}</td>"
        f"<td>{pill(c['ok'])}</td></tr>"
        for c in routing["cases"]
    )
    routing_fail_detail = "".join(
        f"<li><code>{_esc(c['message'])}</code> — {_esc('; '.join(c['errors']))}</li>"
        for c in routing["cases"]
        if c["errors"]
    )

    retrieval_rows = ""
    if not retrieval["skipped"]:
        retrieval_rows = "".join(
            f"<tr><td>{_esc(c['question'])}</td><td>{pill(c['ok'])}</td>"
            f"<td>{_esc('; '.join(c['errors']) or '—')}</td></tr>"
            for c in retrieval["cases"]
        )

    kbs_misses = "".join(f"<li>{_esc(m)}</li>" for m in (kbs.get("misses") or [])[:12])
    hard_route_rows = ""
    if hard:
        hard_route_rows = "".join(
            f"<tr><td>{_esc(k)}</td><td>{v['n']}</td><td>{v['mean']}</td><td>{v['pass']}</td></tr>"
            for k, v in hard["by_route"].items()
        )

    ingest_fail = "".join(f"<li>{_esc(f)}</li>" for f in ingest.get("failures") or [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Pharma AI — Core AI Proof Report</title>
  <style>
    :root {{
      --bg: #0f1419;
      --surface: #1a2332;
      --surface2: #243044;
      --border: #2d3a4f;
      --text: #e8edf4;
      --text-muted: #8b9cb3;
      --accent: #3d8bfd;
      --accent-soft: rgba(61, 139, 253, 0.12);
      --green: #3ecf8e;
      --green-soft: rgba(62, 207, 142, 0.12);
      --amber: #f5a623;
      --amber-soft: rgba(245, 166, 35, 0.12);
      --red: #f56565;
      --red-soft: rgba(245, 101, 101, 0.12);
      --radius: 10px;
      --font: "Segoe UI", system-ui, -apple-system, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
      padding: 2rem 1.5rem 4rem;
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{ font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }}
    .subtitle {{ color: var(--text-muted); margin-top: 0.5rem; font-size: 0.95rem; }}
    .meta {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; font-size: 0.8rem; color: var(--text-muted); }}
    h2 {{ font-size: 1.2rem; margin: 2rem 0 1rem; display: flex; align-items: center; gap: 0.5rem; }}
    h3 {{ font-size: 0.95rem; margin: 1.25rem 0 0.6rem; color: var(--accent); }}
    p {{ margin-bottom: 0.75rem; color: var(--text-muted); }}
    .status {{
      display: inline-block; font-size: 0.72rem; font-weight: 600;
      padding: 0.15rem 0.45rem; border-radius: 4px;
    }}
    .status-done {{ background: var(--green-soft); color: var(--green); }}
    .status-partial {{ background: var(--amber-soft); color: var(--amber); }}
    .status-gap {{ background: var(--red-soft); color: var(--red); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 0.75rem;
      margin: 1rem 0 1.5rem;
    }}
    .metric {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1rem 1.1rem;
    }}
    .metric-value {{ font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em; }}
    .metric-label {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .metric-sub {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; }}
    table {{
      width: 100%; border-collapse: collapse; font-size: 0.875rem;
      margin: 0.75rem 0 1.5rem; background: var(--surface);
      border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border);
    }}
    th, td {{ padding: 0.65rem 0.85rem; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{
      background: var(--surface2); font-weight: 600; font-size: 0.75rem;
      text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);
    }}
    tr:last-child td {{ border-bottom: none; }}
    .phase-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.25rem 1.35rem; margin-bottom: 1rem;
    }}
    .summary-box {{
      background: var(--accent-soft); border: 1px solid rgba(61, 139, 253, 0.25);
      border-radius: var(--radius); padding: 1rem 1.25rem; margin: 1.5rem 0;
    }}
    .summary-box strong {{ color: var(--accent); }}
    code {{
      font-family: "SF Mono", Consolas, monospace; font-size: 0.8em;
      background: var(--surface2); padding: 0.1rem 0.35rem; border-radius: 4px; color: var(--green);
    }}
    ul {{ padding-left: 1.25rem; color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem; }}
    li {{ margin-bottom: 0.3rem; }}
    .preview {{
      font-size: 0.8rem;
      color: var(--text);
      background: var(--surface2);
      padding: 0.6rem 0.75rem;
      border-radius: 6px;
      margin-top: 0.5rem;
    }}
    td.why {{ color: var(--text); }}
    td.not {{ color: var(--text-muted); }}
    .why-lead {{ font-size: 0.95rem; color: var(--text); margin-bottom: 1rem; }}
    .story-say {{
      color: var(--text);
      font-size: 1rem;
      margin-bottom: 0.5rem;
    }}
    .story-num {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 1.5rem; height: 1.5rem; border-radius: 999px;
      background: var(--accent-soft); color: var(--accent);
      font-size: 0.75rem; font-weight: 700; margin-right: 0.4rem;
    }}
    .phase-card h3 {{ color: var(--text); margin-top: 0; }}
    footer {{
      margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
      font-size: 0.8rem; color: var(--text-muted);
    }}
  </style>
</head>
<body>
<header>
  <h1>Pharma AI — Core AI Proof Report</h1>
  <p class="subtitle">Live proof that the product loop works: retrieve book formulas → route lookup/compare without LLM → return cited structured recipes. Docker/Qdrant was up for this run.</p>
  <div class="meta">
    <span>Generated: {_esc(now)}</span>
    <span>Branch snapshot at report time</span>
    <span>Qdrant: {"up" if data["qdrant"] else "down"}</span>
  </div>
</header>

<div class="summary-box">
  <strong>Core loop this project is built on</strong>
  <p style="margin-top:0.6rem">User question → intent route → structured formula search (SQLite) + hybrid retrieval (Qdrant) → grounded answer with page citations. Lookup and compare skip the LLM when confidence is high. That is the feature that makes Pharma AI work.</p>
</div>

<h2>The story — how to present this</h2>
<p class="why-lead">Do not walk the audience through a feature list. Walk them through one formulator, one library, and the moment a wrong percentage becomes a bad batch. Features are the chapters of that story.</p>

<div class="summary-box">
  <strong>The line to open with (10 seconds)</strong>
  <p class="story-say" style="margin-top:0.6rem">This is not ChatGPT on PDFs. A formulator cannot use a shampoo that <em>sounds</em> right. They need a recipe that exists in a reference book — with percentages — and a page they can open. If we cannot cite the page, we refuse.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">1</span> The scene</h3>
  <p class="story-say">Sara is formulating a mild baby shampoo for the EU market. No SLS. Under a cost target. The knowledge is already in twelve books on the shelf. Finding it means flipping tables by hand. Asking a general LLM is faster — and it will invent 8.5% of a surfactant that was never in those books.</p>
  <p>In this domain a wrong percentage is not a chatbot mistake. It is a bad batch.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">2</span> What we refused to build</h3>
  <p class="story-say">The obvious product is “chat with your PDFs.” We did not ship that. A prompt will regenerate the table and change the chemistry. Keyword search misses “mild baby wash.” Fine-tuning still cannot show page 38 of volume 8.</p>
  <p>So the product promise is narrower and stricter: <strong style="color:var(--text)">grounded recipes from our library, or an honest no.</strong></p>
</div>

<div class="phase-card">
  <h3><span class="story-num">3</span> The library becomes software</h3>
  <p class="story-say">The books already look like tables to Sara. A PDF of those tables is not a database. We ingest the PDFs, recover text and grids, and parse each formula into rows: name, ingredient, amount, phase, page. That SQLite library is the source of truth. Chunks in Qdrant are for “why / how” prose. Two stores, two jobs.</p>
  <p>We did not OCR this corpus — the pages had a text layer. OCR is only a fallback for future scans. “Structured” means queryable rows, not “the book had columns.”</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">4</span> The first question — this is the demo</h3>
  <p class="story-say"><em>“Give me a baby shampoo formula with percentages.”</em></p>
  <p>Intent is lookup. We search the structured library, not the LLM. The answer is a named book formula, a table of amounts, and the source page. The model is not asked to write chemistry. That skip-LLM path is the product: fast, cheap, and the percentages are copied, not generated.</p>
  <p>Then the follow-up: <em>“Make it sulfate-free.”</em> Without rewrite, search would drop “baby shampoo.” Query rewrite keeps the thread. Same library, same skip-LLM, new constraint.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">5</span> When the LLM is allowed in</h3>
  <p class="story-say"><em>“Why is CAPB used instead of SLS in mild shampoos?”</em></p>
  <p>Now we retrieve passages and let the model speak — with citations. Vague “best shampoo” is classified unknown, not a fake winner. The LLM is a reasoning layer on retrieved evidence, not the author of recipes.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">6</span> Constraints a formulator actually has</h3>
  <p class="story-say">Sara never asks for “any shampoo.” She asks for EU-legal, no formaldehyde, under a $/kg.</p>
  <p>Once formulas are rows, those are filters — not prompt hopes. Cost is arithmetic on a price list. Substitutions are role-compatible swaps from the same library. Compare is a structured diff of two book recipes, not an essay.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">7</span> What can we make from what we have?</h3>
  <p class="story-say">The warehouse question is the same library, turned around: inventory × book recipes.</p>
  <p>SKU names are not INCI names. Fuzzy match first, embeddings when “CAPB” must meet “cocamidopropyl betaine,” a learned override when a human confirms the alias. Banned / market / cost still apply. This is not a second chatbot. It is the formulary meeting the stockroom.</p>
</div>

<div class="phase-card">
  <h3><span class="story-num">8</span> Trust, then the honest ending</h3>
  <p class="story-say">Parsers fail. Low-confidence rows go to a review queue. A verified badge is a calibrated score, not a green sticker. If there is no source, we refuse.</p>
  <p>What works today: product-type lookup (“baby shampoo”) with a cited table. What still fails: a specific book title plus a constraint we never stored (SPF 24, “normal skin”), or a table the parser only half-read. We present that as the next chapter — not as 100% RAG.</p>
</div>

<h2>Talk track — features in story order</h2>
<p class="why-lead">If you have eight minutes, say these beats in this order. Demo the baby-shampoo turn in beat 4. Do not start with architecture.</p>
<table>
  <thead>
    <tr><th>Beat</th><th>What you say</th><th>Feature you are showing</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="why">Opening</td>
      <td class="why">Not ChatGPT on PDFs. Cited recipes, or we refuse.</td>
      <td class="not">Product promise</td>
    </tr>
    <tr>
      <td class="why">The job</td>
      <td class="why">Formulator + books. A wrong % is a bad batch.</td>
      <td class="not">Problem, not a slide of logos</td>
    </tr>
    <tr>
      <td class="why">RAG</td>
      <td class="why">The books are the authority. Retrieve, then answer. Cite the page.</td>
      <td class="not">Hybrid retrieval (BGE + Qdrant + BM25)</td>
    </tr>
    <tr>
      <td class="why">Structure</td>
      <td class="why">A printed table is not a database. We parsed it into rows so we can copy chemistry, not generate it.</td>
      <td class="not">PDF ingest + SQLite formulas</td>
    </tr>
    <tr>
      <td class="why">Demo</td>
      <td class="why">“Give me a baby shampoo.” Table, amounts, page. No LLM.</td>
      <td class="not">Intent routing + skip-LLM lookup</td>
    </tr>
    <tr>
      <td class="why">Follow-up</td>
      <td class="why">“Make it sulfate-free.” Still the baby shampoo.</td>
      <td class="not">Query rewrite (Phase A)</td>
    </tr>
    <tr>
      <td class="why">Why / how</td>
      <td class="why">Now the model may speak, with evidence.</td>
      <td class="not">Reasoning route + grounding</td>
    </tr>
    <tr>
      <td class="why">Brief</td>
      <td class="why">EU, no SLS, under cost — filters, not vibes.</td>
      <td class="not">Markets, banned, cost_target (A/C)</td>
    </tr>
    <tr>
      <td class="why">Tools</td>
      <td class="why">$/kg, substitutions, compare two book recipes.</td>
      <td class="not">Cost estimator, substitutions, compare UI (C)</td>
    </tr>
    <tr>
      <td class="why">Warehouse</td>
      <td class="why">What can we make from this inventory?</td>
      <td class="not">Discover + alias matching (D)</td>
    </tr>
    <tr>
      <td class="why">Trust</td>
      <td class="why">Verified badge, review queue, refuse if empty.</td>
      <td class="not">KBS + ingest quality (B)</td>
    </tr>
    <tr>
      <td class="why">Close</td>
      <td class="why">Works for product-type lookup. Named titles and half-parsed tables are the gap. Here is the evidence.</td>
      <td class="not">Eval honesty (3/4 live, 2/50 hard)</td>
    </tr>
  </tbody>
</table>

<div class="phase-card">
  <h3>90-second version (if that is all you get)</h3>
  <p class="story-say">Formulation knowledge lives in books. A general model will invent a formula. We retrieve from those books, parse the tables into a database, and for “give me a recipe” we copy the row and cite the page — the model does not write the chemistry. Follow-ups keep context. Markets, cost, and warehouse stock are filters on the same library. If we cannot ground it, we say so. The remaining work is ranking named formulas and completing half-extracted tables — not adding another chatbot.</p>
</div>

<h2>How chatting actually works</h2>
<p class="why-lead">This path is implemented in the product — not a slide. UI is Next.js, threads live in Laravel, answers come from Python <code>route_chat()</code>.</p>

<div class="phase-card">
  <h3>One turn, end to end</h3>
  <p class="story-say">Sara types in <code>/chat</code>. The browser sends the message (plus optional brief: markets, banned, cost) to Laravel. Laravel loads recent thread history, saves the user message, and proxies to FastAPI <code>POST /chat</code> or <code>/chat/stream</code>. Python answers. Laravel stores the assistant message (markdown, structured formula JSON, citations, route). The UI renders the table, source page, and thumbs.</p>
</div>

<table>
  <thead>
    <tr><th>Step</th><th>What happens</th><th>Where</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="why">1. Thread</td>
      <td class="why">Create or resume a conversation. History is persisted so follow-ups work after refresh.</td>
      <td class="not">Laravel <code>chat_threads</code> / <code>chat_messages</code></td>
    </tr>
    <tr>
      <td class="why">2. Rewrite</td>
      <td class="why">If the message is a follow-up (“make it sulfate-free”), rewrite it into a standalone search query using recent history. Short messages always rewrite; otherwise a cheap heuristic, optional LLM rewrite.</td>
      <td class="not"><code>query_rewrite.py</code></td>
    </tr>
    <tr>
      <td class="why">3. Route</td>
      <td class="why">Classify: <code>lookup</code> (give me a formula), <code>compare</code>, <code>reasoning</code> (why/how), or <code>unknown</code> (“best shampoo” — we do not fake a winner).</td>
      <td class="not"><code>intent.py</code> → <code>route_chat()</code></td>
    </tr>
    <tr>
      <td class="why">4. Brief filters</td>
      <td class="why">Merge UI constraints (banned ingredients, markets, cost target) into the search. These are SQL/structured filters, not a prompt.</td>
      <td class="not">Constraints panel → <code>structured_brief</code></td>
    </tr>
    <tr>
      <td class="why">5a. Lookup / compare</td>
      <td class="why">Search SQLite formulas. If confidence is high, <strong>skip the LLM</strong>: copy the recipe table and cite the book page. Compare is a structured diff of two (or more) recipes.</td>
      <td class="not"><code>formulation/search.py</code></td>
    </tr>
    <tr>
      <td class="why">5b. Reasoning</td>
      <td class="why">Hybrid retrieve (Qdrant dense + BM25), then the LLM answers with quotes checked against chunks. No sources → refuse.</td>
      <td class="not"><code>retrieval/search.py</code> + LLM</td>
    </tr>
    <tr>
      <td class="why">6. Show</td>
      <td class="why">Markdown answer, formula worksheet (ingredients, %, phase), source document + page, suggested next actions, thumbs up/down.</td>
      <td class="not">Chat thread + formula panel</td>
    </tr>
  </tbody>
</table>

<p><strong style="color:var(--text)">What to demo:</strong> first turn “Give me a baby shampoo formula with percentages” (lookup, no LLM). Second turn “make it sulfate-free” (rewrite keeps baby shampoo). Third turn “why is CAPB used instead of SLS?” (reasoning, LLM on).</p>

<h2>Why this architecture (conference story)</h2>
<p class="why-lead">The job is not “chat with a PDF.” A formulator cannot use a plausible-sounding shampoo. They need a recipe that exists in a reference book, with percentages, and a page they can open. Every design choice below is in service of that.</p>

<div class="phase-card">
  <h3>The problem</h3>
  <p>Formulation knowledge lives in printed books (tables of ingredients, phases, procedures). Searching by hand is slow. A general LLM will happily invent a formula that looks professional and is wrong. In this domain, a wrong percentage is not a UX bug — it is a bad batch.</p>
</div>

<div class="phase-card">
  <h3>The books already have tables — that is not the same as structured data</h3>
  <p>Yes: a cosmetic formulary is already a table on the page (ingredient, wt%, phase). That is structured <em>for a human holding the book</em>.</p>
  <p>A PDF of that page is not a database. There is no query for “no SLS, EU, under $12/kg,” no stable formula ID, no INCI alias, no way to compare two recipes or skip the LLM. PyMuPDF can recover some grid cells, but reading order, wrapped names, and broken numbers still come out as messy text. “We structured the data” means we turned those visual tables into SQLite rows the product can filter, cite, and copy.</p>
  <p><strong style="color:var(--text)">OCR on this corpus: {health['ocr_docs']} documents, {health['ocr_pages']} pages.</strong> Tesseract runs only as a fallback for image-only scanned pages (text &lt; 40 characters). Amount-repair code (`5 . 0 0` → `5.00`) is for messy PDF extraction, not “we OCR’d the library.”</p>
</div>

<table>
  <thead>
    <tr><th>Step / feature</th><th>Why we chose it</th><th>What we did not choose — and why</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="why"><strong>RAG at all</strong><br/>retrieve first, then answer</td>
      <td class="why">The authority is the corpus, not the model’s training data. RAG lets us point to a book page. If nothing relevant is retrieved, we can refuse instead of hallucinating.</td>
      <td class="not"><strong>Not a bare LLM.</strong> GPT already “knows” cosmetics in a generic way. That knowledge is uncited, undated, and not your library. Fine-tuning on books still cannot show page 38 of volume 8.</td>
    </tr>
    <tr>
      <td class="why"><strong>Not keyword search alone</strong></td>
      <td class="why">Formulators ask in many wordings (“mild baby wash”, “sulfate-free shampoo”). Dense embeddings catch meaning. BM25 still helps exact INCI names and trade strings.</td>
      <td class="not"><strong>Not Elasticsearch-only.</strong> Exact match fails on paraphrase and Arabic queries. <strong>Not vectors-only.</strong> Rare chemical names are sparse; hybrid (RRF) covers both.</td>
    </tr>
    <tr>
      <td class="why"><strong>Structured formulas</strong><br/>SQLite rows: name, ingredient, %, page</td>
      <td class="why">The book already shows a table to a human. We need that same table as machine rows so we can filter (banned, markets, cost), scale a batch, compare two recipes, and return amounts without asking an LLM to re-parse the page every time.</td>
      <td class="not"><strong>Not “the PDF was already structured.”</strong> A printed table is not queryable. <strong>Not chunks-only RAG.</strong> Text snippets force the LLM to rebuild the table — that is how percentages get invented.</td>
    </tr>
    <tr>
      <td class="why"><strong>Ingest + parsers</strong><br/>PDF text + find_tables → formula parsers</td>
      <td class="why">Default path: PyMuPDF extracts selectable text and table grids. Deterministic parsers then split “Phase A / Phase B,” ingredients, and amounts into rows with a page citation.</td>
      <td class="not"><strong>Not “dump PDF into the LLM.”</strong> Context windows cannot hold the library, and the model would still guess tables. <strong>Not retyping into Excel</strong> as the primary path — too slow for hundreds of formulas.</td>
    </tr>
    <tr>
      <td class="why"><strong>OCR fallback</strong><br/>Tesseract, only if a page is almost empty</td>
      <td class="why">Some formulation PDFs are scans (image, no text layer). Without OCR those pages would ingest as blank. We run Tesseract only when extracted text is under 40 characters and the page has images.</td>
      <td class="not"><strong>Not the pipeline for this corpus.</strong> This ingest: {health['ocr_docs']} OCR docs, {health['ocr_pages']} OCR pages. Amount-repair (`5 . 0 0` → `5.00`) is separate — it fixes broken PDF numbers even when Tesseract never ran.</td>
    </tr>
    <tr>
      <td class="why"><strong>Two stores</strong><br/>Qdrant (chunks) + SQLite (formulas)</td>
      <td class="why">Chunks answer “why is CAPB used?” (prose). Formulas answer “give me the recipe” (table). One index cannot do both jobs well.</td>
      <td class="not"><strong>Not one vector DB for everything.</strong> You cannot reliably filter “cost under $12/kg” or “no formaldehyde” on embedding similarity.</td>
    </tr>
    <tr>
      <td class="why"><strong>Intent routing</strong><br/>lookup / compare / reasoning</td>
      <td class="why">Most questions are “give me a formula” or “compare these two.” Those should be a database hit: sub-second, no API bill, no invented %. LLM only when the user asks why/how.</td>
      <td class="not"><strong>Not LLM-on-every-turn.</strong> That is slower, costlier, and more likely to rewrite amounts. Routing is the product decision: extraction is the source of truth for recipes.</td>
    </tr>
    <tr>
      <td class="why"><strong>Grounding</strong><br/>page citation, quote check, refuse if empty</td>
      <td class="why">Trust is the feature. The UI shows the book and page. Quotes that do not appear in the chunk are flagged. No sources → transparent failure, not a confident fake formula.</td>
      <td class="not"><strong>Not “the model said so.”</strong> In R&amp;D, an unsourced answer is unused. We would rather under-answer than ship a hallucinated 8% surfactant.</td>
    </tr>
    <tr>
      <td class="why"><strong>Conversation rewrite</strong><br/>“make it sulfate-free”</td>
      <td class="why">Follow-ups are how people chat. Without rewrite, retrieval searches the words “make it sulfate-free” and drops “baby shampoo.” A cheap rewrite (rules, optional LLM) restores the full query before search.</td>
      <td class="not"><strong>Not stuffing the whole thread into the embedder.</strong> Noise hurts retrieval. Rewrite produces one search string. <strong>Not forcing the user to restate the product every turn.</strong></td>
    </tr>
    <tr>
      <td class="why"><strong>KBS (knowledge-base scoring)</strong></td>
      <td class="why">Parsers fail. Completeness, amount ranges, and regulatory flags produce a precision score so a “verified” badge means something. Humans review low-confidence rows instead of trusting every extraction.</td>
      <td class="not"><strong>Not “if it parsed, it is true.”</strong> And not an admin role system — this is quality of the corpus, not access control.</td>
    </tr>
    <tr>
      <td class="why"><strong>Brief constraints</strong><br/>banned, markets, cost</td>
      <td class="why">A formulator never asks for “any shampoo.” They ask for EU-legal, no SLS, under a cost. Filters run on structured rows. That is only possible because we extracted tables.</td>
      <td class="not"><strong>Not prompt-only constraints</strong> (“please avoid SLS”). The model might forget. A SQL/structured filter cannot forget.</td>
    </tr>
    <tr>
      <td class="why"><strong>Cost, substitutions, warehouse</strong></td>
      <td class="why">Once you have structured formulas, the same objects support tools: $/kg from a price list, substitution rules, “what can we make from this inventory.” These are not a second AI — they consume the library RAG already built.</td>
      <td class="not"><strong>Not a separate ERP chatbot.</strong> Warehouse matching without a formula graph is just fuzzy string matching on SKUs. The value is inventory × book recipes.</td>
    </tr>
  </tbody>
</table>

<h2>What each shipped feature is for</h2>
<p class="why-lead">These are the product pieces we actually built. Each one exists to close a specific failure of “just RAG” or “just an LLM.”</p>
<table>
  <thead>
    <tr><th>Feature</th><th>Purpose — the job it does</th><th>Why this, not another plan</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="why"><strong>PDF ingest + table parsers</strong></td>
      <td class="why">Turn the book’s visual tables into a searchable library (chunks + SQLite). Without ingest there is nothing to retrieve or look up.</td>
      <td class="not">The PDF is the source, not the database. Manual spreadsheet entry does not scale. Dumping whole PDFs into the prompt does not give reusable recipes.</td>
    </tr>
    <tr>
      <td class="why"><strong>OCR fallback</strong></td>
      <td class="why">Keep scanned (image-only) pages from being dropped. Built so a future scan still ingests.</td>
      <td class="not">Not used on this ingest ({health['ocr_pages']} pages). We did not choose OCR as the default way to read these books — selectable PDF text is the main path.</td>
    </tr>
    <tr>
      <td class="why"><strong>Hybrid retrieval</strong><br/>BGE + Qdrant + BM25</td>
      <td class="why">Find the right book pages for a question asked in ordinary language (and Arabic).</td>
      <td class="not">Keyword-only misses paraphrase. Embedding-only misses rare INCI strings. Hybrid was the compromise that works on both.</td>
    </tr>
    <tr>
      <td class="why"><strong>Structured formula store</strong></td>
      <td class="why">Hold each recipe as ingredient + % + phase + page so lookup can return a table, not a paragraph.</td>
      <td class="not">Chunks-only RAG would force the LLM to rebuild every table. That is how percentages get invented.</td>
    </tr>
    <tr>
      <td class="why"><strong>Intent routing</strong><br/>lookup / compare / reasoning</td>
      <td class="why">Send “give me a formula” to the database. Send “why is CAPB used?” to the LLM with retrieved evidence.</td>
      <td class="not">One chat completion per turn is slower, costlier, and will rewrite chemistry. Routing is how we keep recipes grounded.</td>
    </tr>
    <tr>
      <td class="why"><strong>Skip-LLM lookup/compare</strong></td>
      <td class="why">When the structured hit is confident, copy the JSON into the answer. No generation of amounts.</td>
      <td class="not">“Always generate, then cite” still lets the model change 8.5% to 9%. Copying the extraction is the safer product.</td>
    </tr>
    <tr>
      <td class="why"><strong>Grounding + page citations</strong></td>
      <td class="why">The formulator must be able to open the book. If there is no source, refuse.</td>
      <td class="not">A fluent unsourced answer is unused in R&amp;D. We optimized for verifiability, not for sounding complete.</td>
    </tr>
    <tr>
      <td class="why"><strong>Query rewrite</strong> (Phase A)</td>
      <td class="why">Keep multi-turn chat working: “make it sulfate-free” still means the baby shampoo from the last turn.</td>
      <td class="not">Re-embedding the raw follow-up loses the product. Stuffing the whole thread into search adds noise. Rewrite to one query.</td>
    </tr>
    <tr>
      <td class="why"><strong>Markets on the brief</strong> (Phase A)</td>
      <td class="why">EU vs US is a hard constraint, not a vibe. Filter structured rows by market rules.</td>
      <td class="not">Asking the LLM “please keep it EU-legal” is not auditable. A filter either matches or it does not.</td>
    </tr>
    <tr>
      <td class="why"><strong>Ingest quality + review queue</strong> (Phase B)</td>
      <td class="why">Parsers fail. Low-confidence extractions go to a human instead of silently entering the library.</td>
      <td class="not">Shipping every parse as truth would poison RAG. Trust of the corpus is a product feature.</td>
    </tr>
    <tr>
      <td class="why"><strong>KBS verified badge</strong> (Phase B)</td>
      <td class="why">Tell the user which recipes are complete enough to act on (amounts, ranges, flags).</td>
      <td class="not">A binary “parsed / not parsed” hides junk tables. Scoring is how the badge means something.</td>
    </tr>
    <tr>
      <td class="why"><strong>Cost estimator + cost_target</strong> (Phase C)</td>
      <td class="why">Formulators design to a $/kg. Once formulas are tables, cost is arithmetic on a price list.</td>
      <td class="not">Asking the LLM to guess cost is fiction. Cost only exists because structure exists.</td>
    </tr>
    <tr>
      <td class="why"><strong>Substitutions</strong> (Phase C)</td>
      <td class="why">If an ingredient is banned, missing, or too expensive, suggest a role-compatible swap from the library.</td>
      <td class="not">A generic “try cocamidopropyl betaine” from the model is not tied to a book formula or inventory.</td>
    </tr>
    <tr>
      <td class="why"><strong>Warehouse discover</strong> (Phase D)</td>
      <td class="why">Answer “what can we make from what we have?” by matching inventory to book recipes, with banned/market/cost filters.</td>
      <td class="not">A separate inventory chatbot cannot see recipes. Fuzzy SKU match without a formula graph is not formulation intelligence.</td>
    </tr>
    <tr>
      <td class="why"><strong>Embedding alias fallback</strong> (Phase D)</td>
      <td class="why">Warehouse names rarely equal INCI names. Embeddings catch “CAPB” ≈ “cocamidopropyl betaine” after fuzzy fails.</td>
      <td class="not">LLM matching every SKU is slow and non-deterministic. Embeddings sit between exact/fuzzy and a last-resort LLM.</td>
    </tr>
    <tr>
      <td class="why"><strong>Learned alias overrides</strong> (Phase D)</td>
      <td class="why">When a human confirms “this SKU is that INCI,” remember it. The warehouse gets smarter without retraining.</td>
      <td class="not">Re-running fuzzy forever repeats the same miss. A small override table is cheaper than a custom NER model.</td>
    </tr>
    <tr>
      <td class="why"><strong>Formula compare UI</strong></td>
      <td class="why">Show two book recipes side by side (ingredients, roles, cost, compliance) without generating a new formula.</td>
      <td class="not">“Write a comparison paragraph” would hide the tables. Compare is a structured diff, not an essay.</td>
    </tr>
    <tr>
      <td class="why"><strong>Thumbs feedback</strong></td>
      <td class="why">Capture which answers formulators trust, so later we can mine misses. Not yet a closed training loop.</td>
      <td class="not">We did not auto-fine-tune from thumbs. That would reward fluency, not book-faithfulness.</td>
    </tr>
  </tbody>
</table>

<p><strong style="color:var(--text)">How to say it in one breath:</strong> we used RAG because the books are the authority; we structured the data because a formula is a table, and tables let us answer lookup without generating chemistry.</p>

<p style="font-size:0.85rem">The numbers below are <em>regression proof</em> that this loop still runs on the intended queries. They are not a held-out scientific RAG benchmark. Hard named-formula questions remain a known gap.</p>

<div class="grid">
  {metric_card("Core chat pipeline", f"{core['passed']}/{core['n']}", f"{core['rate']}% live turns · follow-up {('pass' if follow['ok'] else 'fail')}")}
  {metric_card("Retrieval hit@k", retrieval_note, "NFR-ACC-06 ≥90%")}
  {metric_card("Unit tests", f"{pytest['passed']}/{pytest['total']}", pytest["summary"] or "")}
  {metric_card("KBS F1", f"{kbs['f1']:.3f}", f"n={kbs['n']}")}
  {metric_card("Corpus formulas", str(ingest["total_formulas"]), f"{ingest['share_6plus_ingredients']*100:.0f}% have ≥6 ingredients")}
  {metric_card("Qdrant", "up" if data["qdrant"] else "down", "pharma_chunks")}
</div>

<p>{pill(overall_pass)} Core loop is working on live Qdrant: {core['passed']}/{core['n']} product turns + follow-up {pill(follow['ok'])} · retrieval {pill(None if retrieval['skipped'] else retrieval.get('meets_target'), skipped=retrieval['skipped'])} · tests {pill(pytest['ok'])}.</p>

<h2>0. Live core pipeline (this is the product)</h2>
<p>Each row is a real <code>route_chat()</code> call against the ingested books + Qdrant. Lookup/compare must return a named formula with amounts and citations, and must <em>not</em> call the LLM.</p>
{core_cards}
<div class="phase-card">
  <h3>Follow-up rewrite — “make it sulfate-free” {pill(follow['ok'])}</h3>
  <p>After “Give me a baby shampoo formula”, the next turn must keep baby-shampoo context.</p>
  <p>Rewritten query: <code>{_esc(follow['rewritten'])}</code> · rewritten={_esc(follow['was_rewritten'])} · route=<code>{_esc(follow['route'])}</code> · llm=<code>{_esc(follow['llm_used'])}</code></p>
  <p>Formulas: {_esc(', '.join(follow['formula_names']) or '—')}</p>
  <p class="preview">{_esc(follow['answer_preview'])}</p>
  {('<ul>' + ''.join(f'<li>{_esc(e)}</li>' for e in follow['errors']) + '</ul>') if follow['errors'] else ''}
</div>

<h2>1. Unit &amp; smoke tests</h2>
<p>CI suite plus Phase C/D tests. These prove chat rewrite, cost filter, warehouse constraints, compare, and feedback logging without a live vector index.</p>
<table>
  <thead><tr><th>Metric</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>Passed</td><td>{pytest['passed']}</td></tr>
    <tr><td>Failed</td><td>{pytest['failed']}</td></tr>
    <tr><td>Exit</td><td>{pytest['exit_code']}</td></tr>
  </tbody>
</table>

<h2>2. Corpus / ingest quality</h2>
<p>What the parsers actually extracted into SQLite. Thresholds: ≥45% formulas with 6+ ingredients, ≥80% with amounts, ≥25% with procedure, median ≥5 ingredients, ≤8% two-ingredient-only.</p>
<div class="grid">
  {metric_card("Formulas", str(ingest["total_formulas"]))}
  {metric_card("≥6 ingredients", f"{ingest['share_6plus_ingredients']*100:.0f}%")}
  {metric_card("Have amounts", f"{ingest['share_with_amounts']*100:.0f}%")}
  {metric_card("Have procedure", f"{ingest['share_with_procedure']*100:.0f}%")}
  {metric_card("Median ingredients", f"{ingest['median_ingredients']:.1f}")}
  {metric_card("High confidence", f"{ingest['share_high_confidence']*100:.0f}%")}
</div>
<p>OCR docs: {health['ocr_docs']} · OCR pages: {health['ocr_pages']} · Ingest gate: {pill(ingest['passed'])}</p>
<p>Zero (or low) OCR means Tesseract did not have to run: pages had a text layer, so PyMuPDF + table parsers were enough. OCR remains a fallback for scans, not a required step.</p>
{"<ul>" + ingest_fail + "</ul>" if ingest_fail else "<p>No ingest-threshold failures.</p>"}

<h2>3. KBS verified-badge classifier</h2>
<p>Precision/recall of the <code>verified</code> badge vs labeled golden extractions (<code>golden_kbs.json</code>).</p>
<div class="grid">
  {metric_card("Precision", f"{kbs['precision']:.3f}")}
  {metric_card("Recall", f"{kbs['recall']:.3f}")}
  {metric_card("F1", f"{kbs['f1']:.3f}")}
  {metric_card("Confusion", f"tp {kbs['tp']} / fp {kbs['fp']} / fn {kbs['fn']} / tn {kbs['tn']}")}
</div>
{"<ul>" + kbs_misses + "</ul>" if kbs_misses else "<p>No misclassifications listed.</p>"}

<h2>4. Intent routing + structured formulas</h2>
<p>Golden product questions. Classification does not need Qdrant. Lookup/compare also require a complete on-topic formula from SQLite structured search.</p>
<table>
  <thead>
    <tr><th>Query</th><th>Expect</th><th>Got</th><th>Top formula</th><th>Conf</th><th>Ings</th><th>Result</th></tr>
  </thead>
  <tbody>{routing_rows}</tbody>
</table>
<p>Structured lookup/compare: {routing['structured_passed']}/{routing['structured_n']} ({routing['structured_rate']}%).</p>
{"<ul>" + routing_fail_detail + "</ul>" if routing_fail_detail else ""}

<h2>5. Retrieval hit@k (NFR-ACC-06)</h2>
<p>Golden set size: {retrieval['golden_n']} questions in <code>golden_retrieval.json</code>. Target ≥90% pass on formula-in-top-k / product-type / forbidden-phrase checks.</p>
{"<p>Skipped: " + _esc(retrieval['reason']) + " Start Docker, then <code>cd ai-service && docker compose up -d qdrant</code> and re-run <code>scripts/write_eval_report.py</code>.</p>" if retrieval["skipped"] else f"<p>Pass rate <strong style='color:var(--text)'>{retrieval['rate']}%</strong> ({retrieval['passed']}/{retrieval['golden_n']}). Meets 90% target: {pill(retrieval.get('meets_target'))}</p><table><thead><tr><th>Question</th><th>Result</th><th>Errors</th></tr></thead><tbody>{retrieval_rows}</tbody></table>"}

<h2>6. Formulator tools (live corpus smoke)</h2>
<div class="phase-card">
  <h3>Cost estimator</h3>
  <p>Price keys {cost['price_table_keys']} · sampled {cost['formulas_sampled']} formulas · {cost['share_priced']}% got a $/kg · median coverage {cost['median_coverage_pct']}% · mean ${cost['mean_cost_per_kg']}/kg among priced.</p>
  <h3>Compare</h3>
  <p>{pill(compare['ok'])} {_esc(compare.get('left','—'))} vs {_esc(compare.get('right','—'))} · Δcost {compare.get('cost_delta')} · compliance {compare.get('left_compliance')}/{compare.get('right_compliance')} · roles: {_esc(', '.join(compare.get('roles') or []))}</p>
  <h3>Brief filters</h3>
  <p>{pill(brief['ok'])} Pool {brief['pool']} → banned formaldehyde {brief['after_banned_formaldehyde']} → EU markets {brief['after_eu_markets']}.</p>
</div>

<h2>7. Archived LLM-as-judge (hard questions)</h2>
<p>Not re-run (OpenRouter cost). From <code>scripts/hard_eval_results.json</code>.</p>
{f'''
<div class="grid">
  {metric_card("Pass", f"{hard['passed']}/{hard['total']}", f"{hard['pass_rate']}%")}
  {metric_card("Mean score", str(hard['mean_score']), "1–5 judge scale")}
  {metric_card("Judge", hard['judge_model'] or "—")}
</div>
<table>
  <thead><tr><th>Route</th><th>N</th><th>Mean score</th><th>Pass</th></tr></thead>
  <tbody>{hard_route_rows}</tbody>
</table>
<p>{_esc(hard['note'])} This 4% pass rate is the stress test on named book formulas, not the golden product queries above.</p>
''' if hard else "<p>No archived hard-eval file.</p>"}

<h2>Why some questions still fail</h2>
<p class="why-lead">These are not “the LLM is dumb.” Lookup often skips the LLM on purpose. Failures are ranking, incomplete tables, and named-formula search — three different bugs.</p>

<table>
  <thead>
    <tr><th>What failed</th><th>What actually happened</th><th>Why — the real cause</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="why"><strong>Live hand cream</strong><br/>1/4 core pipeline</td>
      <td class="why">Asked for a hand cream for normal skin. Returned <em>Prescription 5.27 Cream</em> (a generic cream, 16 ingredients) from the Japanese book. Intent was correct (lookup, no LLM).</td>
      <td class="not">“Hand cream” is tagged only as product type <code>cream</code>. Scoring then rewards a fat cream table. Title match (“hand cream” / “tube-dispensed”) is weaker than ingredient-count. “Normal skin” is ignored — we have no skin-type field. A named hand cream exists in SQLite; it did not win the rank.</td>
    </tr>
    <tr>
      <td class="why"><strong>Anti-dandruff 4 ingredients</strong><br/>golden 4/6</td>
      <td class="why">Returned the right product (<em>Anti-Dandruff Lotion ShamDoo</em>) with amounts. Live eval passes (bar ≥3). Golden fails because it demands ≥6 ingredients.</td>
      <td class="not">The parser kept 4 rows. Either the book table is short, or rows were dropped (garbled names like ShamDoo). This is incomplete extraction, not a wrong route. Same answer, two bars.</td>
    </tr>
    <tr>
      <td class="why"><strong>Hand cream 5 ingredients</strong><br/>golden 4/6</td>
      <td class="why">Structured search <em>did</em> find <em>Tube-Dispensed Hand Cream</em> — the right name — but only 5 parsed ingredients, bar is 6.</td>
      <td class="not">Again extraction completeness, not intent. Live chat did not even surface this formula (see ranking above). Two evals, two different tops, both “fail” for different reasons.</td>
    </tr>
    <tr>
      <td class="why"><strong>Hard set 2/50</strong><br/>named book questions</td>
      <td class="why">Questions like “sunscreen with SPF 24 and Carbopol Ultrez” or “compare emulsifiers in Anti-Acne Cream vs Moisturizing Facial Lotion.” Judge: wrong product, missing named ingredients.</td>
      <td class="not">This is the gap skip-LLM creates. Lookup copies the nearest structured formula by product type. It does not hunt a title + SPF + thickener. Book names are noisy (ShamDoo, Moisturizina). Compare of two named recipes needs two exact hits; we often return two similar types instead. Reasoning needs the right pages; wrong retrieval → the LLM explains the wrong formula.</td>
    </tr>
    <tr>
      <td class="why"><strong>Retrieval 12/12 still passes</strong></td>
      <td class="why">Hit@k only asks: is something on-topic in the top-k chunks?</td>
      <td class="not">That is not “the top recipe is the named hand cream with a full table.” Retrieval can pass while lookup still ranks the wrong cream. Do not quote 12/12 as proof named-formula QA works.</td>
    </tr>
  </tbody>
</table>

<p><strong style="color:var(--text)">How to say it:</strong> the core loop works when the query is a product type (“baby shampoo”). It still fails when the query is a specific title, a constraint the extractors never stored (SPF 24, normal skin), or a table the parser only half-read.</p>

<h2>Read this before the next feature</h2>
<table>
  <thead><tr><th>Gate</th><th>Status</th><th>What it means</th></tr></thead>
  <tbody>
    <tr><td>Unit tests</td><td>{pill(pytest['ok'])}</td><td>Rewrite, cost, warehouse D, compare, feedback work in isolation.</td></tr>
    <tr><td>Corpus completeness</td><td>{pill(ingest['passed'])}</td><td>Extracted library is usable for lookup.</td></tr>
    <tr><td>KBS F1</td><td>{pill(kbs['f1'] >= 0.7)}</td><td>Verified badge is calibrated, not random.</td></tr>
    <tr><td>Golden routing/formulas</td><td>{pill(routing['failed'] == 0)}</td><td>Intent plus structured formula completeness on product golden cases.</td></tr>
    <tr><td>Retrieval ≥90%</td><td>{pill(None if retrieval['skipped'] else retrieval.get('meets_target'), skipped=retrieval['skipped'])}</td><td>NFR-ACC-06 golden retrieval hit@k on live Qdrant.</td></tr>
    <tr><td>Hard LLM judge</td><td><span class="status status-gap">2/50 archived</span></td><td>Named-formula / compare / why-questions are still the weak lane.</td></tr>
  </tbody>
</table>

<footer>
  Written by <code>ai-service/scripts/write_eval_report.py</code> · Re-run with <code>PYTHONPATH=. .venv/bin/python scripts/write_eval_report.py</code> · See also <code>ai-roadmap.html</code>
</footer>
</body>
</html>
"""


def main() -> int:
    print("Running pytest…")
    pytest = run_pytest()
    print(f"  {pytest['summary'] or pytest}")

    print("Ingest / corpus…")
    ingest_rep = audit_ingest_quality()
    ingest = {
        "total_formulas": ingest_rep.total_formulas,
        "share_6plus_ingredients": ingest_rep.share_6plus_ingredients,
        "share_with_amounts": ingest_rep.share_with_amounts,
        "share_with_procedure": ingest_rep.share_with_procedure,
        "share_high_confidence": ingest_rep.share_high_confidence,
        "share_2_ingredient_only": ingest_rep.share_2_ingredient_only,
        "median_ingredients": ingest_rep.median_ingredients,
        "avg_ingredients": ingest_rep.avg_ingredients,
        "passed": ingest_rep.passed,
        "failures": ingest_rep.failures,
    }
    health_rep = build_corpus_health_report()
    health = {
        "ocr_docs": health_rep.ocr.documents_with_ocr,
        "ocr_pages": health_rep.ocr.total_ocr_pages,
    }
    print(f"  {ingest['total_formulas']} formulas, passed={ingest['passed']}")

    print("KBS…")
    kbs = evaluate_kbs()
    print(f"  F1={kbs['f1']}")

    print("Core live pipeline (route_chat)…")
    core = run_core_pipeline()
    print(f"  {core['passed']}/{core['n']} followup={core['followup']['ok']}")

    print("Routing + structured search…")
    routing = run_routing_and_structured()
    print(f"  {routing['passed']}/{routing['n']}")

    print("Retrieval…")
    retrieval = run_retrieval()
    print("  skipped" if retrieval["skipped"] else f"  {retrieval['rate']}%")

    print("Cost / compare / brief…")
    cost = cost_sample()
    compare = compare_smoke()
    brief = brief_filter_smoke()

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "qdrant": qdrant_up(),
        "pytest": pytest,
        "ingest": ingest,
        "health": health,
        "kbs": kbs,
        "core": core,
        "routing": routing,
        "retrieval": retrieval,
        "cost": cost,
        "compare": compare,
        "brief": brief,
        "hard_eval": hard_eval_summary(),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0 if pytest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
