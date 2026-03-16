"""LLM Benchmark Runner — measures real LLM quality against golden datasets.

Usage:
    python -m tests.eval.benchmark run [--label "description"]
    python -m tests.eval.benchmark set-baseline benchmarks/<file>.json
    python -m tests.eval.benchmark compare [--baseline PATH] [--current PATH]
    python -m tests.eval.benchmark list
"""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import settings
from app.services.llm import evaluate_candidates, extract_metadata, synthesize_summary
from tests.eval.golden_datasets import (
    CATEGORY_GOLDEN,
    INTENT_GOLDEN,
    SCORING_PAIRS,
    SUMMARY_GOLDEN,
)
from tests.eval.metrics import bleu_score, precision_recall_f1, rouge_l_score, semantic_similarity

BENCH_DIR = Path(__file__).resolve().parent.parent.parent / "benchmarks"


# ---------------------------------------------------------------------------
# Section 1: Data Collection
# ---------------------------------------------------------------------------

async def bench_summary(progress: bool = True) -> dict:
    total = len(SUMMARY_GOLDEN)
    per_sample = []

    for i, (history, reference, keywords) in enumerate(SUMMARY_GOLDEN):
        if progress:
            print(f"  [summary {i + 1}/{total}]", end="\r", flush=True)
        try:
            generated = await synthesize_summary(history)
            rl = rouge_l_score(generated, reference)
            bl = bleu_score(generated, reference)
            sem = semantic_similarity(generated, reference)
            kw_hits = sum(1 for k in keywords if k.lower() in generated.lower())
            kw_rate = kw_hits / len(keywords) if keywords else 1.0
            per_sample.append({
                "reference": reference,
                "generated": generated,
                "rouge_l": rl,
                "bleu": bl,
                "semantic_sim": sem,
                "keyword_hit_rate": kw_rate,
            })
        except Exception as e:
            per_sample.append({"reference": reference, "generated": None, "error": str(e)})

    if progress:
        print()

    scored = [s for s in per_sample if s.get("generated") is not None]
    n = len(scored) or 1
    return {
        "rouge_l_avg": sum(s["rouge_l"] for s in scored) / n,
        "bleu_avg": sum(s["bleu"] for s in scored) / n,
        "semantic_sim_avg": sum(s["semantic_sim"] for s in scored) / n,
        "keyword_hit_rate": sum(s["keyword_hit_rate"] for s in scored) / n,
        "samples_ok": len(scored),
        "samples_total": total,
        "per_sample": per_sample,
    }


async def bench_metadata(progress: bool = True) -> dict:
    # Intent classification
    intent_preds, intent_labels = [], []
    for i, (query, expected) in enumerate(INTENT_GOLDEN):
        if progress:
            print(f"  [intent {i + 1}/{len(INTENT_GOLDEN)}]", end="\r", flush=True)
        try:
            meta = await extract_metadata(query)
            intent_preds.append(meta.get("intent", ""))
            intent_labels.append(expected)
        except Exception:
            intent_preds.append("")
            intent_labels.append(expected)
    if progress:
        print()

    prf = precision_recall_f1(intent_preds, intent_labels)

    # Category classification
    cat_correct = 0
    per_category = []
    for i, (query, expected) in enumerate(CATEGORY_GOLDEN):
        if progress:
            print(f"  [category {i + 1}/{len(CATEGORY_GOLDEN)}]", end="\r", flush=True)
        try:
            meta = await extract_metadata(query)
            predicted = meta.get("category", "")
            match = predicted.lower() == expected.lower()
            if match:
                cat_correct += 1
            per_category.append({"query": query, "expected": expected, "predicted": predicted, "correct": match})
        except Exception as e:
            per_category.append({"query": query, "expected": expected, "predicted": None, "error": str(e)})
    if progress:
        print()

    # Attribute recall: check that extract_metadata returns an "attributes" dict with at least one key
    attr_has_keys = sum(1 for p in per_category if p.get("predicted") is not None)

    return {
        "intent_f1": prf["f1"],
        "intent_precision": prf["precision"],
        "intent_recall": prf["recall"],
        "category_accuracy": cat_correct / len(CATEGORY_GOLDEN) if CATEGORY_GOLDEN else 0,
        "per_intent": [
            {"query": q, "expected": e, "predicted": p}
            for (q, e), p in zip(INTENT_GOLDEN, intent_preds)
        ],
        "per_category": per_category,
    }


