# Checkpoint Lab 7

Phạm vi: phần cơ bản theo [README](README.md), [BENCHMARK](BENCHMARK.md) và [GUIDE](GUIDE.md).

## 1. Dữ liệu và bộ benchmark đã chuẩn bị

- [x] Xác nhận kết nối DB Lab 6: PostgreSQL `day6_lab`.
- [x] Xác nhận bảng `ingestion_vectors`, collection `C` có 2.864 chunk.
- [x] Xác nhận corpus gồm 667 trang nội dung, trang vật lý PDF 18–684.
- [x] Ghi tên embedding model: `google/embeddinggemma-2`.
- [x] Ghi số chiều embedding: 768.
- [x] Lưu revision, prompt và cách chuẩn hóa vào [manifest](data/benchmark/manifest.json).
- [x] Lưu checksum của collection C vào manifest.
- [ ] Bổ sung quyền sử dụng tài liệu; manifest Lab 6 hiện chưa ghi giấy phép.
- [x] Tạo 15 câu dev có đáp án từ bộ dev Lab 6.
- [x] Tạo 2 câu dev thiếu bằng chứng.
- [x] Tạo 5 câu test có đáp án mới, không dùng lại test Lab 6.
- [x] Tạo 2 câu test thiếu bằng chứng.
- [x] Lưu hai bộ dưới dạng JSON array UTF-8 theo [schema](data/README.md):

| Bộ | Có đáp án | Thiếu bằng chứng | Nguồn câu hỏi |
|---|---:|---:|---|
| [dev.json](data/benchmark/dev.json) | 15 | 2 | Dùng lại 15 câu dev Lab 6; thêm 2 câu thiếu evidence |
| [test.json](data/benchmark/test.json) | 5 | 2 | Tạo mới toàn bộ; không dùng lại 5 câu test Lab 6 |

- [x] Kiểm tra 24 ID câu hỏi không trùng nhau.
- [x] Kiểm tra không có câu hỏi trùng giữa dev và test.
- [x] Đối chiếu `source_id` và trang của từng gold với collection C.
- [x] Kiểm tra evidence của cả 20 câu nằm nguyên văn trong chunk tương ứng.
- [x] Kiểm tra filter của câu hỏi khớp metadata của chunk chứa gold.
- [x] Ghi lý do thiếu bằng chứng cho từng câu không trả lời được.
- [x] Kiểm tra nội dung được hỏi trong 4 câu thiếu evidence trên toàn corpus, không chỉ top-k.
- [x] Xuất chunk vào `starter/data/day6/chunks.json`.
- [x] Tạo `starter/data/day6/dev_retrieval.json` chỉ gồm 15 câu có đáp án.
- [x] Tạo `starter/data/day6/test_retrieval.json` chỉ gồm 5 câu có đáp án.

Giữ nguyên lỗi ký tự/khoảng trắng trong evidence để kiểm chứng được. Bốn câu thiếu evidence kiểm tra chi tiết theo nền tảng, chưa đại diện mọi kiểu thiếu bằng chứng. `starter/data/day6/` được Git bỏ qua.

Đã kiểm tra 15 unit test và chạy TF-IDF trên dev: Hit@1 `9/15`, Evidence Hit@3 `10/15`, Context Evidence Rate `9/15`; kết quả tại `starter/results/tfidf-dev/`. Chưa chạy agent thật hoặc benchmark test. Quyền sử dụng tài liệu kế thừa Lab 6, hiện manifest Lab 6 chưa ghi giấy phép; corpus đầy đủ chỉ nằm ở dữ liệu local.

## 2. Checklist triển khai và đánh giá

`[x]`: đã kiểm chứng. `[ ]`: còn phải làm. Các phương pháp dùng cùng corpus và split; đổi top-k đơn thuần không tính là phương pháp mới.

### 2.1. Dense retrieval

- [ ] Nạp cấu hình kết nối DB trong code Lab 7.
- [ ] Nạp embedding model đúng revision của Lab 6.
- [ ] Áp dụng đúng query prompt và cách chuẩn hóa của Lab 6.
- [ ] Kiểm tra vector query có 768 chiều.
- [ ] Viết hàm tìm vector trong collection C với `top_k` cấu hình được.
- [ ] Áp dụng metadata filter từ đầu vào câu hỏi.
- [ ] Chuyển kết quả về schema chunk Lab 7, giữ score/rank và nguồn.
- [ ] Báo lỗi DB/embedding rõ ràng, không thay bằng kết quả giả.

