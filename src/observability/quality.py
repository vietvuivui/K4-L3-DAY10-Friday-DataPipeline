from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

logger = logging.getLogger(__name__)


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Dựng trạm kiểm soát dữ liệu (Data Quality Gate) với Great Expectations 1.x và Freshness SLA.

    Thiết lập 4 kỳ vọng (Expectations) bắt buộc theo chuẩn GX 1.x:
    1. ExpectTableRowCountToBeBetween: Số lượng bài báo hợp lệ (5 đến 5000).
    2. ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding không được phép để trống.
    3. ExpectColumnValuesToBeUnique: paper_id là khóa duy nhất, không trùng lặp.
    4. ExpectColumnValueLengthsToBeBetween: Trường summary có độ dài tối thiểu 30 ký tự.
    5. Kiểm tra độ tươi mới (Freshness Check):
       Nếu tỉ lệ bài báo cũ (age_days > 180 ngày) vượt quá 25% thì cảnh báo và đánh dấu is_fresh = False.
    """
    # Khởi tạo ephemeral context (chạy trên RAM, không sinh file rác)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")

    # Thiết lập Expectation Suite
    suite = gx.ExpectationSuite(name=f"papers_{report_name}_suite")

    # 1. ExpectTableRowCountToBeBetween: 5 đến 5000 dòng
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))

    # 2. ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))

    # 3. ExpectColumnValuesToBeUnique: paper_id là khóa duy nhất
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))

    # 4. ExpectColumnValueLengthsToBeBetween: summary tối thiểu 30 ký tự
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    context.suites.add(suite)

    # Validation Definition & Run
    val_def = gx.ValidationDefinition(
        name=f"papers_{report_name}_validation",
        data=batch_def,
        suite=suite,
    )
    context.validation_definitions.add(val_def)
    gx_results = val_def.run(batch_parameters={"dataframe": df})

    # Freshness Check
    threshold_days = settings.freshness_threshold_days
    total_rows = len(df)
    stale_rows = int((df["age_days"] > threshold_days).sum()) if "age_days" in df.columns else 0
    stale_ratio = float(stale_rows / total_rows) if total_rows > 0 else 0.0
    is_fresh = stale_ratio <= 0.25

    if not is_fresh:
        logger.warning(
            "Cảnh báo độ tươi mới: Tỉ lệ bài báo cũ (age_days > %d) là %.2f%%, vượt quá ngưỡng cho phép 25%%!",
            threshold_days,
            stale_ratio * 100,
        )

    overall_success = bool(gx_results.success and is_fresh)

    expectations_results = []
    for r in gx_results.results:
        expectations_results.append(
            {
                "expectation_type": r.expectation_config.type,
                "success": bool(r.success),
                "kwargs": r.expectation_config.kwargs,
                "result": r.result,
            }
        )

    report_payload = {
        "success": overall_success,
        "gx_success": bool(gx_results.success),
        "is_fresh": is_fresh,
        "report_name": report_name,
        "evaluated_at": now_utc().isoformat(),
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": threshold_days,
        "expectations": expectations_results,
    }

    # Xác định đường dẫn file báo cáo
    if report_name == "baseline":
        output_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        output_path = settings.paths.corrupted_quality_report
    else:
        output_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    write_json(output_path, report_payload)
    return report_payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str | None = None) -> dict[str, Any]:
    """Tổng hợp freshness report chi tiết và lưu ra file JSON."""
    threshold_days = settings.freshness_threshold_days
    total_rows = len(df)
    stale_rows = int((df["age_days"] > threshold_days).sum()) if "age_days" in df.columns else 0
    stale_ratio = float(stale_rows / total_rows) if total_rows > 0 else 0.0
    is_fresh = stale_ratio <= 0.25

    latest_published = str(df["published"].max()) if not df.empty and "published" in df.columns else ""
    oldest_published = str(df["published"].min()) if not df.empty and "published" in df.columns else ""

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": threshold_days,
        "max_stale_ratio": 0.25,
        "is_fresh": is_fresh,
    }

    target = Path(report_path) if report_path else settings.paths.freshness_report
    write_json(target, payload)
    return payload
