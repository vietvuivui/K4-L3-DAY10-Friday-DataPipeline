from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text

METRIC_LABELS = [
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "Judge Accuracy"),
    ("mean_judge_score", "Mean Judge Score (1-5)"),
]


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _expectation_table(quality: dict[str, Any]) -> list[str]:
    lines = ["| Expectation | Column | Result |", "| --- | --- | --- |"]
    for item in quality.get("expectations", []):
        column = item.get("kwargs", {}).get("column", "-")
        lines.append(f"| `{item['expectation_type']}` | {column} | {_fmt(bool(item['success']))} |")
    return lines


def _type_breakdown(answers: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in answers:
        grouped.setdefault(item.get("question_type", "unknown"), []).append(item)
    lines = ["| Question type | Samples | Hit rate | Mean Token F1 |", "| --- | ---: | ---: | ---: |"]
    for question_type, items in grouped.items():
        hit = sum(1 for i in items if i["retrieval_hit"]) / len(items)
        f1 = sum(i["token_f1"] for i in items) / len(items)
        lines.append(f"| {question_type} | {len(items)} | {hit:.4f} | {f1:.4f} |")
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> None:
    """Viết markdown report cho baseline phase: nguồn dữ liệu, metrics, data quality, freshness."""
    lines = [
        "# Phase 1 Report - Baseline Pipeline",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Source & Lineage",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in source_summary.items()]

    lines += [
        "",
        "## 2. Retrieval & Answer Quality (Baseline)",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    lines += [f"| {label} | {_fmt(metrics.get(key))} |" for key, label in METRIC_LABELS]
    lines.append(f"| Samples | {metrics.get('samples')} |")
    if answers:
        lines += ["", "### Breakdown by question type", ""] + _type_breakdown(answers)

    lines += [
        "",
        "## 3. Data Quality Gate (Great Expectations 1.x)",
        "",
        f"- Overall status: **{_fmt(bool(quality.get('success')))}** "
        f"(GX: {_fmt(bool(quality.get('gx_success')))}, fresh: {_fmt(bool(quality.get('is_fresh')))})",
        f"- Rows validated: {quality.get('total_rows')}",
        "",
    ]
    lines += _expectation_table(quality)

    lines += [
        "",
        "## 4. Freshness SLA",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in freshness.items()]
    lines += [
        "",
        "## 5. Conclusion",
        "",
        (
            "Baseline data passes the quality gate and freshness SLA; these metrics are the reference "
            "point for the corruption experiment."
            if quality.get("success")
            else "Baseline data did NOT pass the quality gate; investigate before using these metrics as reference."
        ),
        "",
    ]
    write_text(report_path, "\n".join(lines))


def _delta(value: Any, reference: Any) -> str:
    if isinstance(value, (int, float)) and isinstance(reference, (int, float)):
        return f"{value - reference:+.4f}"
    return "-"


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    corruption_log: dict[str, Any] | None = None,
) -> None:
    """Viết markdown report so sánh 3 trạng thái Baseline / Corrupted / Repaired."""
    lines = [
        "# Corruption Report - Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Performance Comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in METRIC_LABELS:
        base, corr, rep = baseline_metrics.get(key), corrupted_metrics.get(key), repaired_metrics.get(key)
        lines.append(
            f"| {label} | {_fmt(base)} | {_fmt(corr)} | {_fmt(rep)} | {_delta(corr, base)} | {_delta(rep, base)} |"
        )

    if corruption_log:
        lines += [
            "",
            "## 2. Injected Corruptions",
            "",
            f"Input rows: {corruption_log.get('input_rows')} → corrupted rows: {corruption_log.get('output_rows')} "
            f"(seed={corruption_log.get('seed')})",
            "",
            "| Corruption | Affected rows | Description |",
            "| --- | ---: | --- |",
        ]
        for item in corruption_log.get("corruptions", []):
            lines.append(f"| `{item['corruption']}` | {item['affected_rows']} | {item['description']} |")

    lines += [
        "",
        "## 3. Data Quality Gate",
        "",
        "| Check | Corrupted | Repaired |",
        "| --- | --- | --- |",
        f"| Overall | {_fmt(bool(corrupted_quality.get('success')))} | {_fmt(bool(repaired_quality.get('success')))} |",
        f"| Rows | {corrupted_quality.get('total_rows')} | {repaired_quality.get('total_rows')} |",
    ]
    repaired_by_key = {
        (e["expectation_type"], e.get("kwargs", {}).get("column")): e["success"]
        for e in repaired_quality.get("expectations", [])
    }
    for item in corrupted_quality.get("expectations", []):
        column = item.get("kwargs", {}).get("column")
        repaired_success = repaired_by_key.get((item["expectation_type"], column))
        name = f"`{item['expectation_type']}`" + (f" ({column})" if column else "")
        lines.append(f"| {name} | {_fmt(bool(item['success']))} | {_fmt(bool(repaired_success))} |")

    lines += [
        "",
        "## 4. Freshness SLA",
        "",
        "| Field | Corrupted | Repaired |",
        "| --- | --- | --- |",
    ]
    for key in corrupted_freshness:
        lines.append(f"| {key} | {_fmt(corrupted_freshness.get(key))} | {_fmt(repaired_freshness.get(key))} |")

    hit_drop = (baseline_metrics.get("retrieval_hit_rate", 0) or 0) - (corrupted_metrics.get("retrieval_hit_rate", 0) or 0)
    f1_drop = (baseline_metrics.get("mean_token_f1", 0) or 0) - (corrupted_metrics.get("mean_token_f1", 0) or 0)
    recovered = all(
        abs((repaired_metrics.get(key) or 0) - (baseline_metrics.get(key) or 0)) < 1e-9
        for key in ("retrieval_hit_rate", "mean_token_f1")
    )
    lines += [
        "",
        "## 5. Impact Analysis",
        "",
        f"- **Silent failure:** the pipeline still ran end-to-end on corrupted data, but retrieval hit rate fell by "
        f"{hit_drop:.4f} and mean token F1 fell by {f1_drop:.4f}. Nothing crashed, so without monitoring the "
        "agent would keep serving wrong answers.",
        "- **Root causes:** dropped latest records remove ground-truth documents from the index; truncated titles "
        "break exact title lookup; blank or noisy summaries corrupt both embeddings and extracted answers; stale "
        "dates return wrong publication dates.",
        f"- **Detection:** the quality gate flagged the corrupted batch as "
        f"**{_fmt(bool(corrupted_quality.get('success')))}** (freshness: "
        f"{_fmt(bool(corrupted_freshness.get('is_fresh')))}), so it should be blocked before indexing.",
        f"- **Repair:** rebuilding from the preserved raw artifact (`data/raw/crossref_records.json`) is idempotent "
        f"and {'fully restores' if recovered else 'does NOT fully restore'} baseline retrieval hit rate and token F1.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