### 2.2. Lexical retrieval

- [x] Có TF-IDF offline trong `starter/baseline.py`.
- [x] Chạy TF-IDF trên 15 câu dev có đáp án; lưu `starter/results/tfidf-dev/`.
- [ ] Viết adapter lexical để agent gọi được cùng giao diện với dense.
- [ ] Ghi cách tách từ dùng cho lexical.
- [ ] Ghi rõ cách xử lý filter; TF-IDF mẫu hiện bỏ qua filter.

### 2.3. Hybrid retrieval

- [ ] Lấy candidate từ dense và lexical trên cùng corpus.
- [ ] Hợp nhất ranking, ví dụ bằng RRF; không cộng score thô khác thang đo.
- [ ] Loại candidate trùng ID sau khi hợp nhất.
- [ ] Trả ranking cuối để so sánh cùng cutoff top-3.

### 2.4. Agent dùng model thật

- [ ] Kết nối controller với model thật hỗ trợ gọi tool.
- [ ] Đăng ký retrieval tool cho agent.
- [ ] Cho phép cấu hình phương pháp retrieval được dùng trong từng lần chạy.
- [ ] Chỉ đưa `question` và `filter` vào agent; giữ nhãn chuẩn ở evaluator.
- [ ] Cấu hình giới hạn lượt gọi và điều kiện dừng.
- [ ] Yêu cầu câu trả lời có citation khi có bằng chứng.
- [ ] Yêu cầu từ chối khi chưa đủ bằng chứng, không suy diễn con số.

### 2.5. Đóng gói context

- [ ] Loại chunk trùng giữa các lượt search.
- [ ] Chọn context budget và ghi rõ đơn vị đo.
- [ ] Giữ ID, nguồn và trang trong context gửi model.
- [ ] Lưu context cuối sau khi áp dụng budget/cắt đoạn.
- [ ] Kiểm tra citation ID thuộc context thực sự gửi model.

### 2.6. Lưu trace cho mỗi câu

- [ ] Lưu `query_id` và trạng thái `answered`, `abstain` hoặc `error`.
- [ ] Lưu model và tham số cấu hình của lần chạy.
- [ ] Lưu query gốc; nếu viết lại query, lưu riêng query viết lại.
- [ ] Lưu tên tool và tham số của từng lượt gọi.
- [ ] Lưu kết quả retrieval có thứ hạng, score và nguồn.
- [ ] Xuất top-3 cho query gốc để so sánh các phương pháp.
- [ ] Lưu câu trả lời cuối và danh sách citation.
- [ ] Lưu số lượt gọi retrieval.
- [ ] Đo thời gian từng câu.
- [ ] Ghi token và chi phí; ghi cách tính hoặc lý do không áp dụng.
- [ ] Lưu lỗi model/DB riêng trong trace.

### 2.7. Code đánh giá tự động

- [ ] Runner chỉ chọn đúng split được yêu cầu.
- [ ] Chấm Hit@1 bằng đúng nguồn, trang và evidence.
- [ ] Chấm Evidence Hit@3 với cùng cutoff cho mọi phương pháp.
- [ ] Chấm Context Evidence Rate trên context cuối, không chỉ ID chunk.
- [ ] Loại câu thiếu evidence khỏi mẫu số retrieval/context.
- [ ] Đếm tool use và phân bố số lượt gọi.
- [ ] Đếm câu trả lời có citation.
- [ ] Báo lỗi provider riêng, không tính thành câu trả lời đúng hoặc từ chối đúng.
- [ ] Xuất số đếm `n/N` và tỷ lệ; mẫu số 0 ghi không áp dụng.
- [x] Chạy 15 unit test có sẵn; tất cả đạt.

### 2.8. Chấm thủ công

- [ ] Chấm context 0/1/2 cho từng câu có đáp án cần đánh giá.
- [ ] Chấm grounded answer 0/1/2 cho từng câu có đáp án.
- [ ] Đọc từng citation để xác nhận nội dung hỗ trợ câu trả lời.
- [ ] Xác nhận từ chối đúng cho từng câu thiếu evidence.
- [ ] Ghi riêng câu có đáp án nhưng bị từ chối nhầm.
- [ ] Ghi lý do cho từng nhãn trong `reviews.json`.
- [ ] Dùng `agent_metrics.py` tổng hợp nhãn sau khi chấm.