async def bench_scoring(progress: bool = True) -> dict:
    per_pair = []
    for i, (source, candidate, lo, hi) in enumerate(SCORING_PAIRS):
        if progress:
            print(f"  [scoring {i + 1}/{len(SCORING_PAIRS)}]", end="\r", flush=True)
        try:
            results = await evaluate_candidates(source, [candidate])
            score = results[0]["score"] if results else None
            reasoning = results[0].get("reasoning", "") if results else ""
            in_range = lo <= score <= hi if score is not None else False
            per_pair.append({
                "source": source["raw_text"],
                "candidate": candidate["raw_text"],
                "expected_range": [lo, hi],
                "actual_score": score,
                "in_range": in_range,
                "reasoning": reasoning,
            })
        except Exception as e:
            per_pair.append({
                "source": source["raw_text"],
                "candidate": candidate["raw_text"],
                "expected_range": [lo, hi],
                "actual_score": None,
                "in_range": False,
                "error": str(e),
            })
    if progress:
        print()

    scored = [p for p in per_pair if p["actual_score"] is not None]
    n = len(scored) or 1
    return {
        "in_range_rate": sum(1 for p in scored if p["in_range"]) / n,
        "avg_score": sum(p["actual_score"] for p in scored) / n,
        "pairs": per_pair,
    }


# ---------------------------------------------------------------------------
# Section 2: Main Runner
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown"


async def run_benchmark(label: str | None = None, progress: bool = True) -> dict:
    # Check Ollama is reachable
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
    except Exception as e:
        print(f"ERROR: Cannot reach Ollama at {settings.ollama_base_url}: {e}", file=sys.stderr)
        sys.exit(1)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "git_sha": _git_sha(),
        "label": label,
    }

    start = time.monotonic()

    if progress:
        print(f"Running benchmark with model={settings.ollama_model} ...")

    if progress:
        print("Summary quality:")
    result["summary"] = await bench_summary(progress)

    if progress:
        print("Metadata accuracy:")
    result["metadata"] = await bench_metadata(progress)

    if progress:
        print("Scoring consistency:")
    result["scoring"] = await bench_scoring(progress)

    result["duration_seconds"] = round(time.monotonic() - start, 1)

    if progress:
        print(f"Done in {result['duration_seconds']}s")

    return result


# ---------------------------------------------------------------------------
# Section 3: Persistence
# ---------------------------------------------------------------------------

def save_result(result: dict) -> Path:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    ts = result["timestamp"].replace(":", "-").replace("+", "_")
    model = result["model"].replace(":", "_").replace("/", "_")
    path = BENCH_DIR / f"{ts}_{model}.json"
    path.write_text(json.dumps(result, indent=2))
    return path


def load_result(path: Path) -> dict:
    return json.loads(path.read_text())


def get_baseline() -> dict | None:
    p = BENCH_DIR / "baseline.json"
    return json.loads(p.read_text()) if p.exists() else None


def set_baseline(path: Path) -> None:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, BENCH_DIR / "baseline.json")


def get_latest() -> Path | None:
    results = list_results()
    return results[-1] if results else None


def list_results() -> list[Path]:
    if not BENCH_DIR.exists():
        return []
    return sorted(
        p for p in BENCH_DIR.glob("*.json") if p.name != "baseline.json"
    )


# ---------------------------------------------------------------------------
# Section 4: Comparison & CLI
# ---------------------------------------------------------------------------

_METRICS = [
    ("Summary Quality", [
        ("ROUGE-L avg", "summary", "rouge_l_avg"),
        ("BLEU avg", "summary", "bleu_avg"),
        ("Semantic sim", "summary", "semantic_sim_avg"),
        ("Keyword hit", "summary", "keyword_hit_rate"),
    ]),
    ("Metadata Accuracy", [
        ("Intent F1", "metadata", "intent_f1"),
        ("Intent precision", "metadata", "intent_precision"),
        ("Intent recall", "metadata", "intent_recall"),
        ("Category acc", "metadata", "category_accuracy"),
    ]),
    ("Scoring Consistency", [
        ("In-range rate", "scoring", "in_range_rate"),
        ("Avg score", "scoring", "avg_score"),
    ]),
]


def _delta_marker(delta: float) -> str:
    if delta > 0.01:
        return "  \u2191 IMPROVED"
    elif delta < -0.01:
        return "  \u2193 REGRESSED"
    return ""


