# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Văn Quốc Việt |
| MSSV               | 02973 |
| Khóa/Lớp         | K4 — L3 — Day 10 |
| Tên nhóm         | Friday |
| Vai trò chính    | Trưởng nhóm — Pha 3: Evaluation set, Vector Index & tích hợp pipeline |
| Repository         | https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| Evaluation set 10 câu / 5 dạng | `src/evaluation/testset.py` → `build_test_set()`, `load_or_create_test_set()` | Cleaned dataframe | `data/eval/test_set.json` | Hoàn thành |
| Vector index 3 collection | `src/retrieval/index.py` → `LocalEmbeddingIndex` (`_index_dataframe`, `_manifest_path`, `build_from_clean`) | Cleaned/corrupted/repaired dataframe | `data/chroma/`, `data/embeddings/*.json` | Hoàn thành |
| Orchestration Phase 1 và Phase 2 | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | Toàn bộ module | Metrics + artifacts 3 trạng thái | Hoàn thành |
| Report Markdown | `src/observability/reporting.py` | Metrics, quality, freshness | `phase1_report.md`, `corruption_report.md` | Hoàn thành |
| Phiên bản đầu của corruption suite | `src/ingestion/corruption.py` | Cleaned dataframe | 6 kịch bản lỗi (sau đó được Hùng chỉnh theo đặc tả Pha 5) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Fallback `categories` khi Crossref không trả `subject` | Khuê — `crossref.py` | 24/24 bài có `categories_joined` không rỗng |
| Bỏ nhãn "Abstract/Summary" còn sót ở đầu abstract | Khuê — `crossref.py` | `summary` bắt đầu bằng nội dung thật |
| Thêm `test_set_json` vào `Paths` | `core/config.py` | Tương thích tên đường dẫn giữa các module |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Sinh test set tất định, mỗi bài chỉ dùng một lần | `testset.py` | 10 câu: 2 × (`summary`, `authors`, `date`, `category`, `multi_hop`) | `data/eval/test_set.json` |
| Câu hỏi `multi_hop` ghép 2 bài không chung lĩnh vực | `_pick_multi_hop_pairs()` | 2 câu, mỗi câu có 2 `ground_truth_doc_ids` | Test set |
| Index idempotent: xóa rồi dựng lại collection | `LocalEmbeddingIndex._index_dataframe()` | 3 collection tách biệt, mỗi collection 24 docs | Log `Indexed 24 documents into collection 'papers-baseline'` |
| Nối Phase 1 → Phase 2, chặn index khi repaired vẫn fail gate | `corruption_flow.py` | Raise `RuntimeError` nếu repaired fail | Đọc code và chạy flow |

Output cụ thể: `data/eval/test_set.json` là thước đo dùng chung cho cả 3 trạng thái. Baseline đạt Hit Rate 1.00 trên bộ này.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần một thước đo cố định để so sánh baseline, corrupted và repaired, và cần mỗi trạng thái có không gian vector riêng để kết quả của trạng thái này không bị lẫn sang trạng thái khác.

### Cách triển khai