### 2.9. Thử nghiệm trên dev

- [ ] Chạy retrieval của ít nhất 3 phương pháp trên cùng bộ dev.
- [ ] Chạy agent thật trên 17 câu dev cho các cấu hình cần so sánh.
- [ ] Ghi giả thuyết cho cấu hình cải thiện thứ nhất.
- [ ] Chạy và lưu kết quả cấu hình cải thiện thứ nhất.
- [ ] Ghi giả thuyết cho cấu hình cải thiện thứ hai.
- [ ] Chạy và lưu kết quả cấu hình cải thiện thứ hai.
- [ ] Phân tích lỗi dev thứ nhất và đối chiếu trace.
- [ ] Phân tích lỗi dev thứ hai và đối chiếu trace.
- [ ] Lập bảng so sánh chất lượng, thời gian và chi phí trước/sau.

Một phương pháp mới có thể đồng thời là cấu hình cải thiện nếu có giả thuyết và kết quả riêng.

### 2.10. Chốt cấu hình trước test

- [ ] Công bố tiêu chí chọn cấu hình trước khi chạy test.
- [ ] Chọn cấu hình theo kết quả dev.
- [ ] Lưu model, retrieval, filter và top-k đã chọn.
- [ ] Lưu context budget và cách chọn context đã chọn.
- [ ] Lưu giới hạn lượt gọi và điều kiện dừng đã chọn.
- [ ] Ghi lý do chọn cấu hình cùng các đánh đổi.

### 2.11. Đánh giá test

- [ ] Chạy retrieval baseline trên 5 câu test có đáp án.
- [ ] Chạy retrieval cấu hình chọn trên cùng 5 câu đó.
- [ ] Chạy agent baseline trên toàn bộ 7 câu test.
- [ ] Chạy agent cấu hình chọn trên cùng 7 câu test.
- [ ] Chấm thủ công đủ 5 câu có đáp án cho cả hai cấu hình.
- [ ] Chấm thủ công đủ 2 câu thiếu evidence cho cả hai cấu hình.
- [ ] Tổng hợp metrics test; giữ riêng output của từng cấu hình.

Nếu đã dùng test để chỉnh hệ thống, cần tạo test mới trước khi báo kết quả độc lập.

### 2.12. Báo cáo và nộp bài

- [ ] Sao chép [mẫu báo cáo](report/individual/MSSV_HoTen.md), đổi tên theo MSSV/họ tên.
- [ ] Điền bảng so sánh retrieval/context.
- [ ] Điền bảng đánh giá agent/citation/abstention.
- [ ] Trình bày một câu trả lời có bằng chứng.
- [ ] Trình bày một câu thiếu bằng chứng được từ chối.
- [ ] Trình bày một lỗi và giới hạn còn lại.
- [ ] Ghi lệnh chạy và đường dẫn cấu hình, trace, nhãn, kết quả.
- [ ] Hoàn tất [checklist nộp bài](SUBMISSION.md).

## 3. Dựa vào đâu để viết bộ đánh giá?

Nguồn chuẩn là **tài liệu/chunk thật + nhãn trong JSON + quy tắc BENCHMARK.md**, không phải kiến thức sẵn có của model hoặc việc unit test chạy xanh.

| Phần | Cách chấm |
|---|---|
| Hit@1 | Số câu có evidence đúng trong kết quả đầu / số câu có đáp án |
| Evidence Hit@3 | Số câu có evidence đúng trong top-3 / số câu có đáp án; cùng cutoff cho mọi phương pháp |
| Context Evidence Rate | Số câu có đủ evidence và nguồn trong context cuối thực sự gửi model / số câu có đáp án |
| Context thủ công | 0: thiếu evidence; 1: có nhưng thiếu điều kiện/nguồn; 2: đủ evidence và nguồn |
| Grounded answer | 0: sai/thiếu evidence hoặc từ chối câu có đáp án; 1: đúng một phần; 2: đúng và đủ; báo phân bố và trung bình /2 |
| Citation | ID có trong context **và** nội dung hỗ trợ câu trả lời; báo citation đúng/tổng citation và số câu trả lời có citation/tổng câu trả lời |
| Tool use | Số câu gọi retrieval / số câu chạy thành công; thêm phân bố số lượt gọi |
| Abstention | Số câu thiếu evidence được từ chối đúng / số câu thiếu evidence; báo riêng số câu có đáp án bị từ chối / số câu có đáp án |

