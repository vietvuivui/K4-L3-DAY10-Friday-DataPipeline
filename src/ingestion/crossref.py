from __future__ import annotations

from dataclasses import asdict, dataclass
import html
import logging
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(value: str) -> str:
    """Loại bỏ thẻ HTML/JATS XML rác, giải mã thực thể HTML và chuẩn hóa khoảng trắng."""
    if not value:
        return ""
    stripped = re.sub(r"<[^>]+>", "", value)
    unescaped = html.unescape(stripped)
    return normalize_whitespace(unescaped)


def _normalize_doi(raw_doi: str) -> str:
    """Chuẩn hóa mã định danh DOI."""
    doi = raw_doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/"):]
    elif doi.startswith("doi:"):
        doi = doi[len("doi:"):]
    return doi.strip()


def _parse_iso_date(date_val: Any) -> str:
    """Parse định dạng ngày Crossref thành chuẩn ISO 8601 (YYYY-MM-DD)."""
    if not date_val:
        return ""
    if isinstance(date_val, dict):
        date_parts = date_val.get("date-parts")
        if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
            parts = date_parts[0]
            if isinstance(parts, list) and len(parts) > 0:
                try:
                    if len(parts) >= 3:
                        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                    elif len(parts) == 2:
                        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-01"
                    elif len(parts) == 1:
                        return f"{int(parts[0]):04d}-01-01"
                except (ValueError, TypeError):
                    pass
        date_time = date_val.get("date-time")
        if date_time and isinstance(date_time, str):
            return date_time.split("T")[0]
    elif isinstance(date_val, str):
        val = date_val.strip()
        if "T" in val:
            return val.split("T")[0]
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", val)
        if match:
            return match.group(0)
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thành danh sách PaperRecord.

    Bóc tách các trường:
    - paper_id: Lấy DOI chuẩn hóa.
    - title: Chuẩn hóa khoảng trắng.
    - summary: Loại bỏ các thẻ HTML/JATS XML rác (như <jats:p>, </jats:p>).
    - authors: Danh sách tác giả chuẩn hóa họ tên.
    - categories, primary_category: Chuyên ngành.
    - published, updated: Định dạng ngày chuẩn ISO 8601 (YYYY-MM-DD).
    - Bỏ qua các bản ghi không hợp lệ (thiếu DOI, title hoặc summary).
    """
    items: list[dict] = []
    if isinstance(payload, dict):
        if "message" in payload and isinstance(payload["message"], dict):
            items = payload["message"].get("items", [])
        elif "items" in payload and isinstance(payload["items"], list):
            items = payload["items"]
    elif isinstance(payload, list):
        items = payload

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # paper_id: Lấy DOI chuẩn hóa
        raw_doi = item.get("DOI", "")
        if not raw_doi or not isinstance(raw_doi, str):
            continue
        paper_id = _normalize_doi(raw_doi)
        if not paper_id:
            continue

        # title: Chuẩn hóa khoảng trắng
        titles = item.get("title", [])
        raw_title = ""
        if isinstance(titles, list) and titles:
            raw_title = str(titles[0])
        elif isinstance(titles, str):
            raw_title = titles
        title = _clean_text(raw_title)
        if not title:
            continue

        # summary: Loại bỏ các thẻ HTML/JATS XML rác
        raw_summary = item.get("abstract", "") or item.get("summary", "") or ""
        if isinstance(raw_summary, list) and raw_summary:
            raw_summary = str(raw_summary[0])
        elif not isinstance(raw_summary, str):
            raw_summary = str(raw_summary)
        summary = _clean_text(raw_summary)
        if not summary:
            continue

        # authors
        authors: list[str] = []
        raw_authors = item.get("author", [])
        if isinstance(raw_authors, list):
            for a in raw_authors:
                if isinstance(a, dict):
                    given = _clean_text(str(a.get("given", "")))
                    family = _clean_text(str(a.get("family", "")))
                    name = normalize_whitespace(f"{given} {family}").strip()
                    if not name:
                        name = _clean_text(str(a.get("name", "")))
                elif isinstance(a, str):
                    name = _clean_text(a)
                else:
                    name = ""
                if name:
                    authors.append(name)

        # categories & primary_category
        raw_subjects = item.get("subject", [])
        if isinstance(raw_subjects, list):
            categories = [_clean_text(str(s)) for s in raw_subjects if _clean_text(str(s))]
        elif isinstance(raw_subjects, str) and raw_subjects.strip():
            categories = [_clean_text(raw_subjects)]
        else:
            categories = []
        primary_category = categories[0] if categories else ""

        # published: Parse định dạng ngày ISO 8601 (YYYY-MM-DD)
        published = (
            _parse_iso_date(item.get("published"))
            or _parse_iso_date(item.get("published-online"))
            or _parse_iso_date(item.get("published-print"))
            or _parse_iso_date(item.get("created"))
            or _parse_iso_date(item.get("issued"))
        )

        # updated: Parse định dạng ngày ISO 8601 (YYYY-MM-DD)
        updated = (
            _parse_iso_date(item.get("updated"))
            or _parse_iso_date(item.get("created"))
            or _parse_iso_date(item.get("deposited"))
            or published
        )

        url = str(item.get("URL", "")).strip() or f"https://doi.org/{paper_id}"
        abs_url = url
        pdf_url = url
        comment = f"Crossref record {paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi source API, lưu raw response, parse thành records.

    Cơ chế Cứu hộ Offline (Dual-Mode):
    Nếu API Crossref bị quá tải (mã lỗi 429) hoặc phòng lab mất mạng,
    pipeline tự động chuyển sang đọc snapshot mẫu có sẵn tại data/raw/crossref_response.json
    để việc học không bị gián đoạn.
    """
    payload: dict[str, Any] | None = None
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "User-Agent": "DataObservabilityLab/1.0 (mailto:student@lab.edu)"
    }

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            resp = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                if items:
                    payload = data
                    write_json(settings.paths.raw_api_response, payload)
                    break
                else:
                    logger.warning("Crossref API returned empty items list.")
                    break
            elif resp.status_code in {429, 503}:
                logger.warning(
                    "Crossref API status %d (quá tải / giới hạn tốc độ). Lần thử %d/%d.",
                    resp.status_code,
                    attempt + 1,
                    max_retries,
                )
                # Khi gặp 429 trong phòng lab hoặc quá tải, chuyển ngay sang chế độ cứu hộ
                if resp.status_code == 429:
                    break
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
            else:
                logger.warning("Crossref API trả về mã lỗi HTTP %d.", resp.status_code)
                break
        except requests.RequestException as exc:
            logger.warning(
                "Lỗi kết nối Crossref API: %s. Lần thử %d/%d.",
                exc,
                attempt + 1,
                max_retries,
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))

    # Cơ chế Cứu hộ Offline (Dual-Mode):
    if payload is None:
        if settings.paths.raw_api_response.exists():
            print(
                f"[Dual-Mode Rescue] API Crossref quá tải (429) hoặc phòng lab mất mạng. "
                f"Tự động chuyển sang đọc snapshot mẫu có sẵn tại {settings.paths.raw_api_response}"
            )
            payload = read_json(settings.paths.raw_api_response)
        else:
            raise RuntimeError(
                f"Không thể kết nối Crossref API và không tìm thấy snapshot mẫu tại {settings.paths.raw_api_response}"
            )

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và map thành danh sách `PaperRecord`."""
    data = read_json(path)
    if isinstance(data, dict) and "message" in data:
        return parse_crossref_payload(data)
    if isinstance(data, list):
        return [PaperRecord(**item) for item in data]
    raise ValueError(f"Unsupported payload format in {path}")
