# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `Friday`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-Friday-DataPipeline` — https://github.com/vietvuivui/K4-L3-DAY10-Friday-DataPipeline

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Nguyễn Văn Quốc Việt | 02973 | bestyasuoplay@gmail.com | **Trưởng nhóm — Pha 3:** Evaluation set & Pipeline Integrator (`testset.py`, `retrieval/index.py`, `phase1.py`, `corruption_flow.py`, `reporting.py`) | `report/02973_NguyenVanQuocViet.md` |
| 2 | Nguyễn Xuân Khuê | 02999 | Khue09022004@gmail.com | **Pha 2:** Ingestion, Cleaning & Quality Gate (`crossref.py`, `cleaning.py`, `quality.py` GX 1.x) | `report/02999_NguyenXuanKhue.md` |
| 3 | Thái Hữu Tuấn | 02465 | tuanthhtq@gmail.com | **Pha 4:** Baseline end-to-end & nghiệm thu Phase 1 (`run_phase1.py`, `baseline_metrics.json`, `phase1_report.md`, agent demo) | `report/02465_ThaiHuuTuan.md` |
| 4 | Nguyễn Việt Hùng | 02972 | hungviet1803@gmail.com | **Pha 5:** Data Corruption, đo suy giảm & báo cáo đối chiếu 3 trạng thái (`corruption.py`, `corruption_flow.py`, `corruption_report.md`) | `report/02972_NguyenVietHung.md` |

---

## # Cá nhân

### ## NguyenVanQuocViet-02973
- **Vai trò:** Trưởng nhóm — Pha 3 (Evaluation set, Vector Index & tích hợp pipeline).
- **Công việc chi tiết đã hoàn thành** (commit `c167182`):
  - Xây dựng bộ test set cố định 10 câu, 5 dạng (`summary`, `authors`, `date`, `category`, `multi_hop`) trong `src/evaluation/testset.py`, kèm `load_or_create_test_set` để tái sử dụng cùng một test set cho cả 3 trạng thái.
  - Hoàn thiện `src/retrieval/index.py` (ChromaDB, 3 collection `papers-baseline` / `papers-corrupted` / `papers-repaired`).
  - Kết nối luồng `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` và viết `src/observability/reporting.py`.
  - Bổ sung fallback `categories` trong `crossref.py` khi Crossref không trả `subject` (dùng nơi xuất bản + loại công trình).
- **Điều học được / Đóng góp chính:**
  - Test set phải được đóng băng và dùng chung cho baseline/corrupted/repaired thì phép so sánh mới có ý nghĩa.

### ## NguyenXuanKhue-02999
- **Vai trò:** Pha 2 — Ingestion, Cleaning & Data Quality Gate.
- **Công việc chi tiết đã hoàn thành** (commit `589d25e`):
  - Xây dựng `src/ingestion/crossref.py`: gọi Crossref REST API có retry, lưu raw response, parse DOI/title/abstract (bỏ thẻ JATS)/authors/dates; fallback đọc snapshot khi gặp 429 hoặc mất mạng.
  - Xây dựng `src/ingestion/cleaning.py`: chuẩn hóa text, tính `age_days`, sinh `text_for_embedding` 5 phần, khử trùng lặp theo `paper_id`.
  - Xây dựng Quality Gate chuẩn Great Expectations 1.x (4 loại expectation, 6 check) và Freshness SLA (> 180 ngày, ngưỡng 25%) trong `src/observability/quality.py`.
- **Điều học được / Đóng góp chính:**
  - Bảo toàn raw snapshot (data lineage) để mọi bước phía sau có thể tái tạo lại mà không phụ thuộc API.

### ## ThaiHuuTuan-02465
- **Vai trò:** Pha 4 — Chạy Baseline end-to-end & nghiệm thu Phase 1.
- **Công việc chi tiết đã hoàn thành** (commit `082dbce`):
  - Chạy `python script/run_phase1.py` trên code đã tích hợp, sinh lại `baseline_metrics.json`, `baseline_answers.json`, `phase1_report.md`, `agent_demo_answers.json` và index `papers-baseline`.
  - Nghiệm thu artifact Phase 1: Hit Rate, Token F1, Judge Accuracy, Quality Gate và Freshness của baseline.
- **Điều học được / Đóng góp chính:**
  - Baseline phải được đo trước khi tiêm lỗi; mọi kết luận ở Pha 5 đều được so sánh với mốc này.

### ## NguyenVietHung-02972
- **Vai trò:** Pha 5 — Thử thách tiêm độc tố dữ liệu & đo lường suy giảm.
- **Công việc chi tiết đã hoàn thành:**
  - Chỉnh `src/ingestion/corruption.py` theo đúng đặc tả Pha 5: noise chèn vào `text_for_embedding`, title < 10 ký tự, lùi ngày xuất bản đúng 5 năm (có cập nhật `age_days`), số dòng nhân bản bằng số dòng bị drop (24 → 24 dòng).
  - Ghi log chi tiết từng hành động (giá trị trước/sau) vào `data/results/corruption_log.json`.
  - Bổ sung bảng đối chiếu 3 trạng thái (Quality Gate, Freshness, Hit Rate, Token F1) có cột Baseline trong `corruption_report.md`.
  - Chạy và xác minh `run_phase1.py` + `run_corruption_flow.py` (exit code 0).
- **Điều học được / Đóng góp chính:**
  - Silent failure là có thật: dữ liệu bẩn không làm pipeline crash nhưng làm Hit Rate giảm 1.00 → 0.80 và Token F1 giảm 0.92 → 0.72; chỉ lớp observability mới phát hiện được.
