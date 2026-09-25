# Corruption Report - Baseline vs Corrupted vs Repaired

_Generated at: 2026-09-25T09:25:12.137617+00:00_

## 1. Performance Comparison

| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Retrieval Hit Rate | 1.0000 | 0.6000 | 1.0000 | -0.4000 | +0.0000 |
| Mean Token F1 | 0.9219 | 0.6346 | 0.9219 | -0.2873 | +0.0000 |
| Judge Accuracy | 1.0000 | 0.7000 | 1.0000 | -0.3000 | +0.0000 |
| Mean Judge Score (1-5) | 4.6000 | 3.4000 | 4.6000 | -1.2000 | +0.0000 |

## 2. Injected Corruptions

Input rows: 24 → corrupted rows: 23 (seed=42)

| Corruption | Affected rows | Description |
| --- | ---: | --- |
| `drop_latest_records` | 5 | Dropped the 5 most recently published records. |
| `blank_summary` | 5 | Replaced summary with an empty string. |
| `inject_noise` | 4 | Prepended and appended random garbage tokens to summary. |
| `truncate_title` | 5 | Truncated title to 7 characters. |
| `stale_date` | 7 | Shifted published date back by 365 days. |
| `duplicate_rows` | 4 | Appended exact copies of existing rows. |

## 3. Data Quality Gate

| Check | Corrupted | Repaired |
| --- | --- | --- |
| Overall | FAIL | PASS |
| Rows | 23 | 24 |
| `expect_table_row_count_to_be_between` | PASS | PASS |
| `expect_column_values_to_not_be_null` (paper_id) | PASS | PASS |
| `expect_column_values_to_be_unique` (paper_id) | FAIL | PASS |
| `expect_column_values_to_not_be_null` (title) | PASS | PASS |
| `expect_column_values_to_not_be_null` (text_for_embedding) | PASS | PASS |
| `expect_column_value_lengths_to_be_between` (summary) | FAIL | PASS |

## 4. Freshness SLA

| Field | Corrupted | Repaired |
| --- | --- | --- |
| latest_published | 2026-08-27 | 2026-09-15 |
| oldest_published | 2025-04-01 | 2026-04-01 |
| stale_rows | 8 | 0 |
| total_rows | 23 | 24 |
| stale_ratio | 0.3478 | 0.0000 |
| threshold_days | 180 | 180 |
| max_stale_ratio | 0.2500 | 0.2500 |
| is_fresh | FAIL | PASS |

## 5. Impact Analysis

- **Silent failure:** the pipeline still ran end-to-end on corrupted data, but retrieval hit rate fell by 0.4000 and mean token F1 fell by 0.2873. Nothing crashed, so without monitoring the agent would keep serving wrong answers.
- **Root causes:** dropped latest records remove ground-truth documents from the index; truncated titles break exact title lookup; blank or noisy summaries corrupt both embeddings and extracted answers; stale dates return wrong publication dates.
- **Detection:** the quality gate flagged the corrupted batch as **FAIL** (freshness: FAIL), so it should be blocked before indexing.
- **Repair:** rebuilding from the preserved raw artifact (`data/raw/crossref_records.json`) is idempotent and fully restores baseline retrieval hit rate and token F1.
