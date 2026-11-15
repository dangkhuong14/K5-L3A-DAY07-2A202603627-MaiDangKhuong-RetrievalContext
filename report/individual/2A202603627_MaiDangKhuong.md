# Báo cáo Day 7

## Dữ liệu và benchmark

- Nguồn, quyền sử dụng, số trang và số chunk: PDF tiếng Việt “48 nguyên tắc chủ chốt của quyền lực” (Robert Greene, Joost Elffers; thông tin thư mục: Tp. Hồ Chí Minh, Nxb Trẻ, 2011), file `data/20.1.11. 48 nguyên tắc chủ chốt.pdf` của Lab 6, SHA-256 `27fc7a03…f0f3ba`. Chưa có điều khoản cho phép phân phối PDF/đoạn trích (`license_or_permission: null` trong [manifest](../../data/benchmark/manifest.json)); vì vậy PDF và file chunk đầy đủ không đưa lên Git, chỉ có câu hỏi, evidence ngắn và trace chứa các đoạn đã truy xuất. Corpus gồm 667 trang nội dung (trang vật lý PDF 18–684, đánh số 1-based theo trang vật lý), 2.864 chunk (chiến lược B của Lab 6, tối đa 500 ký tự, không vượt trang).
- Vector store, embedding model, phiên bản và số chiều: PostgreSQL + pgvector, database `day6_lab`, bảng `ingestion_vectors`, collection `C`, tìm cosine, kết nối chỉ đọc; snapshot MD5 `efb5ed762003e52c8804fad05156f9fe` được kiểm tra trước mỗi lần chạy. Embedding `google/embeddinggemma-2`, revision `f9972ac22e696a105c482202646979e33e4b5a1e`, 768 chiều, float32, chuẩn hóa L2, query prompt `task: search result | query: `; nạp từ cache Hugging Face của Lab 6, không tạo lại embedding tài liệu.
- Agent model, cách chạy và phân chia dev/test: `openai/gpt-oss-120b` qua API OpenAI-compatible của Groq (free tier), `temperature=0`, `reasoning_effort=low`, `max_tokens=1024`; OpenAI, Gemini và OpenRouter đã thử nhưng tài khoản hết credit. Agent tự viết bằng thư viện chuẩn ([src/agent.py](../../src/agent.py), [src/llm.py](../../src/llm.py)), chạy local bằng Python 3.11. Benchmark 24 câu: dev 15 câu có đáp án (dùng lại q01–q15 của dev Lab 6) + 2 câu thiếu bằng chứng; test 5 câu có đáp án mới (trang 112, 114, 154, 166, 167, không dùng lại test Lab 6) + 2 câu thiếu bằng chứng. Chỉ dùng dev để chọn cấu hình; tiêu chí và cấu hình được commit trước khi chạy test.
- Cách xác định câu có/thiếu evidence và tiêu chí chấm: câu có đáp án ghi `source_id`, trang và evidence nguyên văn; evidence phải nằm trọn trong một chunk đúng nguồn/trang của collection C (đã kiểm tra cả 20 câu). Bốn câu thiếu evidence hỏi con số cụ thể theo nền tảng (LinkedIn, TikTok, Zoom, Microsoft Teams) gần chủ đề chương 4, 5, 6, 13; đã tìm trên toàn bộ 667 trang và 2.864 chunk (chuẩn hóa Unicode, bỏ khoảng trắng), 0 kết quả. Hit@1/Evidence Hit@3 dùng query gốc, đúng nguồn + trang + chứa nguyên văn evidence; Context Evidence Rate chấm trên context cuối thực sự gửi model sau budget. Câu trả lời, context, citation, abstention được chấm thủ công theo [BENCHMARK.md](../../BENCHMARK.md), có lý do cho từng nhãn.

