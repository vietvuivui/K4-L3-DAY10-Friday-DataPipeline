# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Việt Hùng |
| MSSV               | 02972 |
| Khóa/Lớp         | K4 — L3 — Day 10 |
| Tên nhóm         | Friday |
| Vai trò chính    | Pha 5 — Data Corruption & đo lường suy giảm |
| Repository         | https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| 6 kịch bản tiêm lỗi theo đặc tả Pha 5 | `src/ingestion/corruption.py` → `corrupt_clean_dataframe()` | `data/clean/papers_clean.json` (24 dòng) | `papers_clean_corrupted.csv/json` (24 dòng) | Hoàn thành |
| Corruption log chi tiết | `corrupt_clean_dataframe()` → `_entry()` | Các hành động tiêm lỗi | `data/results/corruption_log.json` | Hoàn thành |
| Bảng đối chiếu 3 trạng thái | `src/observability/reporting.py`, `src/pipelines/corruption_flow.py` | Metrics + quality/freshness 3 trạng thái | `data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chạy lại và nghiệm thu cả 2 flow trên code đã tích hợp | Việt (orchestration) | `run_phase1.py` và `run_corruption_flow.py` exit 0 |
| Đổi LLM judge sang model còn hoạt động | Toàn nhóm (`.env`, không commit) | `gemini-2.5-flash` trả 404 → dùng `gemini-3.5-flash-lite` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Noise chèn vào `text_for_embedding` (trước đó chèn vào `summary`) | `corruption.py` bước 5 | 4 dòng có token rác trong text embed | Đếm token rác trong `papers_clean_corrupted.json` |
| Title cắt < 10 ký tự | `TITLE_MAX_CHARS = 7` | 5 title dài 7 ký tự | `title_after` trong log |
| Lùi ngày đúng 5 năm (trước đó 365 ngày) | `pd.DateOffset(years=5)`, cập nhật `age_days` | 7 dòng, ví dụ `2026-08-27 → 2021-08-27`, `age_days = 1855` | `published_before/after` trong log |
| Duplicate = số dòng bị drop | `duplicate_idx` | 24 → 24 dòng | Lệnh kiểm tra trong Guide |
| Thêm cột Baseline + bảng nghiệm thu 3 trạng thái | `_gate()`, `_freshness()` | Mục 0 của `corruption_report.md` | Đọc report |

Output cụ thể: `data/results/corruption_log.json` ghi đủ 6 loại lỗi, seed 42, số dòng 24 → 24, và `details` cho từng dòng bị tác động (title cũ/mới, ngày cũ/mới, chuỗi noise đã chèn).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Chứng minh bằng thực nghiệm rằng dữ liệu bẩn không làm pipeline crash nhưng làm agent trả lời sai (silent failure), đồng thời kiểm tra lớp observability phát hiện được lỗi nào.

### Cách triển khai

- Dùng `random.Random(42)` để lần chạy nào cũng tiêm lỗi vào cùng các dòng. Nhờ vậy số liệu tái hiện được và có thể so sánh giữa các lần chạy.
- Thứ tự xử lý: drop → blank summary → truncate title → stale date → **rebuild `text_for_embedding`** → inject noise → duplicate. Noise phải tiêm *sau* bước rebuild, nếu không bước rebuild sẽ ghi đè mất noise.
- `blank_summary` dùng chuỗi rỗng `""` thay vì `None`, vì GX bỏ qua giá trị null khi kiểm tra độ dài.
- `stale_date` dùng `DateOffset(years=5)` để xử lý đúng năm nhuận. `age_days` được cộng thêm đúng số ngày bị lùi, nên freshness nhận ra được.
- Số dòng nhân bản bằng số dòng bị drop, nên tổng vẫn là 24. Nhờ vậy chứng minh được rằng một check row count đơn thuần không phát hiện được việc mất dữ liệu tươi.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input | DataFrame sạch theo clean schema (16 cột), đường dẫn log |
| Output | DataFrame bẩn cùng schema; file `corruption_log.json` |
| Module phụ thuộc | `cleaning.py` (schema), `core/utils.write_json` |
| Module sử dụng output | `corruption_flow.py` (index + evaluate), `quality.py`, `reporting.py` (đọc key `corruption`, `affected_rows`, `description`) |
| Điều kiện lỗi cần xử lý | Giữ nguyên schema log cũ để `reporting.py` không bị hỏng; `published` phải parse được |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** 24 dòng; log đủ 6 lỗi; quality gate FAIL; metrics giảm; repaired phục hồi.
- **Kết quả thực tế:** `Corrupted 24 dòng`; GX fail 2/6 check; freshness 37.5% > 25%; Hit Rate 1.00 → 0.80 → 1.00.
- **Artifact/log:** `data/results/corruption_log.json`, `data/results/corrupted_metrics.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Đề yêu cầu chèn noise vào `text_for_embedding`, nhưng code ban đầu chèn vào `summary` rồi mới rebuild.
- **Các phương án đã cân nhắc:** (a) giữ chèn vào `summary`, noise tự lan sang text embed; (b) chèn thẳng vào `text_for_embedding` sau khi rebuild.
- **Phương án đã chọn:** (b).
- **Lý do:** Làm đúng đặc tả, và tách bạch tác động: noise chỉ làm lệch vector retrieval, không sửa `summary` mà QA dùng để trích câu trả lời. Nhờ vậy đo được riêng ảnh hưởng của nhiễu lên retrieval.
- **Bằng chứng quyết định phù hợp:** 2 câu hỏi có tài liệu đích bị noise (`eval_002`, `eval_003`) vẫn retrieval đúng. Với MiniLM và top-4, 12 token rác chưa đủ để kéo tài liệu khỏi top-k; đây là một kết quả đo được, không phải giả định.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lệnh kiểm tra trong Guide in `Tín hiệu hoàn thành: Corrupted 23 dòng`, trong khi tín hiệu mong đợi là 24 dòng.
- **Lệnh hoặc bước tái hiện:** Lệnh kiểm tra bước 7 trong `docs/Guide.md`.
- **Nguyên nhân gốc:** Drop 20% (5 dòng) nhưng chỉ nhân bản 20% của 19 dòng còn lại (4 dòng), nên 24 − 5 + 4 = 23.
- **Cách xử lý:** Đặt số dòng nhân bản bằng `drop_count`.
- **Cách xác minh sau khi sửa:** Chạy lại lệnh → `Corrupted 24 dòng`; `corruption_log.json` có `input_rows = output_rows = 24`.
- **Điều học được:** Lỗi mất dữ liệu có thể bị "che" bởi lỗi trùng dữ liệu. Chỉ đếm số dòng là không đủ; phải kiểm tra tính duy nhất và ngày mới nhất.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. `crossref.py` gọi API (có retry, fallback snapshot) và lưu raw → `cleaning.py` chuẩn hóa, tính `age_days`, ghép `text_for_embedding` → `quality.py` chặn dữ liệu xấu → `index.py` embed bằng MiniLM và nạp vào ChromaDB.
2. Mỗi câu hỏi mang `ground_truth_doc_ids` (DOI). Hit Rate kiểm tra DOI đó có nằm trong top-4 hay không; Token F1 và LLM judge so câu trả lời với `ground_truth`.
3. Quality checks kiểm tra *cấu trúc/nội dung* (null, unique, độ dài). Freshness kiểm tra *thời gian* (tỷ lệ bài > 180 ngày). Lỗi `stale_date` qua được toàn bộ GX nhưng bị freshness bắt.
4. Test set là thước đo cố định. Nếu sinh lại test set từ dữ liệu bẩn, câu hỏi sẽ chứa title đã bị cắt hoặc ngày đã bị lùi, và ta đo "dữ liệu bẩn so với chính nó".
5. Repair thành công khi quality gate 6/6 PASS, `is_fresh = True` và Hit Rate, Token F1 trở về đúng giá trị baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | 2 câu mất tài liệu đích do drop |
| `mean_token_f1`      | 0.9219 | 0.7219 | 0.9219 | 2 câu `date` về F1 = 0 |
| `judge_accuracy`     | 0.8000 | 0.6000 | 0.8000 | 2 câu `multi_hop` sai ở cả 3 trạng thái |
| `mean_judge_score`   | 4.4000 | 3.6000 | 4.4000 | |
| Quality checks         | 6/6 | 4/6 | 6/6 | Fail: unique `paper_id`, độ dài `summary` |
| Freshness status       | Fresh | Stale (37.5%) | Fresh | |

