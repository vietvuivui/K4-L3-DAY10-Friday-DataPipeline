from __future__ import annotations

import math
import random
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json

CORRUPTION_SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_RATIO = 0.25
NOISE_RATIO = 0.25
TRUNCATE_TITLE_RATIO = 0.25
STALE_DATE_RATIO = 0.35
STALE_SHIFT_YEARS = 5
TITLE_MAX_CHARS = 7  # < 10 ký tự theo yêu cầu Pha 5
NOISE_TOKENS = ["#@!", "zzxq", "��", "lorem", "ERR_0x7f", "%%%", "null", "<br/>", "qwrt"]
PREVIEW_CHARS = 80


def _pick(indices: list[int], ratio: float, rng: random.Random) -> list[int]:
    count = max(1, math.ceil(len(indices) * ratio))
    return sorted(rng.sample(indices, min(count, len(indices))))


def _noise(rng: random.Random, length: int = 8) -> str:
    return " ".join(rng.choice(NOISE_TOKENS) for _ in range(length))


def _preview(value: Any) -> str:
    text = str(value)
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "..."


def _rebuild_text(row: pd.Series) -> str:
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def _entry(corruption: str, description: str, details: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "corruption": corruption,
        "description": description,
        "affected_rows": len(details),
        "paper_ids": [item["paper_id"] for item in details],
        "details": details,
    }


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Đóng vai "kẻ thử thách có chủ đích": tiêm 6 dạng sự cố dữ liệu vào cleaned dataframe.

    1. drop_latest_records: Bỏ rơi 20% bài báo mới nhất (mất dữ liệu tươi).
    2. blank_summary: Xóa trắng summary (thiếu thông tin).
    3. inject_noise: Chèn chuỗi ký tự rác vô nghĩa vào `text_for_embedding`.
    4. truncate_title: Cắt title xuống dưới 10 ký tự.
    5. stale_date: Đổi ngày xuất bản về 5 năm trước (dữ liệu bị mốc meo).
    6. duplicate_rows: Nhân đôi một số dòng (số dòng nhân đôi = số dòng bị bỏ, nên tổng số dòng
       không đổi và một check row count đơn thuần không thể phát hiện).
    Mỗi hành động được ghi chi tiết (giá trị trước/sau) vào corruption log.
    """
    rng = random.Random(CORRUPTION_SEED)
    corrupted = df.copy(deep=True).reset_index(drop=True)
    log_entries: list[dict[str, Any]] = []

    # 1. Drop latest records
    drop_count = max(1, math.ceil(len(corrupted) * DROP_LATEST_RATIO))
    latest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_count)
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)
    log_entries.append(
        _entry(
            "drop_latest_records",
            f"Dropped the {drop_count} most recently published records ({DROP_LATEST_RATIO:.0%}).",
            [{"paper_id": row["paper_id"], "published": row["published"]} for _, row in latest.iterrows()],
        )
    )
    indices = list(range(len(corrupted)))

    # 2. Blank summary (chuỗi rỗng để GX length check bắt được, null sẽ bị bỏ qua)
    blank_idx = _pick(indices, BLANK_SUMMARY_RATIO, rng)
    blank_details = [
        {
            "paper_id": corrupted.at[i, "paper_id"],
            "summary_chars_before": len(str(corrupted.at[i, "summary"])),
            "summary_after": "",
        }
        for i in blank_idx
    ]
    corrupted.loc[blank_idx, "summary"] = ""
    log_entries.append(_entry("blank_summary", "Replaced summary with an empty string.", blank_details))

    # 3. Truncate title
    truncate_idx = _pick(indices, TRUNCATE_TITLE_RATIO, rng)
    truncate_details = []
    for i in truncate_idx:
        before = str(corrupted.at[i, "title"])
        corrupted.at[i, "title"] = before[:TITLE_MAX_CHARS]
        truncate_details.append(
            {"paper_id": corrupted.at[i, "paper_id"], "title_before": _preview(before), "title_after": corrupted.at[i, "title"]}
        )
    log_entries.append(
        _entry("truncate_title", f"Truncated title to {TITLE_MAX_CHARS} characters (< 10).", truncate_details)
    )

    # 4. Stale date: lùi đúng 5 năm theo lịch (xử lý cả năm nhuận), cập nhật age_days tương ứng
    stale_idx = _pick(indices, STALE_DATE_RATIO, rng)
    stale_details = []
    for i in stale_idx:
        before = pd.Timestamp(str(corrupted.at[i, "published"]))
        after = before - pd.DateOffset(years=STALE_SHIFT_YEARS)
        corrupted.at[i, "published"] = after.strftime("%Y-%m-%d")
        corrupted.at[i, "age_days"] = int(corrupted.at[i, "age_days"]) + (before - after).days
        stale_details.append(
            {
                "paper_id": corrupted.at[i, "paper_id"],
                "published_before": before.strftime("%Y-%m-%d"),
                "published_after": corrupted.at[i, "published"],
                "age_days_after": int(corrupted.at[i, "age_days"]),
            }
        )
    log_entries.append(_entry("stale_date", f"Moved published date back {STALE_SHIFT_YEARS} years.", stale_details))

    # Rebuild các cột phụ thuộc để blank/truncate/stale chảy vào text_for_embedding
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text, axis=1)

    # 5. Inject noise vào text_for_embedding (sau khi rebuild để không bị ghi đè).
    #    Chỉ chọn các dòng chưa bị blank để tác động của từng lỗi tách bạch.
    noise_pool = [i for i in indices if i not in blank_idx]
    noise_idx = _pick(noise_pool, NOISE_RATIO, rng)
    noise_details = []
    for i in noise_idx:
        prefix, suffix = _noise(rng), _noise(rng, 4)
        corrupted.at[i, "text_for_embedding"] = f"{prefix}\n{corrupted.at[i, 'text_for_embedding']}\n{suffix}"
        noise_details.append({"paper_id": corrupted.at[i, "paper_id"], "noise_prefix": prefix, "noise_suffix": suffix})
    log_entries.append(
        _entry("inject_noise", "Prepended and appended random garbage tokens to text_for_embedding.", noise_details)
    )

    # 6. Duplicate rows: nhân đôi đúng bằng số dòng đã bị drop
    duplicate_idx = sorted(rng.sample(indices, min(drop_count, len(indices))))
    duplicates = corrupted.loc[duplicate_idx].copy()
    log_entries.append(
        _entry(
            "duplicate_rows",
            f"Appended exact copies of {len(duplicate_idx)} existing rows.",
            [{"paper_id": paper_id} for paper_id in duplicates["paper_id"]],
        )
    )
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    # Ghi corruption log
    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "seed": CORRUPTION_SEED,
            "input_rows": len(df),
            "output_rows": len(corrupted),
            "corruption_types": len(log_entries),
            "corruptions": log_entries,
        },
    )
    return corrupted