## Retrieval và thử nghiệm

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Baseline | Dense (pgvector, collection C), top-3 mỗi lượt, filter `section` của câu hỏi, không rerank, 800 ký tự, tối đa 3 lượt tìm | Dense trên vector store Lab 6 | dev | 6/15 (40,0%) | 11/15 (73,3%) | Query gốc: 6/15 (40,0%); agent: 5/15 (33,3%) | Retrieval median 205 ms/câu; agent median 4,2 s/câu (10,5 s tính cả chờ rate limit); 48.842 / 4.735 token in/out; ước tính 0,0086 USD, thực trả 0 |
| Phương pháp 2 | BM25 n-gram 4 ký tự (bỏ khoảng trắng), top-3, filter, không rerank, 800 ký tự | Lexical chịu được lỗi tách chữ PDF (`b ắt đầu`); so với BM25 âm tiết 11/15, 12/15 | dev | 11/15 (73,3%) | 13/15 (86,7%) | Query gốc: 11/15 (73,3%) | 29 ms/câu, dựng chỉ mục 0,4 s; 0 USD (chỉ đánh giá retrieval) |
| Phương pháp 3 | Hybrid RRF dense + BM25 char4 (mỗi bên top-20, `k=60`), top-3, filter, 800 ký tự | Gộp theo thứ hạng, không cộng score khác thang đo | dev | 11/15 (73,3%) | 13/15 (86,7%) | Query gốc: 11/15 (73,3%) | 227 ms/câu; 0 USD (chỉ đánh giá retrieval) |
| Cải thiện 1 | Dense, top-3, filter, không rerank, **2000 ký tự**, tối đa 3 lượt | Budget 800 chỉ chứa khoảng 1 chunk nên evidence ở hạng 2–3 bị bỏ; tăng budget để giữ top-3 | dev | 6/15 (40,0%) | 11/15 (73,3%) | Query gốc: 11/15 (73,3%); agent: 7/15 (46,7%) | Retrieval 216 ms; agent median 4,1 s (13,2 s cả chờ); 52.376 / 4.279 token; ước tính 0,0087 USD |
| Cải thiện 2 | **Hybrid RRF** dense + BM25 char4, top-3, filter, 2000 ký tự, tối đa 3 lượt | Agent rút câu hỏi thành từ khóa và chunk lỗi tách chữ làm dense mất evidence; thêm BM25 n-gram ký tự qua RRF (đồng thời là phương pháp 3 với budget mới) | dev | 11/15 (73,3%) | 13/15 (86,7%) | Query gốc: 13/15 (86,7%); agent: 12/15 (80,0%) | Retrieval 249 ms; agent median 3,9 s (13,8 s cả chờ); 47.789 / 3.814 token; ước tính 0,0079 USD |
| Cấu hình đã chọn | Như cải thiện 2 ([configs/selected.json](../../configs/selected.json)) | Chốt trên dev trước khi chạy test | test | 4/5 (80,0%) | 5/5 (100%) | Query gốc: 5/5 (100%); agent: 4/4 câu chạy thành công (1 lỗi provider) | Retrieval 173 ms; agent median 3,7 s (10,7 s cả chờ); 15.600 / 1.496 token; ước tính 0,0026 USD |
| Baseline | Như baseline dev | Đối chứng trên cùng test | test | 4/5 (80,0%) | 5/5 (100%) | Query gốc: 4/5 (80,0%); agent: 4/5 (80,0%) | Retrieval 169 ms; agent median 3,6 s; 18.718 / 1.668 token; ước tính 0,0031 USD |

Đơn vị: thời gian retrieval là median ms/câu, thời gian agent là median giây/câu, chi phí ước tính theo giá niêm yết Groq cho gpt-oss-120b ($0,15/1M token input, $0,075/1M token cached, $0,60/1M token output); free tier thực tế tính 0 USD. Budget tính bằng ký tự Unicode của toàn bộ context gửi model, gồm header. Hit@1/Hit@3 là top-3 của query gốc, không phụ thuộc budget; Context Evidence Rate của agent đo trên context tích lũy qua các lượt tìm của agent. TF-IDF mẫu (bỏ qua filter) đạt 9/15, 10/15, 9/15 và được giữ làm mốc tham khảo. Bỏ filter làm Hit@3 của dense, BM25 char4 và hybrid char4 giảm 1 câu mỗi phương pháp.

**Lỗi dev 1, budget cắt mất evidence.** Baseline có Evidence Hit@3 11/15 nhưng context agent chỉ 5/15. Ở `d7-dev-07`, trace cho thấy cả ba lượt tìm đều bỏ chunk vì hết budget (`dropped_ids`, tổng 6 chunk); context chỉ còn trang 70 nên model từ chối, dù đoạn nghịch đảo ở trang 79 đã có trong top-3. Tăng budget lên 2000 ký tự (cải thiện 1) đưa context lên 7/15, grounded answer trung bình từ 0,60 lên 1,00, từ chối nhầm từ 9 xuống 5; `d7-dev-07` trả lời đúng bằng trang 79.

