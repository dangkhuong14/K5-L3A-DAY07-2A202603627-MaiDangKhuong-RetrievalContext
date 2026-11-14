# Code Lab 7

`dense.py` nối với collection C của Lab 6 bằng tìm kiếm cosine, hỗ trợ `top_k`, filter `section`/`chapter_number` và trả schema chunk Lab 7. Kết nối DB chỉ đọc; không tạo lại embedding tài liệu.

## Chạy dense retrieval

Dùng Python 3.11 và các phiên bản thư viện trong [requirements.txt](../requirements.txt), khớp môi trường Lab 6. Workspace hiện có `.venv/python.exe` và dùng lại thư viện từ `.venv` của Lab 6 qua file `.pth` local. Khi dựng môi trường độc lập, cài bằng `python -m pip install -r requirements.txt`.

Chạy từ gốc Lab 7:

```powershell
.\.venv\python.exe -m src.dense --query "Hoàn cảnh nào khiến im lặng gây bất an cho cấp trên?" --section nguyen_tac_04 --top-k 3 --output starter/results/dense/dev-query.json
```

- Cấu hình mẫu: [.env.example](../.env.example). Ưu tiên biến môi trường, tiếp theo `.env` Lab 7; `DATABASE_URL` để trống thì đọc từ `starter/.env` Lab 6. Không ghi URL kết nối vào trace.
- Model được nạp từ cache Lab 6, đúng revision trong [manifest](../data/benchmark/manifest.json), không tải model thay thế. Có thể đổi đường dẫn qua `HF_MODEL_CACHE` hoặc `--day6-root`.
- CLI kiểm tra checksum corpus trước khi search. Khi DB/profile/cache không hợp lệ, lệnh báo lỗi; không thay bằng kết quả giả.
- Output gồm query, filter, profile, snapshot, ranking, nguồn/trang, thời gian search và tổng thời gian gồm nạp model. `service_cost_usd=0` là phí dịch vụ API; không tính điện/phần cứng local.

Khi nối agent, dùng `DenseRetriever.search(query, filters=..., top_k=...)` theo giao diện của `starter/agentic.py`. Mục này chưa nối controller với model trả lời.

```powershell
python -m unittest discover -s tests -v
```