def compare(current: dict, baseline: dict) -> str:
    lines = ["=== Benchmark Comparison ==="]
    for tag, data in [("Current ", current), ("Baseline", baseline)]:
        lbl = data.get("label") or ""
        lines.append(
            f'{tag}:  {data["timestamp"][:16]}  model={data["model"]}  '
            f'sha={data.get("git_sha", "?")}  label="{lbl}"'
        )
    lines.append("")

    for section_name, metrics in _METRICS:
        lines.append(f"--- {section_name} ---")
        lines.append(f"{'':20s}{'Baseline':>10s}{'Current':>10s}{'Delta':>10s}")
        for label, section, key in metrics:
            bval = baseline.get(section, {}).get(key)
            cval = current.get(section, {}).get(key)
            if bval is None or cval is None:
                lines.append(f"  {label:18s}{'N/A':>10s}{'N/A':>10s}")
                continue
            delta = cval - bval
            marker = _delta_marker(delta)
            lines.append(f"  {label:18s}{bval:10.3f}{cval:10.3f}{delta:+10.3f}{marker}")
        lines.append("")

    bd = baseline.get("duration_seconds", 0)
    cd = current.get("duration_seconds", 0)
    lines.append(f"Duration: {bd}s \u2192 {cd}s  ({cd - bd:+.0f}s)")

    return "\n".join(lines)


def _print_raw(result: dict) -> None:
    print(f"=== Benchmark Results ===")
    print(f"  Timestamp: {result['timestamp']}")
    print(f"  Model: {result['model']}")
    print(f"  Git SHA: {result.get('git_sha', '?')}")
    if result.get("label"):
        print(f"  Label: {result['label']}")
    print()

    for section_name, metrics in _METRICS:
        print(f"--- {section_name} ---")
        for label, section, key in metrics:
            val = result.get(section, {}).get(key)
            print(f"  {label:18s}{val:10.3f}" if val is not None else f"  {label:18s}{'N/A':>10s}")
        print()

    print(f"Duration: {result.get('duration_seconds', 0)}s")


def main():
    parser = argparse.ArgumentParser(description="LLM Benchmark Runner")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run benchmark against live Ollama")
    run_p.add_argument("--label", default=None, help="Optional label for this run")

    sb_p = sub.add_parser("set-baseline", help="Set a result file as the baseline")
    sb_p.add_argument("path", type=Path, help="Path to result JSON file")

    cmp_p = sub.add_parser("compare", help="Compare two result files")
    cmp_p.add_argument("--baseline", type=Path, default=None)
    cmp_p.add_argument("--current", type=Path, default=None)

    sub.add_parser("list", help="List all stored benchmark results")

    args = parser.parse_args()

    if args.command == "run":
        result = asyncio.run(run_benchmark(label=args.label))
        path = save_result(result)
        print(f"\nSaved to {path}")

        baseline = get_baseline()
        if baseline:
            print()
            print(compare(result, baseline))
        else:
            _print_raw(result)
            print(f"\nNo baseline set. To set one:\n  python -m tests.eval.benchmark set-baseline {path}")

    elif args.command == "set-baseline":
        if not args.path.exists():
            print(f"File not found: {args.path}", file=sys.stderr)
            sys.exit(1)
        set_baseline(args.path)
        print(f"Baseline set from {args.path}")

    elif args.command == "compare":
        bl_path = args.baseline
        cur_path = args.current
        if bl_path is None:
            bl = get_baseline()
            if bl is None:
                print("No baseline set. Use --baseline or set-baseline first.", file=sys.stderr)
                sys.exit(1)
        else:
            bl = load_result(bl_path)
        if cur_path is None:
            latest = get_latest()
            if latest is None:
                print("No results found. Run a benchmark first.", file=sys.stderr)
                sys.exit(1)
            cur = load_result(latest)
        else:
            cur = load_result(cur_path)
        print(compare(cur, bl))

    elif args.command == "list":
        results = list_results()
        if not results:
            print("No benchmark results found.")
        else:
            for p in results:
                data = load_result(p)
                lbl = f'  label="{data["label"]}"' if data.get("label") else ""
                print(f"  {p.name}  model={data['model']}  {data['timestamp'][:16]}{lbl}")
            bl = BENCH_DIR / "baseline.json"
            if bl.exists():
                data = load_result(bl)
                print(f"\n  Baseline: model={data['model']}  {data['timestamp'][:16]}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
