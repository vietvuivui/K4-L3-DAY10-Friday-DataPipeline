# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Thái Hữu Tuấn |
| MSSV               | [MSSV] |
| Khóa/Lớp         | K4 — L3 — Day 10 |
| Tên nhóm         | Friday |
| Vai trò chính    | Pha 4 — Baseline end-to-end & nghiệm thu Phase 1 |
| Repository         | https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| Chạy Baseline end-to-end với LLM judge thật | `script/run_phase1.py` (điều phối bởi `src/pipelines/phase1.py`) | Code đã tích hợp ở Pha 2–3, `.env` (không commit) | `data/results/baseline_metrics.json`, `baseline_answers.json` | Hoàn thành |
| Báo cáo Phase 1 | `data/reports/phase1_report.md` | Metrics, quality, freshness | Báo cáo Markdown | Hoàn thành |
| Agent demo | `data/results/agent_demo_answers.json` (từ `retrieval/agent.py`) | Index `papers-baseline` | 2 câu trả lời của agent | Hoàn thành |

Ghi chú: commit `082dbce` ("pha 4") chỉ chứa artifact sinh ra từ lần chạy pipeline, không sửa mã nguồn.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác minh baseline cho Pha 5 | Hùng — corruption flow | `baseline_metrics.json` là mốc so sánh cho corrupted/repaired |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chạy lại Phase 1 để judge dùng LLM thật thay vì heuristic dự phòng | `baseline_answers.json` | Trước: 10/10 câu có `reasoning` = "Fallback heuristic judge used..."; sau: 10/10 câu có nhận xét thật từ LLM | So sánh `baseline_answers.json` giữa commit `c167182` và `082dbce` |
| Chạy được agent demo | `agent_demo_answers.json` | Trước: `"skipped": "Agent demo unavailable: "`; sau: 2 câu hỏi có câu trả lời đầy đủ từ agent | Đọc file |
| Nghiệm thu quality/freshness baseline | `baseline_quality_report.json` | GX PASS, fresh | Đọc report |

Output cụ thể: `data/results/baseline_metrics.json` phản ánh đánh giá bằng LLM thật. `judge_accuracy` đổi từ 1.0 (heuristic) sang 0.7 ở lần chạy của mình; lần chạy lại gần nhất của nhóm cho 0.8.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Baseline là mốc để đo mọi suy giảm ở Pha 5. Nếu baseline được chấm bằng heuristic thay vì LLM judge, cột "LLM Judge" trong báo cáo không phản ánh đánh giá thật.

### Cách triển khai

