# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Xuân Khuê |
| MSSV               | 02999 |
| Khóa/Lớp         | K4 — L3 — Day 10 |
| Tên nhóm         | Friday |
| Vai trò chính    | Pha 2 — Ingestion, Cleaning & Data Quality Gate |
| Repository         | https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| Raw ingestion + lineage | `src/ingestion/crossref.py` → `fetch_source_records()`, `parse_crossref_payload()`, `load_raw_records()` | Crossref `/works` (query, filter, rows = 24) | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Cleaning & data model | `src/ingestion/cleaning.py` → `build_clean_dataframe()` | `list[PaperRecord]`, `run_date` | `data/clean/papers_clean.csv/json` | Hoàn thành |
| Quality Gate GX 1.x + Freshness SLA | `src/observability/quality.py` → `run_data_quality_checks()`, `build_freshness_report()` | Dataframe mỗi trạng thái | `data/quality/*_quality_report.json`, `*freshness_report.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Cung cấp clean schema ổn định cho index/test set | Việt — `index.py`, `testset.py` | Các cột `authors_joined`, `categories_joined`, `text_for_embedding` được dùng trực tiếp |
| Hàm `build_clean_dataframe` được tái sử dụng cho repair | Pha 5 — `corruption_flow.py` | Repaired khớp 100% baseline |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Gọi Crossref có retry + fallback snapshot | `fetch_source_records()` | 24 records | `Tín hiệu hoàn thành: Đã tải 24 bài báo` |
| Bỏ thẻ JATS/HTML, giải mã entity | `_clean_text()` | 0 thẻ `<jats` trong dữ liệu sạch | Tìm `<jats` trong `papers_clean.json` |
| Chuẩn hóa ngày thiếu ngày/tháng | `_parse_iso_date()` | `[2026, 7]` → `2026-07-01` | Cột `published` |
| Tính `age_days`, sinh `text_for_embedding` 5 phần, dedupe | `build_clean_dataframe()` | 24 dòng, 16 cột | `Clean thành công 24 dòng` |
| 6 check GX 1.x + freshness | `run_data_quality_checks()` | Baseline 6/6 PASS, `is_fresh = True` | `data/quality/baseline_quality_report.json` |

Output cụ thể: Quality Gate chạy trên dữ liệu bị tiêm lỗi đã báo FAIL 2/6 check (10 giá trị `paper_id` trùng, 6 summary < 30 ký tự) và freshness FAIL (37.5% bài > 180 ngày). Đây là bằng chứng lớp observability do mình dựng hoạt động đúng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Đưa dữ liệu thật, bẩn và không đồng nhất từ Crossref về một schema sạch, có thể truy vết về bản gốc, và chặn dữ liệu xấu trước khi nó vào vector store.

### Cách triển khai

- Ingestion: gửi query, filter (`from-pub-date` 180 ngày gần nhất, `has-abstract:true`) và `rows = 24`. Lỗi 503 hoặc lỗi mạng thì thử lại tối đa 3 lần với backoff 1s, 2s. Lỗi 429 thì chuyển ngay sang snapshot `data/raw/crossref_response.json` để không làm chậm phòng lab. Raw response được lưu nguyên vẹn trước khi parse.
- Parse: chuẩn hóa DOI (bỏ `https://doi.org/`, `doi:`), bỏ record thiếu DOI, title hoặc abstract. Tác giả ghép từ `given + family`, fallback sang `name`. Ngày lấy theo thứ tự ưu tiên `published → published-online → published-print → created → issued`.
- Cleaning: bỏ summary < 30 ký tự; `age_days = (run_date − published).days`; `text_for_embedding` gồm Title / Authors / Published / Categories / Summary; dedupe theo `paper_id`; sắp xếp theo ngày giảm dần.
- Quality: dùng ephemeral context của GX 1.x (`gx.get_context(mode="ephemeral")` → `add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe`), `ExpectationSuite` và `ValidationDefinition`. Freshness đánh `is_fresh = False` khi hơn 25% số bài có `age_days > 180`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input | Crossref payload `message.items[]` |
| Output | `PaperRecord` (11 trường) → clean dataframe (16 cột) → quality report JSON (`success`, `gx_success`, `is_fresh`, `expectations[]`) |
| Module phụ thuộc | `core/config.py`, `core/utils.py` |
| Module sử dụng output | `retrieval/index.py`, `evaluation/testset.py`, `pipelines/*`, `reporting.py` |
| Điều kiện lỗi cần xử lý | 429/503/mất mạng; thiếu DOI, title, abstract; ngày chỉ có năm hoặc năm-tháng; abstract chứa JATS |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```

- **Kết quả mong đợi:** 24 bài; `Quality check status = True`.
- **Kết quả thực tế:** 24 raw → 24 clean; baseline GX 6/6, freshness 0/24 bài quá hạn.
- **Artifact/log:** `data/raw/`, `data/clean/`, `data/quality/baseline_quality_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** API Crossref có thể trả 429 (bị giới hạn tốc độ) khi cả lớp cùng gọi.
- **Các phương án đã cân nhắc:** (a) retry 429 với backoff dài; (b) gặp 429 thì chuyển ngay sang snapshot đã lưu.
- **Phương án đã chọn:** (b) cho 429; còn 503 và lỗi mạng thì vẫn retry.
- **Lý do:** Trong phòng lab, retry 429 chỉ làm tăng tải và làm mọi người chờ lâu. Snapshot raw đã được lưu nguyên vẹn nên dữ liệu vẫn truy vết được.
- **Bằng chứng quyết định phù hợp:** Pipeline luôn có dữ liệu để chạy; raw response được lưu trong `data/raw/crossref_response.json` (24 items, `total-results` = 103.669).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Một số bài Crossref có `date-parts` chỉ gồm năm-tháng (ví dụ `[[2026, 7]]`), nên nếu parse theo dạng `YYYY-MM-DD` cứng thì sẽ lỗi hoặc mất ngày.
- **Lệnh hoặc bước tái hiện:** Parse payload thật chứa bản ghi có `published.date-parts = [[2026, 7]]`.
- **Nguyên nhân gốc:** Crossref chỉ trả phần ngày mà nhà xuất bản khai báo.
- **Cách xử lý:** `_parse_iso_date()` xử lý đủ 3 trường hợp: 3 phần giữ nguyên; 2 phần thì thêm `-01`; 1 phần thì thêm `-01-01`. Nếu không có `date-parts` thì fallback sang `date-time`.
- **Cách xác minh sau khi sửa:** Mọi dòng trong `papers_clean.json` đều có `published` hợp lệ; khoảng ngày là 2026-04-01 → 2026-09-15.
- **Điều học được:** Phải thiết kế parser theo dữ liệu thật chứ không theo ví dụ đẹp trong tài liệu.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref → raw response lưu nguyên vẹn → `PaperRecord` → clean dataframe → quality gate → embedding MiniLM → ChromaDB.
2. Mỗi câu hỏi gắn DOI của tài liệu đích; Hit Rate kiểm tra DOI có nằm trong top-4 hay không, còn Token F1 và judge so câu trả lời với ground truth.
3. GX kiểm tra tính hợp lệ của dữ liệu (null, unique, độ dài, số dòng); freshness kiểm tra tuổi dữ liệu so với SLA 180 ngày.
4. Giữ nguyên test set để chênh lệch metric chỉ phản ánh chất lượng dữ liệu.
5. Repair dùng lại chính `build_clean_dataframe()` trên `crossref_records.json` → GX 6/6, `is_fresh = True`, metrics khớp baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | |
| `mean_token_f1`      | 0.9219 | 0.7219 | 0.9219 | |
| `judge_accuracy`     | 0.8000 | 0.6000 | 0.8000 | |
| `mean_judge_score`   | 4.4000 | 3.6000 | 4.4000 | |
| Quality checks         | 6/6 | 4/6 | 6/6 | Unique và length bắt được `duplicate_rows`, `blank_summary` |
| Freshness status       | Fresh (0%) | Stale (37.5%) | Fresh (0%) | Bắt được `stale_date` |

