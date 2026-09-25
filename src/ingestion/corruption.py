from __future__ import annotations

from datetime import datetime, timedelta
import math
import random

import pandas as pd

from core.utils import now_utc, write_json

CORRUPTION_SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_RATIO = 0.25
NOISE_RATIO = 0.25
TRUNCATE_TITLE_RATIO = 0.25
STALE_DATE_RATIO = 0.35
DUPLICATE_RATIO = 0.20
STALE_SHIFT_DAYS = 365
TITLE_MAX_CHARS = 7
NOISE_TOKENS = ["#@!", "zzxq", "��", "lorem", "ERR_0x7f", "%%%", "null", "<br/>", "qwrt"]


def _pick(indices: list[int], ratio: float, rng: random.Random) -> list[int]:
    count = max(1, math.ceil(len(indices) * ratio))
    return sorted(rng.sample(indices, min(count, len(indices))))


def _noise(rng: random.Random, length: int = 8) -> str:
    return " ".join(rng.choice(NOISE_TOKENS) for _ in range(length))


def _rebuild_text(row: pd.Series) -> str:
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Mô phỏng 6 dạng sự cố dữ liệu thường gặp trên cleaned dataframe.

    1. drop_latest_records: Bỏ 20% bài báo mới nhất (mất dữ liệu tươi).
    2. blank_summary: Xóa trắng summary (lỗi cào dữ liệu rỗng).
    3. inject_noise: Chèn chuỗi ký tự rác vào đầu summary.
    4. truncate_title: Cắt title xuống dưới 8 ký tự.
    5. stale_date: Lùi ngày xuất bản 365 ngày (dữ liệu bị mốc).
    6. duplicate_rows: Nhân đôi một số dòng.
    Sau đó rebuild `text_for_embedding` và ghi corruption log.
    """
    rng = random.Random(CORRUPTION_SEED)
    corrupted = df.copy(deep=True).reset_index(drop=True)
    log_entries: list[dict] = []

    # 1. Drop latest records
    drop_count = max(1, math.ceil(len(corrupted) * DROP_LATEST_RATIO))
    latest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_count)
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)
    log_entries.append(
        {
            "corruption": "drop_latest_records",
            "description": f"Dropped the {drop_count} most recently published records.",
            "affected_rows": drop_count,
            "paper_ids": latest["paper_id"].tolist(),
        }
    )
    indices = list(range(len(corrupted)))

    # 2. Blank summary (chuỗi rỗng để GX length check bắt được, null sẽ bị bỏ qua)
    blank_idx = _pick(indices, BLANK_SUMMARY_RATIO, rng)
    corrupted.loc[blank_idx, "summary"] = ""
    log_entries.append(
        {
            "corruption": "blank_summary",
            "description": "Replaced summary with an empty string.",
            "affected_rows": len(blank_idx),
            "paper_ids": corrupted.loc[blank_idx, "paper_id"].tolist(),
        }
    )

    # 3. Inject noise vào những dòng chưa bị blank
    noise_pool = [i for i in indices if i not in blank_idx]
    noise_idx = _pick(noise_pool, NOISE_RATIO, rng)
    for i in noise_idx:
        corrupted.at[i, "summary"] = f"{_noise(rng)} {corrupted.at[i, 'summary']} {_noise(rng, 4)}"
    log_entries.append(
        {
            "corruption": "inject_noise",
            "description": "Prepended and appended random garbage tokens to summary.",
            "affected_rows": len(noise_idx),
            "paper_ids": corrupted.loc[noise_idx, "paper_id"].tolist(),
        }
    )

    # 4. Truncate title
    truncate_idx = _pick(indices, TRUNCATE_TITLE_RATIO, rng)
    for i in truncate_idx:
        corrupted.at[i, "title"] = str(corrupted.at[i, "title"])[:TITLE_MAX_CHARS]
    log_entries.append(
        {
            "corruption": "truncate_title",
            "description": f"Truncated title to {TITLE_MAX_CHARS} characters.",
            "affected_rows": len(truncate_idx),
            "paper_ids": corrupted.loc[truncate_idx, "paper_id"].tolist(),
        }
    )

    # 5. Stale date
    stale_idx = _pick(indices, STALE_DATE_RATIO, rng)
    for i in stale_idx:
        published = datetime.strptime(str(corrupted.at[i, "published"]), "%Y-%m-%d")
        corrupted.at[i, "published"] = (published - timedelta(days=STALE_SHIFT_DAYS)).strftime("%Y-%m-%d")
        corrupted.at[i, "age_days"] = int(corrupted.at[i, "age_days"]) + STALE_SHIFT_DAYS
    log_entries.append(
        {
            "corruption": "stale_date",
            "description": f"Shifted published date back by {STALE_SHIFT_DAYS} days.",
            "affected_rows": len(stale_idx),
            "paper_ids": corrupted.loc[stale_idx, "paper_id"].tolist(),
        }
    )

    # 6. Duplicate rows
    duplicate_idx = _pick(indices, DUPLICATE_RATIO, rng)
    duplicates = corrupted.loc[duplicate_idx].copy()
    log_entries.append(
        {
            "corruption": "duplicate_rows",
            "description": "Appended exact copies of existing rows.",
            "affected_rows": len(duplicate_idx),
            "paper_ids": duplicates["paper_id"].tolist(),
        }
    )
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    # 7. Rebuild các cột phụ thuộc
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text, axis=1)

    # 8. Ghi corruption log
    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "seed": CORRUPTION_SEED,
            "input_rows": len(df),
            "output_rows": len(corrupted),
            "corruptions": log_entries,
        },
    )
    return corrupted