- Test set: sắp xếp theo `paper_id` để chạy lần nào cũng chọn cùng bài. Ghép cặp `multi_hop` trước vì điều kiện chặt hơn (hai bài không chung category), sau đó lấy lần lượt các bài còn lại cho 4 dạng câu đơn. Có kiểm tra điều kiện, ví dụ câu `category` bắt buộc `categories_joined` không rỗng.
- `load_or_create_test_set()` đọc lại file nếu đã có. Nhờ vậy corruption flow dùng đúng bộ câu hỏi sinh từ dữ liệu sạch.
- Index: mỗi trạng thái map sang một collection và một manifest riêng. Mỗi lần build đều `delete_collection` rồi tạo lại, nên chạy nhiều lần không bị nhân đôi vector.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input | Clean schema: `paper_id`, `title`, `summary`, `authors_joined`, `categories`, `published`, `text_for_embedding`... |
| Output | Test set `{id, type, question_type, question, ground_truth, ground_truth_doc_ids}`; ChromaDB collection + manifest |
| Module phụ thuộc | `cleaning.py`, `embeddings.py`, `core/config.py` |
| Module sử dụng output | `evaluation/metrics.py`, `retrieval/qa.py`, `retrieval/agent.py` |
| Điều kiện lỗi cần xử lý | Ít hơn 10 bài; không đủ cặp khác lĩnh vực; không đủ bài có category |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** 10 câu, 3 collection, report 3 trạng thái.
- **Kết quả thực tế:** Test set có 2 câu mỗi dạng; baseline Hit Rate 1.00; corrupted và repaired dùng lại đúng file `test_set.json`.
- **Artifact/log:** `data/eval/test_set.json`, `data/embeddings/papers_embeddings*.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Starter yêu cầu 4 dạng câu hỏi, nhưng các câu hỏi đơn tài liệu không kiểm tra được khả năng tổng hợp nhiều nguồn.
- **Các phương án đã cân nhắc:** (a) chỉ 4 dạng, 10 câu; (b) thêm dạng `multi_hop` ghép 2 bài khác lĩnh vực.
- **Phương án đã chọn:** (b).
- **Lý do:** Lộ được giới hạn thật của QA: trích câu đầu từ một tài liệu thì không trả lời đủ câu hỏi cần 2 nguồn.
- **Bằng chứng quyết định phù hợp:** Baseline cho 8 câu đơn F1 = 1.0, nhưng 2 câu `multi_hop` chỉ đạt 0.70 và 0.52, và judge chấm sai cả hai. Đây là nguyên nhân Token F1 baseline là 0.92 chứ không phải 1.0.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Với dữ liệu Crossref thật, `categories` của các bài đều rỗng, nên không đủ bài hợp lệ để sinh câu hỏi dạng `category`.
- **Lệnh hoặc bước tái hiện:** `python script/run_phase1.py` với dữ liệu live.
- **Nguyên nhân gốc:** Crossref gần như không còn trả `subject` (0/24 bài trong snapshot hiện tại).
- **Cách xử lý:** Trong `crossref.py`, khi thiếu `subject` thì lấy `container-title` → `group-title` (bỏ "In Review") → `institution`, và nối thêm `type`.
- **Cách xác minh sau khi sửa:** Test set có 2 câu `category`, ví dụ "JMIR Formative Research, posted-content"; baseline đạt F1 = 1.0 ở dạng này.
- **Điều học được:** Schema trên tài liệu API không bảo đảm dữ liệu thật có trường đó; phải kiểm tra trên payload thực tế.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref → raw JSON → `PaperRecord` → dataframe sạch → `text_for_embedding` → MiniLM (384 chiều, chuẩn hóa) → ChromaDB cosine.
2. `ground_truth_doc_ids` là DOI: Hit Rate đo retrieval, còn Token F1 và judge đo câu trả lời.
3. GX kiểm tra tính đúng đắn của từng bản ghi và của bảng; freshness kiểm tra tuổi của cả tập dữ liệu.
4. Cùng test set thì chênh lệch metric chỉ đến từ dữ liệu, không đến từ việc đổi câu hỏi.
5. Repaired: GX 6/6, `is_fresh = True`, Hit Rate và Token F1 khớp baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Test set cố định cho thấy rõ 2 câu bị trượt |
| `mean_token_f1`      | 0.9219 | 0.7219 | 0.9219 | `multi_hop` kéo baseline xuống 0.92 |
| `judge_accuracy`     | 0.8000 | 0.6000 | 0.8000 | |
| `mean_judge_score`   | 4.4000 | 3.6000 | 4.4000 | |
| Quality checks         | 6/6 | 4/6 | 6/6 | |
| Freshness status       | Fresh | Stale | Fresh | |

### Kết luận từ số liệu

1. `drop_latest_records` → không có signal quality nào (row count vẫn 24) → `eval_005` và `eval_007` trượt retrieval.
2. Repair từ raw → gate 6/6 → mọi metric trở về baseline, vì cùng test set và cùng index được dựng lại từ đầu.

Kết quả khác kỳ vọng: `eval_007` trượt retrieval nhưng câu trả lời vẫn đúng, vì một bài khác có cùng "Research Square, posted-content". Nếu chỉ nhìn answer metric sẽ không thấy lỗi; phải đo cả Hit Rate.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Đóng băng evaluation set là điều kiện để so sánh có ý nghĩa.
2. Tách collection theo trạng thái giúp đối chiếu khách quan và không bị lẫn vector.
3. Answer metric có thể "đúng vì lý do sai"; retrieval metric bổ sung cho điểm mù này.

### Nếu có thêm thời gian

Nâng QA để tổng hợp câu trả lời từ nhiều tài liệu trong top-k, và đo lại Token F1 của dạng `multi_hop` (hiện 0.61).

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Văn Quốc Việt
**Ngày xác nhận:** [YYYY-MM-DD]
