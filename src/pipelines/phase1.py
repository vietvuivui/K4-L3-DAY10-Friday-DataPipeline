from __future__ import annotations

from dataclasses import asdict
import logging

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

logger = logging.getLogger(__name__)

DEMO_QUESTION_COUNT = 2


def save_clean_artifacts(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _run_agent_demo(settings, index, test_set: list[dict]) -> None:
    """Demo agent trên vài câu hỏi mẫu; lỗi LLM không làm hỏng pipeline."""
    demo: list[dict] = []
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        for item in test_set[:DEMO_QUESTION_COUNT]:
            demo.append({"question": item["question"], "answer": str(run_agent_question(agent, item["question"]))})
    except Exception as exc:
        logger.warning("Agent demo skipped: %s", exc)
        demo.append({"skipped": f"Agent demo unavailable: {exc}"})
    write_json(settings.paths.demo_answers, demo)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    # 1-2. Ingestion: fetch từ API (có fallback snapshot) hoặc parse lại raw response đã lưu
    if settings.refresh_source or not paths.raw_api_response.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(paths.raw_api_response)
        write_json(paths.raw_records_json, [asdict(record) for record in records])
    print(f"[1/6] Ingestion: {len(records)} raw records")

    # 3-4. Cleaning
    clean_df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(clean_df, paths.clean_csv, paths.clean_json)
    print(f"[2/6] Cleaning: {len(clean_df)} clean rows -> {paths.clean_csv}")

    # 8. Quality gate trước khi index
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings)
    print(f"[3/6] Quality gate: success={quality['success']} | fresh={freshness['is_fresh']}")
    if not quality["success"]:
        logger.warning("Baseline data failed the quality gate; see %s", paths.baseline_quality_report)

    # 5. Index vào ChromaDB
    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)
    print(f"[4/6] Indexed {len(index.documents)} documents into collection '{index.collection_name}'")

    # 6. Test set cố định (chỉ tạo lại khi chưa có hoặc REFRESH_TEST_SET=1)
    if settings.refresh_test_set or not paths.eval_testset.exists():
        test_set = build_test_set(clean_df, paths.eval_testset)
    else:
        test_set = read_json(paths.eval_testset)

    # 7. Evaluate baseline
    bundle = evaluate_pipeline(settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers)
    metrics = bundle.summary
    print(
        f"[5/6] Baseline: hit_rate={metrics['retrieval_hit_rate']:.4f} | "
        f"token_f1={metrics['mean_token_f1']:.4f} | judge_acc={metrics['judge_accuracy']:.4f}"
    )

    # 9. Report
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "run_date": run_date.isoformat(),
        "raw_response": str(paths.raw_api_response.relative_to(paths.project_dir)),
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "test_set_samples": len(test_set),
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
    }
    generate_phase1_report(paths.baseline_report, source_summary, metrics, quality, freshness, bundle.answers)

    # 10. Agent demo
    _run_agent_demo(settings, index, test_set)
    print(f"[6/6] Report written to {paths.baseline_report}")