**Lỗi dev 2, query do agent viết lại làm dense mất evidence.** Với cải thiện 1, query gốc có gold trong top-3 ở `d7-dev-01, 12, 14`, nhưng agent rút câu hỏi thành từ khóa (ví dụ `ẩn mặt tạo sự quý hiếm tác động tập thể`). Khi đó dense xếp trang khác lên trên; ở `d7-dev-14` cả ba lượt tìm không ra trang 297, nơi chunk có lỗi tách chữ `đ{o gi ếng`. Hybrid RRF với BM25 n-gram ký tự (cải thiện 2) nâng Hit@1 từ 6/15 lên 11/15, context agent từ 7/15 lên 12/15, grounded answer trung bình từ 1,00 lên 1,60, từ chối nhầm từ 5 xuống 1.

**Lý do chọn.** Tiêu chí công bố trước test ([configs/selection.json](../../configs/selection.json)), theo thứ tự: grounded answer trung bình trên dev, Context Evidence Rate, giữ abstention 2/2 và ít từ chối nhầm, rồi đến token/thời gian. Cải thiện 2 đứng đầu cả ba tiêu chí chất lượng và dùng ít token nhất (ít lượt tìm hơn: trung bình 1,41 so với 1,82). Đánh đổi: thêm chỉ mục BM25 trong RAM và mỗi lượt tìm chậm hơn dense khoảng 20–40 ms; mỗi lần gọi model dài hơn do budget 2000.

## Agent và đánh giá

- Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi: hai tool là `search_book(query)` (retriever theo cấu hình; filter của câu hỏi do runner áp dụng, model không đặt filter) và `final_answer(status, answer, citations)`. Agent chỉ nhận `question` và `filter`; gold ở lại evaluator. Tối đa 3 lượt tìm; agent dừng khi gọi `final_answer` hoặc trả JSON cuối. Khi hết lượt, agent bỏ tools và buộc trả JSON; nếu nội dung cuối rỗng, hỏi lại một lần ở chế độ JSON. Context: loại trùng theo chunk ID giữa các lượt (chunk đã gửi chỉ nhắc lại mã), giữ thứ tự hạng, bỏ chunk không vừa budget. Header mỗi block là `[S<n> | trang | section]`, mã `S<n>` ánh xạ 1-1 sang chunk ID trong trace. Citation phải thuộc context đã gửi; citation sai hoặc thiếu chuyển thành `abstain`. Lỗi DB/model ném lỗi, ghi `status: "error"` kèm events đã chạy, không thay bằng kết quả giả. HTTP 429 theo phút thì chờ và thử lại, thời gian chờ ghi riêng. Lỗi sinh tool call của Groq (`tool_use_failed`) được thử lại tối đa 3 lần, các lỗi khác ghi `error` ngay; `--retry-errors` chạy lại riêng câu lỗi và giữ lỗi cũ ở `previous_errors`.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| Baseline / dev | 17/17 (100%) | 1: 8, 2: 4, 3: 5 câu; TB 1,82 | 9 / 3 / 3; 0,60 | 6/6 (100%) | 6/6 (100%) | 2/2 (100%) | 9/15 (60,0%) |
| Cải thiện 1 / dev | 17/17 (100%) | 1: 11, 2: 2, 3: 4; TB 1,59 | 6 / 3 / 6; 1,00 | 10/11 (90,9%) | 10/10 (100%) | 2/2 (100%) | 5/15 (33,3%) |
| Cải thiện 2 / dev | 17/17 (100%) | 1: 13, 2: 1, 3: 3; TB 1,41 | 2 / 2 / 11; 1,60 | 13/14 (92,9%) | 14/14 (100%) | 2/2 (100%) | 1/15 (6,7%) |
| Baseline / test | 7/7 (100%) | 1: 4, 2: 2, 3: 1; TB 1,57 | 0 / 0 / 5; 2,00 | 5/5 (100%) | 5/5 (100%) | 2/2 (100%) | 0/5 (0%) |
| Cấu hình đã chọn / test | 6/6 (100%), 1 lỗi provider | 1: 5, 2: 1; TB 1,17 | 0 / 0 / 4; 2,00 | 4/4 (100%) | 4/4 (100%) | 2/2 (100%) | 0/4 (0%) |

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| `d7-test-05` (cấu hình chọn) | Có đáp án | 1 lượt `search_book("Nguyên tắc 12 động tác tốt bụng bao dung cảnh giác người đa nghi")`, filter `nguyen_tac_12`; hybrid trả trang 167, 173, 171 | “Những động tác tốt bụng và bao dung sẽ hạ thấp sự cảnh giác của những người đa nghi…” [S1 = trang 167] | Context 2, answer 2, citation đúng: S1 chứa nguyên văn evidence. Baseline dense chỉ có trang 173 (đoạn thay thế), context 1, answer 2 |
| `d7-dev-09` (cải thiện 2) | Có đáp án | 1 lượt, hybrid đưa trang 123 vào context | “…họ buộc phải thay đổi kế hoạch ban đầu của mình.” [S2 = trang 123] | Context 2, answer 2. Cải thiện 1 (dense) trích trang 132 nói về việc tấn công trước: answer 0, citation sai |
| `d7-test-u01` (cả hai) | Thiếu bằng chứng | Baseline 2 lượt (trang 79, 50), cấu hình chọn 1 lượt (trang 79, 289, 77), không có thông tin “Zoom”/số giây | “Không đủ bằng chứng trong tài liệu để trả lời: không có thông tin cụ thể về thời gian im lặng tính bằng giây trong cuộc họp Zoom.”, không citation | Từ chối đúng, không đưa ra con số |
| `d7-dev-05` (cải thiện 2) | Có đáp án, lỗi | 1 lượt; hybrid không đưa trang 43 vào context, chỉ có trang 139 | “…người khác không biết lời nói và hành động của bạn sẽ ảnh hưởng ra sao…” [S1 = trang 139] | Context 0, answer 0, citation sai: trang 139 nói người tranh luận không biết lời mình tác động ra sao, model đọc ngược chủ thể |
| `d7-dev-03` (baseline) | Có đáp án, từ chối nhầm | 2 lượt dense; context có trang 23 chứa đủ chức vụ và lương bổng | Từ chối: cho rằng thiếu chi tiết | Context 2, answer 0: model quá thận trọng dù có evidence |
| `d7-test-02` (cấu hình chọn) | Có đáp án, lỗi provider | 1 lượt, tìm đúng trang 114 (Tesla 18 tiếng/ngày) | Không có: lượt trả lời rỗng, lượt buộc JSON bị Groq trả `json_validate_failed` ở cả lần chạy đầu và lần chạy lại | `status: "error"`, báo riêng, không chấm nhãn và không tính vào mẫu số chất lượng |

- Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí:
  - Cấu hình: [configs/](../../configs/) (`baseline-dense`, `improve1-dense-b2000`, `improve2-hybrid-b2000`, `selected`, `selection.json`).
  - Retrieval: `results/retrieval-dev/k3-b800/`, `results/retrieval-dev/k3-b2000/`, `results/retrieval-dev/k3-b2000-nofilter/`, `results/retrieval-test/<config>/` (`<method>.traces.json`, `summary.json`).
  - Agent: `results/agent-<split>/<config>/` gồm `config.json` (system prompt, schema tool, snapshot DB), `traces.json`, `auto_metrics.json`, `reviews.json` (nhãn và lý do), `summary.json` (tổng hợp bằng `starter/agent_metrics.py`).
  - Lệnh (từ gốc repo, Windows, `.\.venv\python.exe` là Python 3.11 dùng thư viện Lab 6; key đặt trong `.env` theo [.env.example](../../.env.example)):

    ```powershell
    .\.venv\python.exe -X utf8 -m unittest discover -s tests
    .\.venv\python.exe -X utf8 -m src.retrieval_eval --split dev --methods tfidf bm25-syllable bm25-char3 bm25-char4 dense hybrid-syllable hybrid-char4 --budget 800 --output results/retrieval-dev/k3-b800
    .\.venv\python.exe -X utf8 -m src.retrieval_eval --split dev --methods tfidf bm25-syllable bm25-char3 bm25-char4 dense hybrid-syllable hybrid-char4 --budget 2000 --output results/retrieval-dev/k3-b2000
    .\.venv\python.exe -X utf8 -m src.agent --config configs/improve2-hybrid-b2000.json --split dev --output results/agent-dev/improve2-hybrid-b2000
    .\.venv\python.exe -X utf8 -m src.agent --config configs/improve2-hybrid-b2000.json --split dev --retry-errors --output results/agent-dev/improve2-hybrid-b2000
    .\.venv\python.exe -X utf8 -m src.agent_eval --split dev --traces results/agent-dev/improve2-hybrid-b2000/traces.json --output results/agent-dev/improve2-hybrid-b2000/auto_metrics.json
    .\.venv\python.exe -X utf8 starter/agent_metrics.py --cases data/benchmark/dev.json --traces results/agent-dev/improve2-hybrid-b2000/traces.json --reviews results/agent-dev/improve2-hybrid-b2000/reviews.json --split dev --output results/agent-dev/improve2-hybrid-b2000/summary.json
    .\.venv\python.exe -X utf8 -m src.retrieval_eval --split test --methods hybrid-char4 --budget 2000 --output results/retrieval-test/selected-hybrid-b2000
    .\.venv\python.exe -X utf8 -m src.agent --config configs/selected.json --split test --output results/agent-test/selected-hybrid-b2000
    ```

    Các cấu hình khác chạy tương tự, chỉ đổi `--config`, `--methods`, `--budget` và `--output`. Chunk local `starter/data/day6/chunks.json` (cho BM25/TF-IDF và evaluator) tái tạo bằng hàm `convert_chunk` trong `starter/convert_day6.py` từ `starter/results/read_chunk/chunks_B.jsonl` của Lab 6 (trường `recreate_from` trong manifest); `src/dense.py` kiểm tra số chunk và checksum DB khớp manifest trước khi chạy.
  - Thời gian và chi phí: toàn bộ agent dev chạy 202 s, 211 s và 239 s cho 3 cấu hình, trong đó 131–167 s là chờ rate limit 8K token/phút của Groq free tier. Test chạy 48 s (baseline) và 66 s (cấu hình chọn). Tổng token cả 5 lần chạy là 183.325 input và 15.992 output, ước tính khoảng 0,031 USD theo giá niêm yết, thực trả 0 USD. Dense chạy embedding trên CPU.
- Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:
  - **Trước/sau trên dev:** từ baseline đến cấu hình chọn, context agent tăng từ 5/15 lên 12/15, grounded answer trung bình từ 0,60 lên 1,60, từ chối nhầm giảm từ 9/15 xuống 1/15, abstention giữ 2/2. Token gần như không đổi (53,6K so với 51,6K), median thời gian không tính chờ rate limit tương đương (4,2 s so với 3,9 s).
  - **Trên test:** hai cấu hình ngang nhau về câu trả lời (đều 2,00/2 trên các câu chạy thành công, abstention 2/2). Khác biệt nằm ở context: hybrid đưa đúng trang gold 167 ở `test-05`, retrieval context 5/5 so với 4/5. Test chỉ có 5 câu có đáp án, dễ hơn dev và mỗi câu bằng 20 điểm phần trăm, nên chưa đủ để kết luận cấu hình chọn tốt hơn trên test.
  - **Ví dụ lỗi:** `d7-dev-05` trích sai trang 139; `d7-dev-06` không tìm được trang 70; `d7-test-02` lỗi provider.
  - **Đánh đổi:** budget 2000 làm mỗi lượt gọi dài hơn nhưng giảm số lượt tìm; hybrid thêm 20–40 ms/lượt và cần chỉ mục BM25 trong RAM.
  - **Giới hạn:**
    - Model đôi khi sinh nội dung rỗng sau lượt tool, hoặc lỗi định dạng tool/JSON trên Groq: 1 lỗi ở dev đã chạy lại thành công, 1 lỗi ở test vẫn còn. Không sửa code sau khi xem test để giữ đánh giá độc lập; hướng sửa là thử lại lượt trả lời không dùng JSON mode, kiểm chứng trên dev hoặc test mới.
    - Agent hay rút query thành từ khóa; luôn tìm thêm bằng câu hỏi gốc là hướng thử tiếp.
    - PDF có lỗi glyph và tách chữ, có thể làm hỏng khớp nguyên văn.
    - Chỉ có một người chấm, chưa đo độ đồng thuận.
    - Bốn câu thiếu bằng chứng cùng một kiểu (con số theo nền tảng).
    - Rate limit làm thời gian thực tế dài gấp 2–3 lần thời gian xử lý.
    - Chưa có giấy phép phân phối tài liệu.

## Thử thách nâng cao (nếu thực hiện)

Không thực hiện phần nâng cao; các mục dưới đây để trống.

- Tài liệu, nguồn, quyền sử dụng, số trang và phiên bản: không áp dụng.
- Cách xử lý text, bảng, ảnh, biểu đồ; phạm vi index và phần chưa xử lý: không áp dụng.
- Cách chia benchmark, schema evidence, model và cấu hình đã chốt trên dev: không áp dụng.

| Nhóm test | Đạt / tổng | Tỷ lệ | Lỗi / nhận xét |
|---|---|---|---|
| Bảng | | | Không thực hiện |
| Ảnh, sơ đồ | | | Không thực hiện |
| Biểu đồ | | | Không thực hiện |
| Multi-hop | | | Không thực hiện |
| Text | | | Không thực hiện |
| Thiếu bằng chứng | | | Không thực hiện |
| **Toàn bộ** | | | Không thực hiện |

- Trace, nhãn và evidence từng câu; thời gian, chi phí, lỗi hệ thống: không áp dụng.
- Giới hạn, cách tái lập và đường dẫn benchmark: không áp dụng.