### Kết luận từ số liệu

1. `blank_summary` + `duplicate_rows` → GX fail 2 check → nếu gate được dùng để chặn thì batch này không được index.
2. Repair từ raw → GX 6/6 và fresh → metrics trở về baseline.

Corruption ảnh hưởng rõ nhất đến observability là `stale_date`: GX không bắt được, chỉ freshness bắt được.

Kết quả khác kỳ vọng: 4 expectations bắt buộc không phát hiện được `truncate_title`, `inject_noise` và `drop_latest_records`, vì các lỗi này không vi phạm null, unique hay độ dài summary.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Luôn lưu raw nguyên vẹn trước khi biến đổi; đó là "bảo hiểm" cho việc repair.
2. Quality gate chỉ bắt được những gì mình định nghĩa; bộ check tối thiểu vẫn còn điểm mù.
3. Dữ liệu thiếu hoặc cũ không làm crash hệ thống mà làm agent trả lời sai.

### Nếu có thêm thời gian

Thêm lọc ngôn ngữ ở bước ingest: dữ liệu sạch hiện còn 3/24 bài không phải tiếng Anh (2 tiếng Indonesia, 1 tiếng Nga), trong khi MiniLM chỉ tối ưu cho tiếng Anh. Đo lại Hit Rate sau khi lọc.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Xuân Khuê
**Ngày xác nhận:** [YYYY-MM-DD]
