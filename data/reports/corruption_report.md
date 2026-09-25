# Corruption Report - Baseline vs Corrupted vs Repaired

_Generated at: 2026-09-25T10:05:09.784732+00:00_

## 0. Bảng đối chiếu 3 trạng thái (nghiệm thu)

| Metric / Chỉ số | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Bị Lỗi) | Repaired (Sau Khi Phục Hồi) |
| --- | --- | --- | --- |
| Data Quality Gate | ✅ PASSED (6/6) | ❌ FAILED (2/6 expectations lỗi) | ✅ PASSED (6/6) |
| Kiểm tra Độ Tươi (Freshness) | ✅ Đạt chuẩn (0% bài > 180 ngày) | ❌ Vi phạm (38% bài > 180 ngày, ngưỡng 25%) | ✅ Đạt chuẩn (0% bài > 180 ngày) |
| Retrieval Hit Rate | 1.0000 | 0.8000 | 1.0000 |
| Mean Token F1 | 0.9219 | 0.7219 | 0.9219 |

## 1. Performance Comparison

| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Retrieval Hit Rate | 1.0000 | 0.8000 | 1.0000 | -0.2000 | +0.0000 |
| Mean Token F1 | 0.9219 | 0.7219 | 0.9219 | -0.2000 | +0.0000 |
| Judge Accuracy | 0.8000 | 0.6000 | 0.8000 | -0.2000 | +0.0000 |
| Mean Judge Score (1-5) | 4.4000 | 3.6000 | 4.4000 | -0.8000 | +0.0000 |

## 2. Injected Corruptions

Input rows: 24 → corrupted rows: 24 (seed=42)

| Corruption | Affected rows | Description |
| --- | ---: | --- |
| `drop_latest_records` | 5 | Dropped the 5 most recently published records (20%). |
| `blank_summary` | 5 | Replaced summary with an empty string. |
| `truncate_title` | 5 | Truncated title to 7 characters (< 10). |
| `stale_date` | 7 | Moved published date back 5 years. |
| `inject_noise` | 4 | Prepended and appended random garbage tokens to text_for_embedding. |
| `duplicate_rows` | 5 | Appended exact copies of 5 existing rows. |

## 3. Data Quality Gate

| Check | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Overall | PASS | FAIL | PASS |
| Rows | 24 | 24 | 24 |
| `expect_table_row_count_to_be_between` | PASS | PASS | PASS |
| `expect_column_values_to_not_be_null` (paper_id) | PASS | PASS | PASS |
| `expect_column_values_to_be_unique` (paper_id) | PASS | FAIL | PASS |
| `expect_column_values_to_not_be_null` (title) | PASS | PASS | PASS |
| `expect_column_values_to_not_be_null` (text_for_embedding) | PASS | PASS | PASS |
| `expect_column_value_lengths_to_be_between` (summary) | PASS | FAIL | PASS |

## 4. Freshness SLA

| Field | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| latest_published | 2026-09-15 | 2026-08-26 | 2026-09-15 |
| oldest_published | 2026-04-01 | 2021-04-01 | 2026-04-01 |
| stale_rows | 0 | 9 | 0 |
| total_rows | 24 | 24 | 24 |
| stale_ratio | 0.0000 | 0.3750 | 0.0000 |
| threshold_days | 180 | 180 | 180 |
| max_stale_ratio | 0.2500 | 0.2500 | 0.2500 |
| is_fresh | PASS | FAIL | PASS |

## 5. Impact Analysis

- **Silent failure:** the pipeline still ran end-to-end on corrupted data, but retrieval hit rate fell by 0.2000 and mean token F1 fell by 0.2000. Nothing crashed, so without monitoring the agent would keep serving wrong answers.
- **Root causes:** dropped latest records remove ground-truth documents from the index; truncated titles break exact title lookup; blank summaries corrupt both embeddings and extracted answers; noise injected into `text_for_embedding` distorts the vectors used for retrieval; stale dates (5 years back) return wrong publication dates; duplicate rows crowd the top-k results.
- **Detection:** the quality gate flagged the corrupted batch as **FAIL** (freshness: FAIL), so it should be blocked before indexing.
- **Repair:** rebuilding from the preserved raw artifact (`data/raw/crossref_records.json`) is idempotent and fully restores baseline retrieval hit rate and token F1.
