from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json

QUESTION_TYPES = ["summary", "authors", "date", "category", "multi_hop"]
QUESTIONS_PER_TYPE = 2
MIN_DOCUMENTS = 10


def _sample(
    question_type: str,
    question: str,
    ground_truth: str,
    doc_ids: list[str],
) -> dict[str, Any]:
    return {
        "type": question_type,
        # Giữ thêm `question_type` để tương thích với evaluation/metrics.py
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": doc_ids,
    }


def _summary_question(row: pd.Series) -> dict[str, Any]:
    return _sample(
        "summary",
        f"What is the main research contribution summarized in the paper '{row['title']}'?",
        first_sentence(row["summary"]),
        [row["paper_id"]],
    )


def _authors_question(row: pd.Series) -> dict[str, Any]:
    return _sample(
        "authors",
        f"Who authored the research on the topic '{row['title']}'?",
        row["authors_joined"],
        [row["paper_id"]],
    )


def _date_question(row: pd.Series) -> dict[str, Any]:
    return _sample(
        "date",
        f"When was the study '{row['title']}' published?",
        row["published"],
        [row["paper_id"]],
    )


def _category_question(row: pd.Series) -> dict[str, Any]:
    return _sample(
        "category",
        f"What categories (fields of expertise) does the paper '{row['title']}' belong to?",
        row["categories_joined"],
        [row["paper_id"]],
    )


def _multi_hop_question(left: pd.Series, right: pd.Series) -> dict[str, Any]:
    return _sample(
        "multi_hop",
        (
            f"Combining the {left['primary_category']} study '{left['title']}' with the "
            f"{right['primary_category']} study '{right['title']}', what does each paper contribute?"
        ),
        f"{first_sentence(left['summary'])} {first_sentence(right['summary'])}",
        [left["paper_id"], right["paper_id"]],
    )


def _pick_multi_hop_pairs(candidates: pd.DataFrame, count: int) -> list[tuple[pd.Series, pd.Series]]:
    """Ghép cặp hai bài báo không chung chuyên ngành nào để tạo câu hỏi liên ngành."""
    pairs: list[tuple[pd.Series, pd.Series]] = []
    used: set[str] = set()
    rows = [row for _, row in candidates.iterrows()]
    for i, left in enumerate(rows):
        if left["paper_id"] in used:
            continue
        for right in rows[i + 1 :]:
            if right["paper_id"] in used:
                continue
            if set(left["categories"]) & set(right["categories"]):
                continue
            pairs.append((left, right))
            used.update({left["paper_id"], right["paper_id"]})
            break
        if len(pairs) == count:
            break
    return pairs


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tạo bộ Benchmark Test Set cố định từ cleaned dataframe.

    Gồm 5 dạng câu hỏi (mỗi dạng QUESTIONS_PER_TYPE câu), mỗi bài báo chỉ dùng một lần:
    - summary: Tóm tắt nội dung nghiên cứu chính.
    - authors: Ai là tác giả của nghiên cứu về chủ đề X?
    - date: Nghiên cứu Y được công bố vào năm/tháng nào?
    - category: Công trình này thuộc lĩnh vực chuyên môn nào?
    - multi_hop: Câu hỏi kết hợp liên ngành giữa hai chủ đề (2 ground_truth_doc_ids).
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(f"Cần tối thiểu {MIN_DOCUMENTS} bài báo để tạo test set, hiện chỉ có {len(df)}.")

    # Sắp xếp theo paper_id để kết quả tất định giữa các lần chạy
    candidates = df.sort_values("paper_id").reset_index(drop=True)

    # Ưu tiên cặp multi_hop trước vì điều kiện chọn chặt hơn (khác chuyên ngành)
    pairs = _pick_multi_hop_pairs(candidates, QUESTIONS_PER_TYPE)
    if len(pairs) < QUESTIONS_PER_TYPE:
        raise ValueError("Không đủ cặp bài báo khác chuyên ngành để tạo câu hỏi multi_hop.")
    used = {row["paper_id"] for pair in pairs for row in pair}
    remaining = candidates[~candidates["paper_id"].isin(used)]

    single_builders = {
        "summary": (_summary_question, lambda r: len(r["summary"]) > 0),
        "authors": (_authors_question, lambda r: bool(r["authors_joined"])),
        "date": (_date_question, lambda r: bool(r["published"])),
        "category": (_category_question, lambda r: bool(r["categories_joined"])),
    }

    samples: list[dict[str, Any]] = []
    rows = iter(row for _, row in remaining.iterrows())
    for question_type, (builder, is_eligible) in single_builders.items():
        picked = 0
        while picked < QUESTIONS_PER_TYPE:
            row = next(rows, None)
            if row is None:
                raise ValueError(f"Không đủ bài báo hợp lệ để tạo câu hỏi dạng '{question_type}'.")
            if is_eligible(row):
                samples.append(builder(row))
                picked += 1

    samples.extend(_multi_hop_question(left, right) for left, right in pairs)

    test_set = [{"id": f"eval_{index:03d}", **sample} for index, sample in enumerate(samples, start=1)]
    write_json(output_path, test_set)
    return test_set


@dataclass(frozen=True)
class TestSet:
    path: Path
    samples: list[dict[str, Any]]


def load_or_create_test_set(df: pd.DataFrame, output_path, refresh: bool = False) -> TestSet:
    """Đọc test set cố định nếu đã có, ngược lại tạo mới bằng `build_test_set`."""
    path = Path(output_path)
    if path.exists() and not refresh:
        return TestSet(path=path, samples=read_json(path))
    return TestSet(path=path, samples=build_test_set(df, path))