- Chạy `python script/run_phase1.py`. Pipeline thực hiện: ingest → clean → quality gate + freshness → index vào `papers-baseline` → đọc test set cố định → evaluate (Hit Rate, Token F1, LLM judge) → sinh `phase1_report.md` → agent demo.
- Kiểm tra trường `reasoning` trong `baseline_answers.json` để chắc chắn judge không rơi vào nhánh fallback của `evaluation/metrics.py` (`_judge_answer` bắt exception rồi dùng heuristic theo Token F1).

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input | `data/raw/`, `data/eval/test_set.json`, cấu hình LLM trong `.env` |
| Output | `baseline_metrics.json` (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`), `baseline_answers.json`, `phase1_report.md`, `agent_demo_answers.json` |
| Module phụ thuộc | Toàn bộ `src/` |
| Module sử dụng output | `pipelines/corruption_flow.py`, `reporting.py` (Pha 5) |
| Điều kiện lỗi cần xử lý | LLM không khả dụng → judge fallback, agent demo bị skip |

### Cách xác minh

```bash
python script/run_phase1.py
```

- **Kết quả mong đợi:** exit 0; đủ artifact Phase 1; judge dùng LLM thật.
- **Kết quả thực tế:** exit 0; Hit Rate 1.00, Token F1 0.92; `reasoning` của judge là nhận xét thật; agent demo có câu trả lời.
- **Artifact/log:** `data/results/baseline_metrics.json`, `data/results/baseline_answers.json`, `data/results/agent_demo_answers.json`, `data/reports/phase1_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Baseline trước đó có `judge_accuracy = 1.0`, nhìn thì đẹp nhưng được chấm bằng heuristic.
- **Các phương án đã cân nhắc:** (a) giữ baseline heuristic vì số liệu cao hơn; (b) chạy lại để LLM judge chấm thật.
- **Phương án đã chọn:** (b).
- **Lý do:** Rubric trừ điểm nặng nếu số liệu không khớp thực tế; một baseline "đẹp giả" sẽ làm sai mọi so sánh ở Pha 5.
- **Bằng chứng quyết định phù hợp:** Sau khi chạy lại, LLM judge chấm sai 2 câu `multi_hop` (Token F1 0.70 và 0.52), đúng với giới hạn thật của QA; heuristic trước đó không phản ánh điều này.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `agent_demo_answers.json` chứa `"skipped": "Agent demo unavailable: "`; toàn bộ `reasoning` trong `baseline_answers.json` là "Fallback heuristic judge used because the LLM evaluator was unavailable."
- **Lệnh hoặc bước tái hiện:** `python script/run_phase1.py` với cấu hình LLM của lần chạy trước.
- **Nguyên nhân gốc:** Pipeline không gọi được LLM. [Tuấn bổ sung nguyên nhân cụ thể, ví dụ thiếu/sai API key hay model không còn khả dụng.]
- **Cách xử lý:** [Tuấn bổ sung thay đổi cấu hình đã làm, không ghi giá trị key.]
- **Cách xác minh sau khi sửa:** Chạy lại Phase 1: `reasoning` là nhận xét thật của LLM, agent demo trả về câu trả lời.
- **Điều học được:** Nhánh fallback giữ pipeline chạy tiếp nhưng có thể che mất lỗi; đây cũng là một dạng silent failure, nên luôn phải kiểm tra judge thực sự chạy bằng gì.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref → raw JSON → clean dataframe (`text_for_embedding`) → quality gate → MiniLM embedding → ChromaDB `papers-baseline`.
2. Mỗi câu hỏi mang DOI đích; Hit Rate đo retrieval top-4, Token F1 và LLM judge đo câu trả lời.
3. Quality checks xét tính hợp lệ của dữ liệu; freshness xét tuổi dữ liệu (> 180 ngày, ngưỡng 25%).
4. Dùng cùng test set để metric của corrupted/repaired so sánh được với baseline mà mình đã đo.
5. Repair thành công khi gate 6/6, fresh, và metric trở về đúng baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | |
| `mean_token_f1`      | 0.9219 | 0.7219 | 0.9219 | |
| `judge_accuracy`     | 0.8000 | 0.6000 | 0.8000 | Lần chạy của mình cho 0.70; model `flash-lite` bỏ qua `temperature` nên judge dao động giữa các lần |
| `mean_judge_score`   | 4.4000 | 3.6000 | 4.4000 | |
| Quality checks         | 6/6 | 4/6 | 6/6 | |
| Freshness status       | Fresh | Stale (37.5%) | Fresh | |

### Kết luận từ số liệu

1. Tiêm lỗi → GX fail 2/6 và freshness 37.5% → Hit Rate giảm 0.20 và Judge Accuracy giảm 0.20.
2. Repair từ raw → gate và freshness phục hồi → metrics trở về đúng mốc baseline.

Corruption ảnh hưởng rõ nhất là `drop_latest_records`, vì nó xóa tài liệu đích của `eval_005` và `eval_007` khỏi index.

Kết quả khác kỳ vọng: `judge_accuracy` baseline không cố định (0.70 ở lần chạy của mình, 0.80 ở lần chạy cuối), trong khi Hit Rate và Token F1 ổn định. Vì vậy khi so sánh 3 trạng thái nên ưu tiên hai chỉ số tất định này.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Baseline phải được đo đúng cách trước khi đo suy giảm.
2. Fallback là con dao hai lưỡi: giữ hệ thống chạy tiếp nhưng có thể che lỗi.
3. LLM judge có độ dao động; cần chỉ số tất định đi kèm.

### Nếu có thêm thời gian

Ghi rõ vào `baseline_metrics.json` số câu dùng judge fallback và tên model judge, để phát hiện ngay khi judge không chạy bằng LLM thật. Đo bằng cách tắt API key và kiểm tra metrics báo đúng số câu fallback.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Thái Hữu Tuấn
**Ngày xác nhận:** [YYYY-MM-DD]