### Kết luận từ số liệu

1. `stale_date` → freshness 37.5% > 25% (`is_fresh = False`) → `eval_006` trả `2021-08-26` thay vì `2026-08-26`, Token F1 1.0 → 0.0.
2. Rebuild từ raw → GX 6/6, freshness 0% → Hit Rate và Token F1 khớp 100% baseline.

Corruption ảnh hưởng rõ nhất là `drop_latest_records`: nó không bị check nào phát hiện, làm trượt retrieval ở 2 câu, và khiến `eval_005` trả lời bằng ngày của một bài khác.

Kết quả khác kỳ vọng: Hit Rate chỉ giảm xuống 0.80, không "giảm sâu" như mức ví dụ ≤ 40% trong đề. Nguyên nhân là QA tra cứu theo tiêu đề chính xác rồi fallback sang semantic search, và top-4 trên 24 tài liệu khá rộng. Nhóm giữ nguyên số liệu thật, không chỉnh tham số để làm đẹp kết quả. Ngoài ra, ở `eval_007` retrieval trượt nhưng câu trả lời vẫn đúng vì một preprint khác cùng thuộc Research Square.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot bất biến + hàm cleaning tất định = repair idempotent, không cần sửa tay.
2. Observability phải phủ nhiều chiều: 4 expectations bắt buộc bỏ lọt 3/6 loại lỗi.
3. Dữ liệu bẩn làm agent sai một cách tự tin: không có exception nào, chỉ metric mới lộ ra lỗi.

### Nếu có thêm thời gian

Thêm 3 check cho các lỗi đang lọt: độ dài title ≥ 10, regex phát hiện token rác trong `text_for_embedding`, và so sánh `latest_published` với lần chạy trước. Đo cải thiện bằng cách chạy lại corruption flow và đếm số loại lỗi bị gắn cờ (mục tiêu 6/6).

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Việt Hùng
**Ngày xác nhận:** [YYYY-MM-DD]
