# Phase 1 Report - Baseline Pipeline

_Generated at: 2026-09-25T09:24:39.582007+00:00_

## 1. Source & Lineage

| Field | Value |
| --- | --- |
| source_api | Crossref REST API |
| source_query | agentic retrieval augmented generation large language model |
| source_filter | from-pub-date:2026-03-29,has-abstract:true |
| run_date | 2026-09-25T09:24:28.338813+00:00 |
| raw_response | data\raw\crossref_response.json |
| raw_records | 24 |
| clean_rows | 24 |
| test_set_samples | 10 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| llm_provider | mock |

## 2. Retrieval & Answer Quality (Baseline)

| Metric | Value |
| --- | ---: |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 0.9219 |
| Judge Accuracy | 1.0000 |
| Mean Judge Score (1-5) | 4.6000 |
| Samples | 10 |

### Breakdown by question type

| Question type | Samples | Hit rate | Mean Token F1 |
| --- | ---: | ---: | ---: |
| summary | 2 | 1.0000 | 1.0000 |
| authors | 2 | 1.0000 | 1.0000 |
| date | 2 | 1.0000 | 1.0000 |
| category | 2 | 1.0000 | 1.0000 |
| multi_hop | 2 | 1.0000 | 0.6097 |

## 3. Data Quality Gate (Great Expectations 1.x)

- Overall status: **PASS** (GX: PASS, fresh: PASS)
- Rows validated: 24

| Expectation | Column | Result |
| --- | --- | --- |
| `expect_table_row_count_to_be_between` | - | PASS |
| `expect_column_values_to_not_be_null` | paper_id | PASS |
| `expect_column_values_to_be_unique` | paper_id | PASS |
| `expect_column_values_to_not_be_null` | title | PASS |
| `expect_column_values_to_not_be_null` | text_for_embedding | PASS |
| `expect_column_value_lengths_to_be_between` | summary | PASS |

## 4. Freshness SLA

| Field | Value |
| --- | --- |
| latest_published | 2026-09-15 |
| oldest_published | 2026-04-01 |
| stale_rows | 0 |
| total_rows | 24 |
| stale_ratio | 0.0000 |
| threshold_days | 180 |
| max_stale_ratio | 0.2500 |
| is_fresh | PASS |

## 5. Conclusion

Baseline data passes the quality gate and freshness SLA; these metrics are the reference point for the corruption experiment.
