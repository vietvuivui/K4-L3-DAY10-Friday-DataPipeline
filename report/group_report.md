# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4 — L3 — Day 10 |
| Tên nhóm         | Friday |
| Repository         | https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Văn Quốc Việt (Trưởng nhóm) | 02973 | Pha 3 — Evaluation set, index & tích hợp | `evaluation/testset.py`, `retrieval/index.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, `observability/reporting.py` |
| 2 | Nguyễn Xuân Khuê | 02999 | Pha 2 — Ingestion, cleaning & quality gate | `ingestion/crossref.py`, `ingestion/cleaning.py`, `observability/quality.py` |
| 3 | Thái Hữu Tuấn | 02465 | Pha 4 — Baseline end-to-end | `script/run_phase1.py` → `baseline_metrics.json`, `phase1_report.md`, `agent_demo_answers.json` |
| 4 | Nguyễn Việt Hùng | 02972 | Pha 5 — Corruption & đo suy giảm | `ingestion/corruption.py`, `corruption_log.json`, `corrupted_metrics.json`, `corruption_report.md` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm hoàn thành đủ pipeline 7 tầng và cả hai lệnh `run_phase1.py`, `run_corruption_flow.py` đều chạy thành công (exit code 0) trên dữ liệu thật lấy từ Crossref REST API ngày 2026-09-25 (24 bài báo về agentic RAG/LLM, xuất bản 2026-04-01 → 2026-09-15). Baseline tạo đủ artifact: raw response/records, cleaned CSV/JSON, 3 collection ChromaDB, test set 10 câu (5 dạng), metrics và 2 báo cáo Markdown. Trên dữ liệu sạch, Quality Gate GX 1.x đạt 6/6 check, freshness 0% bài quá hạn, Hit Rate 1.00, Token F1 0.92.

Sau khi tiêm 6 loại lỗi (seed 42), pipeline **vẫn chạy trơn tru không báo lỗi** nhưng Hit Rate giảm còn 0.80, Token F1 còn 0.72, Judge Accuracy từ 0.80 xuống 0.60 — đúng hiện tượng silent failure. Lỗi ảnh hưởng rõ nhất là `drop_latest_records` (làm trượt retrieval 2 câu) và `stale_date` (làm sai câu trả lời về ngày xuất bản). Quality Gate bắt được `blank_summary` và `duplicate_rows`, Freshness SLA bắt được `stale_date` (37.5% bài > 180 ngày). Repair dựng lại dữ liệu từ `data/raw/crossref_records.json` và phục hồi **100%** Hit Rate, Token F1, Judge Accuracy về mức baseline.

Giới hạn lớn nhất: 3 lỗi (`drop_latest_records`, `inject_noise`, `truncate_title`) lọt qua 4 expectations bắt buộc; dữ liệu sạch vẫn còn 3 bài không phải tiếng Anh; LLM judge free tier bị giới hạn 15 request/phút.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API (query "agentic retrieval augmented generation large language model", 24 rows)
    -> data/raw/crossref_response.json + crossref_records.json      (crossref.py)
    -> data/clean/papers_clean.csv/json                             (cleaning.py)
    -> Quality Gate GX 1.x + Freshness SLA -> data/quality/         (quality.py)
    -> MiniLM embedding + ChromaDB "papers-baseline"                (retrieval/index.py)
    -> test set cố định data/eval/test_set.json + evaluation        (testset.py, metrics.py)
    -> data/results/baseline_metrics.json, data/reports/phase1_report.md
    -> corruption 6 kịch bản -> "papers-corrupted" -> re-evaluate   (corruption.py)
    -> repair: rebuild từ data/raw/crossref_records.json -> "papers-repaired" -> re-evaluate
    -> data/reports/corruption_report.md (Baseline vs Corrupted vs Repaired)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref `/works` (query + filter `from-pub-date`, `has-abstract`) | Retry 429/503, fallback snapshot, parse DOI/title/abstract/authors/dates, bỏ thẻ JATS | `data/raw/crossref_response.json`, `crossref_records.json` | Khuê |
| Cleaning          | `crossref_records.json` | Chuẩn hóa text, `age_days`, `text_for_embedding`, dedupe `paper_id` | `data/clean/papers_clean.csv/json` | Khuê |
| Embedding/index   | Cleaned dataframe | `all-MiniLM-L6-v2`, ChromaDB cosine, 3 collection tách biệt | `data/chroma/`, `data/embeddings/*.json` | Việt |
| Evaluation        | Cleaned dataframe | Test set 10 câu / 5 dạng; Hit Rate, Token F1, LLM judge | `data/eval/test_set.json`, `data/results/*_metrics.json` | Việt |
| Observability     | Dataframe mỗi trạng thái | 6 check GX 1.x + Freshness SLA | `data/quality/*.json` | Khuê |
| Corruption/repair | `papers_clean.json`, raw records | 6 kịch bản lỗi + rebuild từ raw | `corruption_log.json`, `papers_clean_corrupted/repaired.*` | Hùng (corruption), Việt (repair flow) |
| Orchestration     | Toàn bộ module | Thứ tự chạy Phase 1 → Phase 2 | `phase1_report.md`, `corruption_report.md` | Việt; Tuấn chạy & nghiệm thu Phase 1 |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `gemini` |
| `LLM_MODEL`                | `gemini-3.5-flash-lite` (`gemini-2.5-flash` đã trả 404 với key của nhóm) |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 (`max_results`) |
| Retrieval`top_k`           | 4 |
| Freshness threshold          | 180 ngày, tối đa 25% bài quá hạn |
| Random seed, nếu có        | 42 (`CORRUPTION_SEED`) |

### Lệnh cài đặt

```bash
python -m pip install -e .
```

### Lệnh chạy

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (exit 0) | 2026-09-25 10:02 UTC | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công (exit 0) | 2026-09-25 10:05 UTC | `data/reports/corruption_report.md`, `data/results/corruption_log.json` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | `https://api.crossref.org/works` |
| Query/filter                | `agentic retrieval augmented generation large language model` / `from-pub-date:2026-03-29,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-09-25 ~09:59 UTC (lần chạy Phase 1 gần nhất) |
| Số record nhận được    | 24 items (Crossref báo `total-results` = 103.669) |
| Cơ chế retry/backoff      | Tối đa 3 lần, backoff tuyến tính 1s, 2s cho 503/lỗi mạng; gặp 429 hoặc hết lượt thì chuyển sang đọc snapshot `data/raw/crossref_response.json` |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | str (DOI chuẩn hóa) | Có | Khóa định danh tài liệu | Thiếu DOI → bỏ record; trùng → giữ bản đầu |
| `title` | str | Có | Tiêu đề | Rỗng → bỏ record |
| `summary` | str | Có | Abstract đã bỏ JATS và nhãn "Abstract" | Rỗng hoặc < 30 ký tự → bỏ record |
| `authors` / `authors_joined` | list / str | Không | Danh sách tác giả | Ghép `given + family`, fallback `name` |
| `categories` / `categories_joined` | list / str | Không | Lĩnh vực | Crossref không trả `subject` → dùng nơi xuất bản + loại công trình |
| `published` | str `YYYY-MM-DD` | Có | Ngày xuất bản | Ưu tiên `published` → `published-online` → `published-print` → `created` → `issued` |
| `age_days` | int | Có | `(run_date - published).days` | Không parse được → 0 |
| `text_for_embedding` | str | Có | Title / Authors / Published / Categories / Summary | Luôn sinh từ các cột đã làm sạch |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ record thiếu DOI/title/summary | Completeness | 0 | 24 raw → 24 clean |
| Bỏ summary < 30 ký tự | Validity | 0 | GX `expect_column_value_lengths_to_be_between` PASS |
| Bỏ thẻ JATS / nhãn "Abstract" đầu abstract | Validity / Consistency | Áp dụng trên toàn bộ abstract | `papers_clean.json` không còn `<jats:` |
| Dedupe theo `paper_id` | Uniqueness | 0 | GX `expect_column_values_to_be_unique` PASS |
| Fallback categories khi thiếu `subject` | Completeness | 24/24 (Crossref không trả `subject`) | `categories_joined` dạng "Research Square, posted-content" |

`text_for_embedding` ghép 5 dòng `Title / Authors / Published / Categories / Summary` để embedding mang đủ ngữ cảnh cho cả câu hỏi về tác giả, ngày và lĩnh vực. Document ID là DOI chuẩn hóa. `age_days` tính theo ngày chạy pipeline, nên cùng một bài sẽ "già đi" theo thời gian và freshness phản ánh đúng thời điểm chạy.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 |
| Các`question_type`                    | `summary`, `authors`, `date`, `category`, `multi_hop` (2 câu mỗi dạng) |
| Ground-truth document ID                 | DOI của bài dùng sinh câu hỏi (`multi_hop` có 2 DOI) |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB (cosine): `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval`top_k`                       | 4 |
| LLM provider/model                       | Gemini `gemini-3.5-flash-lite` (LLM judge) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

Test set được sinh một lần từ dữ liệu sạch và đọc lại qua `load_or_create_test_set`. Nếu mỗi trạng thái tự sinh test set, câu hỏi sẽ được tạo từ chính dữ liệu bẩn (ví dụ tiêu đề đã bị cắt, ngày đã bị lùi), nên metric sẽ không đo được mức suy giảm so với sự thật ban đầu.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | 24 items / 24 records |
| Cleaned dataset          | `data/clean/`                        | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/`   | Có | 24 docs mỗi collection |
| Evaluation set           | `data/eval/`                         | Có | 10 câu |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | |
| Quality/freshness        | `data/quality/`                      | Có | baseline/corrupted/repaired |
| Baseline report          | `data/reports/phase1_report.md`      | Có | |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | 1.0000 | 10/10 câu có tài liệu đích trong top-4 |
| `mean_token_f1`      | 0.9219 | 8 câu đơn đạt F1 = 1.0; 2 câu `multi_hop` chỉ đạt 0.70 và 0.52 vì QA trích câu đầu của một tài liệu |
| `judge_accuracy`     | 0.8000 | 8/10 đúng; judge chấm sai đúng 2 câu `multi_hop` |
| `mean_judge_score`   | 4.4000 | |
| Ragas, nếu có        | N/A | Không bật `RUN_RAGAS=1` để giới hạn chi phí gọi LLM |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Volume | 5–5000 dòng | PASS (24) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` (`paper_id`, `title`, `text_for_embedding`) | Completeness | 0 null | PASS (3/3) | như trên |
| `ExpectColumnValuesToBeUnique` (`paper_id`) | Uniqueness | Không trùng | PASS | như trên |
| `ExpectColumnValueLengthsToBeBetween` (`summary`) | Validity | ≥ 30 ký tự | PASS | như trên |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cleaned dataset (`age_days`) |
| Timestamp mới nhất       | 2026-09-15 (cũ nhất 2026-04-01) |
| Ngưỡng freshness         | `age_days > 180` không quá 25% số bài |
| Trạng thái baseline      | Fresh |
| Lý do                     | 0/24 bài quá 180 ngày, vì filter API chỉ lấy bài từ 2026-03-29 |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest_records` | Bỏ 20% bài mới nhất | 5 | Không có check trực tiếp | Không bị phát hiện; `eval_005`, `eval_007` mất tài liệu đích (hit ❌) | Rebuild từ raw |
| `blank_summary` | Summary = "" | 5 | GX độ dài summary | Bị phát hiện (6 dòng lỗi, tính cả bản nhân đôi); 2 câu hỏi dính lỗi nhưng không làm sai đáp án | Rebuild từ raw |
| `truncate_title` | Cắt title còn 7 ký tự | 5 | Không có check trực tiếp | Không bị phát hiện; `eval_006` bị trúng | Rebuild từ raw |
| `stale_date` | Lùi `published` 5 năm, cập nhật `age_days` | 7 | Freshness SLA | Bị phát hiện (37.5% bài quá hạn > 25%); `eval_006` trả lời `2021-08-26` thay vì `2026-08-26` | Rebuild từ raw |
| `inject_noise` | Chèn token rác vào đầu/cuối `text_for_embedding` | 4 | Không có check trực tiếp | Không bị phát hiện; 2 câu hỏi bị trúng nhưng retrieval vẫn đúng | Rebuild từ raw |
| `duplicate_rows` | Nhân đôi đúng bằng số dòng bị drop | 5 | GX unique `paper_id` | Bị phát hiện (10 giá trị trùng); tổng số dòng giữ 24 nên check row count không thấy | Rebuild từ raw |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: đủ 6 loại lỗi, seed, số dòng vào/ra (24 → 24), danh sách `paper_ids`, và `details` ghi giá trị trước/sau cho từng dòng (title cũ/mới, ngày cũ/mới + `age_days`, chuỗi noise đã chèn).

Repair không vá từng ô bị hỏng. Toàn bộ dataset được dựng lại bằng chính hàm `build_clean_dataframe` từ raw artifact bất biến `data/raw/crossref_records.json`, nên kết quả không phụ thuộc vào việc biết trước lỗi nào đã xảy ra, và chạy lại bao nhiêu lần cũng cho cùng kết quả. Dataset sau repair phải qua lại Quality Gate; nếu vẫn fail thì `corruption_flow.py` từ chối index (`RuntimeError`).

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | 1.0000 | 0.8000 | 1.0000 | −0.2000 | 100% | 2 câu mất tài liệu đích do drop |
| `mean_token_f1`        | 0.9219 | 0.7219 | 0.9219 | −0.2000 | 100% | 2 câu `date` về F1 = 0 |
| `judge_accuracy`       | 0.8000 | 0.6000 | 0.8000 | −0.2000 | 100% | |
| `mean_judge_score`     | 4.4000 | 3.6000 | 4.4000 | −0.8000 | 100% | |
| Quality checks pass/fail | 6/6 PASS | 4/6 (FAIL) | 6/6 PASS | −2 check | 100% | Fail: unique `paper_id`, độ dài `summary` |
| Freshness status         | Fresh (0%) | Stale (37.5%) | Fresh (0%) | +37.5% bài quá hạn | 100% | |

Kết luận nhân quả có artifact hỗ trợ:

1. `stale_date` lùi `published` của bài `eval_006` về 2021-08-26 → Freshness SLA chuyển sang `is_fresh=False` (37.5% bài > 180 ngày) → agent trả lời sai ngày cho `eval_006` (Token F1 1.0 → 0.0) dù retrieval vẫn đúng tài liệu. Đây là silent failure điển hình: tìm đúng tài liệu nhưng nội dung đã bị mốc.
2. `drop_latest_records` loại bài đích của `eval_005` khỏi index → không có check nào bắt được (row count vẫn 24 vì duplicate bù lại) → retrieval trượt và agent lấy ngày của một bài khác (`2021-08-26`), F1 = 0. Repair dựng lại từ raw → GX 6/6, fresh → cả hai câu trở lại F1 = 1.0 và Hit Rate về 1.00.

Kết quả khác kỳ vọng: `eval_007` (category) mất tài liệu đích nhưng câu trả lời vẫn "đúng" vì một preprint khác cũng thuộc "Research Square, posted-content". Answer metric không phát hiện được lỗi ở câu này; chỉ Hit Rate phát hiện được. Vì vậy phải đo cả retrieval lẫn answer.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Với dữ liệu Crossref thật, `categories` của mọi bài đều rỗng, nên câu hỏi dạng `category` trong test set không có ground truth hợp lệ và `categories_joined` trong `text_for_embedding` bị trống.
- **Nguyên nhân:** Crossref gần như không còn trả trường `subject` (24/24 bài không có), trong khi code ingestion ban đầu chỉ đọc `subject`.
- **Cách xử lý:** Trong `crossref.py`, khi không có `subject` thì fallback sang nơi xuất bản (`container-title`, `group-title` khác "In Review", `institution`) cộng với loại công trình (`type`).
- **Cách xác minh:** `python script/run_phase1.py` → `data/eval/test_set.json` có 2 câu `category` với ground truth không rỗng (ví dụ "JMIR Formative Research, posted-content"); baseline đạt F1 = 1.0 ở dạng này.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| 3/6 lỗi (`drop_latest_records`, `inject_noise`, `truncate_title`) lọt qua 4 expectations bắt buộc | Dữ liệu bẩn vẫn có thể được index | Thêm check độ dài title ≥ 10, regex ký tự rác, so sánh `latest_published`/tập DOI với lần chạy trước; kiểm chứng bằng việc chạy lại corruption flow và kiểm tra cả 6 lỗi đều bị gắn cờ |
| 3/24 bài không phải tiếng Anh (2 tiếng Indonesia, 1 tiếng Nga) trong khi MiniLM chỉ tối ưu cho tiếng Anh | Embedding của các bài này kém chính xác | Lọc theo trường `language` và heuristic stopword khi ingest; đo lại Hit Rate |
| Mỗi lần chạy Phase 1 đều gọi API live và ghi đè raw snapshot | Dữ liệu có thể thay đổi giữa các lần chạy | Chỉ fetch khi bật cờ `REFRESH_SOURCE` và lưu metadata thời điểm fetch |
| LLM judge free tier: 15 request/phút, và `gemini-3.5-flash-lite` bỏ qua `temperature` | Chạy chậm; Judge Accuracy baseline có lần là 0.70, có lần 0.80 | Dùng model hỗ trợ `temperature=0` hoặc chấm lặp nhiều lần lấy trung bình; Hit Rate và Token F1 là chỉ số ổn định để so sánh |
| QA trích câu đầu của một tài liệu | `multi_hop` chỉ đạt F1 0.52–0.70 | Tổng hợp câu trả lời từ nhiều tài liệu trong top-k |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (mỗi người cần tự đọc lại, điền MSSV và xác nhận).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
