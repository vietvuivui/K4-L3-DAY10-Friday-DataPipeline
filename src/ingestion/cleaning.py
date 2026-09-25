from __future__ import annotations

from datetime import datetime, timezone
import logging

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord

logger = logging.getLogger(__name__)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Làm sạch và chuẩn hóa danh sách raw PaperRecord thành DataFrame sẵn sàng để embed.

    Các bước thực hiện:
    1. Chuẩn hóa title, summary, authors, categories.
    2. Parse published date và tính toán độ tươi của dữ liệu:
       age_days = (run_date - published).days
    3. Tạo các cột helper:
       - authors_joined: Ghép tên các tác giả bằng dấu phẩy
       - categories_joined: Ghép các chuyên ngành bằng dấu phẩy
       - summary_chars: Số lượng ký tự trong summary
       - text_for_embedding: Đoạn văn bản hoàn chỉnh để nhúng vector:
         Title: <Tiêu đề>
         Authors: <Danh sách tác giả>
         Published: <Ngày xuất bản>
         Categories: <Chuyên ngành>
         Summary: <Tóm tắt nội dung>
    4. Khử trùng lặp bản ghi theo khóa duy nhất paper_id và lọc bỏ bản ghi không hợp lệ.
    5. Sắp xếp dataframe và trả về.
    """
    rows = []
    ref_date = run_date.date() if isinstance(run_date, datetime) else run_date

    for r in records:
        if not r.paper_id or not r.title or not r.summary:
            continue

        paper_id = r.paper_id.strip()
        title = normalize_whitespace(r.title)
        summary = normalize_whitespace(r.summary)

        # Lọc bỏ bài có summary quá ngắn (< 30 ký tự) theo tiêu chuẩn chất lượng
        if len(summary) < 30:
            continue

        # Parse published date và tính age_days
        try:
            pub_date = datetime.strptime(r.published.strip(), "%Y-%m-%d").date()
            age_days = max(0, (ref_date - pub_date).days)
        except Exception:
            age_days = 0

        authors = [normalize_whitespace(a) for a in r.authors if normalize_whitespace(a)]
        authors_joined = ", ".join(authors)

        categories = [normalize_whitespace(c) for c in r.categories if normalize_whitespace(c)]
        categories_joined = ", ".join(categories)

        summary_chars = len(summary)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {r.published.strip()}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": r.primary_category.strip() if r.primary_category else (categories[0] if categories else ""),
                "published": r.published.strip(),
                "updated": r.updated.strip() if r.updated else r.published.strip(),
                "abs_url": r.abs_url.strip(),
                "pdf_url": r.pdf_url.strip(),
                "comment": r.comment.strip(),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "paper_id",
                "title",
                "summary",
                "authors",
                "categories",
                "primary_category",
                "published",
                "updated",
                "abs_url",
                "pdf_url",
                "comment",
                "authors_joined",
                "categories_joined",
                "summary_chars",
                "age_days",
                "text_for_embedding",
            ]
        )

    df = pd.DataFrame(rows)

    # 4. Khử trùng lặp bản ghi theo khóa duy nhất paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # 5. Sắp xếp dataframe theo ngày xuất bản giảm dần và paper_id
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)

    return df
