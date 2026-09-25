from __future__ import annotations

import logging

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import save_clean_artifacts
from retrieval.index import LocalEmbeddingIndex

METRIC_KEYS = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]


def _print_comparison(baseline: dict, corrupted: dict, repaired: dict) -> None:
    print()
    print(f"{'Metric':<22}{'Baseline':>12}{'Corrupted':>12}{'Repaired':>12}")
    print("-" * 58)
    for key in METRIC_KEYS:
        print(f"{key:<22}{baseline[key]:>12.4f}{corrupted[key]:>12.4f}{repaired[key]:>12.4f}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    paths = settings.paths

    # 1. Load baseline metrics và clean dataset (yêu cầu đã chạy Phase 1)
    for required in (paths.baseline_metrics, paths.clean_json, paths.eval_testset, paths.raw_records_json):
        if not required.exists():
            raise FileNotFoundError(f"Missing {required}. Run `python script/run_phase1.py` first.")
    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.DataFrame(read_json(paths.clean_json))

    # 2-3. Tiêm lỗi và lưu corrupted artifacts
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    save_clean_artifacts(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    print(f"[1/5] Corrupted dataset: {len(clean_df)} -> {len(corrupted_df)} rows (log: {paths.corruption_log})")

    # 5. Quality gate + freshness trên dữ liệu bẩn
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(
        f"[2/5] Corrupted quality gate: success={corrupted_quality['success']} | "
        f"fresh={corrupted_freshness['is_fresh']}"
    )

    # 4. Cố tình index dữ liệu bẩn để đo silent failure
    corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, paths.corrupted_embeddings_json)
    corrupted_metrics = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers
    ).summary
    print(f"[3/5] Corrupted evaluation done -> {paths.corrupted_metrics}")

    # 6. Repair idempotent: rebuild từ raw artifact đã lưu, ghi đè dữ liệu hỏng
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    save_clean_artifacts(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )
    if not repaired_quality["success"]:
        raise RuntimeError("Repaired dataset still fails the quality gate; refusing to index it.")

    # 7. Evaluate repaired dataset
    repaired_index = LocalEmbeddingIndex.build(repaired_df, settings, paths.repaired_embeddings_json)
    repaired_metrics = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset, paths.repaired_metrics, paths.repaired_answers
    ).summary
    print(f"[4/5] Repaired dataset: {len(repaired_df)} rows, quality gate success={repaired_quality['success']}")

    # 8. Comparison report
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        corruption_log=read_json(paths.corruption_log),
        baseline_quality=read_json(paths.baseline_quality_report) if paths.baseline_quality_report.exists() else None,
        baseline_freshness=read_json(paths.freshness_report) if paths.freshness_report.exists() else None,
    )
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics)
    print(f"[5/5] Comparison report written to {paths.comparison_report}")