Báo `n/N` và tỷ lệ; mẫu số 0 ghi không áp dụng. Câu thiếu evidence không vào mẫu số retrieval/context. Lỗi model/DB ghi `status: "error"`, báo riêng và giữ nguyên trace.

Code tham khảo:

- [baseline.py](starter/baseline.py): `validate`, `hit`, `evaluate`. Một hit cần đồng thời đúng `source_id`, `page` và chứa nguyên văn `gold.evidence`. Không chấm bằng trùng từ khóa hoặc chỉ đúng trang.
- [agentic.py](starter/agentic.py): vòng gọi tool và chọn context. Chấm context cuối sau budget/cắt đoạn; ID chunk được chọn chưa đủ chứng minh evidence còn trong context.
- [agent_metrics.py](starter/agent_metrics.py): tổng hợp trace và nhãn thủ công; không tự quyết định câu trả lời/citation đúng. Các unit test trong `tests/` kiểm tra code, không đo chất lượng agent thật.

Runner chỉ truyền `question` và `filter` nếu có vào agent. Giữ `gold`, `expected_answer`, `answerable`, `expected_behavior`, `absence_reason`, `absence_check` ở phía evaluator. Filter của bộ này lấy từ phạm vi nguyên tắc đã nêu trong câu hỏi; áp dụng nhất quán khi so sánh các phương pháp hỗ trợ filter. TF-IDF mẫu bỏ qua filter; ghi rõ khác biệt này trong bảng cấu hình.

Với mỗi cấu hình, lưu trace có `query_id`, `status`, model/tham số, query gốc và query viết lại, top-3, tool call/kết quả, context cuối, answer, citations, số lượt gọi, thời gian, token/chi phí và lỗi. Người chấm ghi `context_grade`, `answer_grade` cho câu có đáp án; `abstention_correct` cho câu thiếu evidence; `citation_support` theo từng citation và lý do. Đọc đủ 5 câu test có đáp án + 2 câu thiếu evidence cho cả baseline và cấu hình chọn.

## 4. Lệnh chuẩn bị và kiểm tra

Chạy từ thư mục gốc Lab 7, Python 3.11+. Các file local đã được xuất từ DB C; để tái tạo từ chunk Lab 6 tương ứng:

```powershell
@'
import json
import sys
from pathlib import Path
sys.path.insert(0, "starter")
from convert_day6 import convert_chunk
lab6 = Path(r"D:\AI_ThucChien\Lab6\K5-L3A-DAY06-2A202603627-DataIngestion")
out = Path("starter/data/day6")
out.mkdir(parents=True, exist_ok=True)
rows = (lab6 / "starter/results/read_chunk/chunks_B.jsonl").read_text(encoding="utf-8").splitlines()
chunks = [convert_chunk(json.loads(line)) for line in rows if line.strip()]
(out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
for split in ("dev", "test"):
    cases = json.loads(Path(f"data/benchmark/{split}.json").read_text(encoding="utf-8"))
    questions = [q for q in cases if q["answerable"]]
    (out / f"{split}_retrieval.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python -m unittest discover -s tests -v
python starter/baseline.py --chunks starter/data/day6/chunks.json --questions starter/data/day6/dev_retrieval.json --split dev --output starter/results/tfidf-dev
```

Lab 6 dùng cùng chunk B cho collection C; checksum C được ghi trong manifest. Hai file `*_retrieval.json` loại câu thiếu evidence vì baseline mẫu chỉ nhận câu có gold. Agent phải chạy cả 17 câu dev hoặc 7 câu test trong `data/benchmark/`, không dùng tập đã lọc thay cho benchmark agent.

Baseline mẫu có budget 800 ký tự; khi tự code, ghi budget thực dùng và chấm context sau khi đóng gói. Sau khi chốt cấu hình, đổi sang `test_retrieval.json`, `--split test` và output riêng để chạy retrieval test; chạy agent baseline và agent cấu hình chọn trên `test.json`. Tạo `traces.json` và `reviews.json` thật rồi dùng `starter/agent_metrics.py --cases data/benchmark/test.json --traces <traces.json> --reviews <reviews.json> --split test --output <summary.json>` để tổng hợp từng cấu hình.
