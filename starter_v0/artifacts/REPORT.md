# Research Agent — Báo cáo nhóm VuVo

- 2A202603682 — Hà Huy Thái
- 2A202603699 — Nguyễn Lê Hải Nam
- 2A202603701 — Đỗ Nhật Anh
- 2A202603663 — Lê Quang Trường

Cấu hình được chọn: **Python 3.12, Ollama `qwen3.5:4b-q4_K_M`, profile `v13-scope-check`**. Kết quả đã đo: **20/20 base, 10/10 group, 10/10 hồi quy** theo rubric chọn tool/arguments; **205 tests passed, 0 failed, 0 skipped** ở lần kiểm thử gần nhất.

# PHẦN A — Giới thiệu agent

## A1. Chức năng và link dùng thử

Agent hỗ trợ tìm bài đăng, tìm web, đọc URL/paper arXiv, tra chính sách nội bộ, bỏ kết quả trùng và tạo digest. Khi thiếu dữ liệu, agent hỏi lại; gửi Telegram cần người dùng xác nhận nội dung.

UI dùng Streamlit. Từ `starter_v0`, chạy:

```powershell
.\.venv312\Scripts\python.exe -m streamlit run app.py
```

Mở **http://localhost:8501**, chọn `ollama` để dùng model thật. UI hiện chỉ chạy local; chưa có link public. Chế độ `demo (offline)` là scripted, không được tính là bằng chứng model thật. Các API nghiên cứu cần key riêng theo [hướng dẫn setup](../../TOOL-SETUP.md).

## A2. Các tool

| Tool | Chức năng |
|---|---|
| `clarify` | Hỏi thông tin thiếu hoặc xin xác nhận |
| `timeline` | Lấy bài đăng từ một tài khoản đã xác định |
| `social_search` | Tìm bài đăng theo chủ đề/từ khóa |
| `lookup` | Tìm web, hỗ trợ tin tức và khoảng thời gian |
| `fetch` | Đọc nội dung URL |
| `format` | Trình bày các kết quả đã có thành digest |
| `send` | Gửi Telegram sau xác nhận |
| `policy` | Tra chính sách nội bộ trong repo |
| `papers` | Tìm metadata/abstract paper arXiv |
| `paper_text` | Đọc text từ PDF arXiv |
| `deduplicate` — tool mới | Bỏ trùng URL/tiêu đề, giữ mục đầu tiên và thứ tự |

## A3. Câu hỏi demo

Gửi lần lượt trong cùng phiên Ollama. Ba câu này dùng tool local, không cần API key nghiên cứu:

1. `Loại trùng URL, giữ bản đầu tiên và mọi trường: [{"title":"Orchid","url":"https://example.org/orchid","rank":8},{"title":"Maple","url":"https://example.org/orchid/","rank":5},{"title":"Orchid","url":"https://example.net/second","tags":["botany"]}]`
2. `Dùng lại danh sách gốc tôi gửi ở lượt đầu, lần này bỏ trùng theo tiêu đề; giữ bản đầu tiên và mọi trường.`
3. `Tra policy nội bộ thuộc nhóm tool_usage: cần làm gì trước khi một công cụ gửi nội dung ra bên ngoài? Lấy 2 đoạn liên quan.`

Để thử nghiên cứu online: “Tin tức AI hôm nay trên web có gì nổi bật?” cần Tavily key; “Mọi người bàn gì về năng lượng tái tạo trên X?” cần RapidAPI key; tìm/đọc paper cần kết nối arXiv. Thiếu cấu hình, tool trả error dict.

# PHẦN B — Chi tiết và bằng chứng

## B1. Các phiên bản và kết quả

### Baseline và ba vòng bắt buộc

Các run sau dùng Ollama `qwen2.5:3b` và cùng 20 base cases. Điểm được giữ theo scorer lịch sử; không gộp với scorer mới để kết luận tác động riêng của prompt.

| Version | Thay đổi và giả thuyết | Case đúng (trước → sau) | Routing | Arguments | Multi-turn | Run |
|---|---|---|---:|---:|---:|---|
| v0 | Baseline trước tối ưu | — → 7/20 | 0.50 | 0.35 | 0.50 | [v0](../runs/v0_B_base_ollama_20261110T095915950610.json) |
| v1 | Làm rõ routing/boundary; đồng thời tích hợp khai báo `deduplicate` | 7/20 → 12/20 | 0.65 | 0.60 | 0.8333 | [v1](../runs/v1_B_base_ollama_20261110T105305856367.json) |
| v2 | Chỉ sửa mô tả trong `tools.yaml`: phân biệt nguồn, quy ước args và xác nhận gửi | 12/20 → 12/20 | 0.80 | 0.60 | 0.6667 | [v2](../runs/v2_B_base_ollama_20261110T112419425370.json) |
| v3 | Chỉ sửa prompt: checklist giữ args và ngữ cảnh trước khi gọi tool | 12/20 → 15/20 | 0.80 | 0.75 | 0.6667 | [v3](../runs/v3_B_base_ollama_20261110T113016705870.json) |

V1 đổi cả prompt và khai báo tool nên chưa cô lập một yếu tố. V2 tăng routing nhưng chưa tăng accuracy tổng; v3 tăng arguments và accuracy, còn lỗi nhiều lượt. Từ v4 có thay đổi code/scorer, model và giao thức nên không quy toàn bộ mức tăng sau đó cho prompt.

### Profile hiện tại: v13-scope-check

Ba run dưới đây đều `completed`, đo đủ case, không có provider error hoặc lỗi scope checker. Case/routing/argument/multiturn accuracy đều **1.00** trên từng bộ.

| Bộ eval | Case đúng | Model requests | Tool calls / lỗi execution / dry-run | Run |
|---|---|---:|---|---|
| Base | 20/20 | 26 | 18 / 15 / 0 | [base](../runs/v13-scope-check_B_base_ollama_20261110T215745048265.json) |
| Group | 10/10 | 11 | 9 / 2 / 1 | [group](../runs/v13-scope-check_B_group_ollama_20261110T220209935907.json) |
| Hồi quy riêng | 10/10 | 13 | 9 / 4 / 0 | [hồi quy](../runs/v13-scope-check_B_cross_ollama_20261110T220336582487.json) |

Tổng **40/40**, dùng **50 model requests**: 45 native/planning requests và 5 scope checks. Có **36 tool calls: 21 lỗi execution, 1 dry-run, 14 call không lỗi**. Các lỗi nghiên cứu do thiếu API key. Vì vậy 40/40 chứng minh routing/arguments theo rubric, chưa chứng minh mọi tác vụ nghiên cứu thực thi thành công hoặc mọi câu trả lời đúng nội dung.

Pipeline thử native trước; nếu thiếu call bắt buộc hoặc phản hồi auto rỗng, cho phép tối đa một retry với schema của đầy đủ 11 tool. Model chọn tên tool/args; adapter không sửa theo đáp án eval. Câu trả lời trực tiếp được một model request riêng phân loại phạm vi. Nhãn `outside` thay phần hiển thị bằng lời từ chối; draft gốc, quyết định và chi phí vẫn được lưu. Đây là kết quả của pipeline có retry/checker, không phải native một lần gọi.

Prompt/tools hiện tại có hash `cf5769335127...` / `b55cee54af1f...`. [Version log](version_log.csv), [bảng thí nghiệm](../analysis/local_tuning_results.csv) và [runtime cuối](../analysis/final_runtime.json) lưu đường dẫn, hashes, cấu hình và các lần thử; run gián đoạn vẫn được giữ, không tính thành kết quả hoàn chỉnh. Cách chạy lại ở [README](../../README.md) và [TOOL-SETUP](../../TOOL-SETUP.md).

## B2. Phân tích lỗi

Baseline v0 sai **13/20 case**. Bảng này nhóm theo lỗi quan sát; nhãn case gốc và toàn bộ `failures` vẫn giữ trong [run v0](../runs/v0_B_base_ollama_20261110T095915950610.json) và [CSV phân tích](../analysis/base_runs.csv).

| Lỗi quan sát | Case v0 | Ví dụ và cách sửa |
|---|---|---|
| Sai giá trị args | R01, R06, M03 | `samaltman` thay `sama`; news dùng `general`; mất handle/số lượng. Làm rõ args và giữ ràng buộc chưa bị thay đổi. |
| Chọn sai/thiếu tool theo nguồn | R03, R04, R13, M02, M06 | Dùng social thay web, `paper_text` cho URL thường, thiếu một nguồn ở yêu cầu song song. Làm rõ routing và ưu tiên nguồn ở lượt mới nhất. |
| Không hỏi dữ liệu thiếu | R10, R11 | Tự chọn tài khoản hoặc tự tìm khi chưa có URL. Yêu cầu dùng `clarify` thay vì đoán. |
| Gửi khi chưa được xác nhận | R12 | Model tự tạo text và `confirmed=true`. Yêu cầu xin xác nhận nội dung; eval mặc định dry-run, code kiểm tra boolean. |
| Gọi tool ngoài phạm vi | R08, R14 | Dùng `clarify` cho toán/coding ngoài nhiệm vụ research. Làm rõ phạm vi trước khi chọn tool. |

V3 vẫn sai R10, R11, R14, M03 và M06: đoán handle, hỏi bằng prose thay tool, hỏi xác nhận ngoài scope, mất `limit=3` và không chuyển nguồn. Các run mới đã đạt rubric cho các case này.

**Lỗi nội dung mà điểm routing không phát hiện:** [hồi quy v12](../runs/v12-local_B_cross_ollama_20261110T212556705830.json) vẫn PASS X05 vì không gọi tool, dù trả mã Java ngoài phạm vi. V13 giữ nguyên prompt/tools v12 và thêm scope checker: R08, R14, X05 hiển thị từ chối; R09 giới thiệu khả năng và G05 cảm ơn giữ nguyên. Draft X05 của model native vẫn chứa mã và được lưu trong metadata. Checker giải quyết phần hiển thị ở các case đã quan sát; không chứng minh native model đã tự hết lỗi hoặc checker luôn đúng.

## B3. Eval nhóm và tool mới

[eval_group.json](../data/eval_group.json) gồm **5 single-turn và 5 multi-turn**; profile hiện tại đạt **10/10**.

| Case | Hành vi được kiểm tra |
|---|---|
| G01 | Route tìm paper sang `papers` |
| G02 | `policy_area=source_citation` |
| G03 | Bỏ `@` khỏi handle, giữ `limit=3` |
| G04 | Tool mới: đủ `items`, bỏ trùng URL |
| G05 | Lời cảm ơn không gọi tool |
| G06 | Từ tìm paper sang đọc đúng arXiv ID, `max_pages=2` |
| G07 | Đổi `Latest` sang `Top`, giữ query chủ đề |
| G08 | Dùng danh sách từ lượt trước, đổi sang bỏ trùng tiêu đề |
| G09 | Giữ `policy_area=data_privacy`, `top_k=2` |
| G10 | Giữ nguyên text đã duyệt và boolean `confirmed=true`; execution dry-run |

Tool `deduplicate(items, key_by="url")` đã có [code](../tools/deduplicate/tool.py), [TOOL.md](../tools/deduplicate/TOOL.md), [registry](../tools/__init__.py) và [declaration](tools.yaml). `items` bắt buộc là list các object; `key_by` tùy chọn `url|title`. Output gồm `tool`, `items`, `removed_count`; dữ liệu sai trả error dict. Tool chạy local, giữ bản đầu và thứ tự, không thay input; không gộp nội dung hay phát hiện trùng ngữ nghĩa.

Run group v3 lịch sử đạt 7/10 theo scorer subset cũ. [Replay offline](../analysis/v4_group_offline_replay.json) cùng calls đạt 6/10 khi kiểm tra schema chặt hơn; đó không phải lần gọi model mới. Kết quả 10/10 hiện tại là một run model thật riêng, không thay nhãn log cũ.

## B4. Chat live và UI

[Transcript UI hiện tại](../transcripts/v13-scope-check_ollama_20261110T220653977216.transcript.json) được tạo qua Streamlit/AppTest với Ollama thật, đúng UTF-8, scope checker bật, không demo fallback. Cả 3 lượt đều trả lời live:

| Lượt | Yêu cầu | Kết quả kiểm tra |
|---|---|---|
| 1 | Bỏ trùng URL trong 3 items | Bỏ 1 mục, giữ bản đầu, thứ tự và metadata |
| 2 | Bỏ trùng tiêu đề từ danh sách gốc ở lượt 1 | Dùng đủ danh sách gốc, bỏ 1 mục; không dùng nhầm danh sách đã rút gọn |
| 3 | Tra `tool_usage`, lấy 2 đoạn về gửi nội dung ra ngoài | Giữ đúng filter/số lượng, trả facts liên quan đến xác nhận |

[Kiểm tra phiên UI](../analysis/v13-scope-check_ui_live_check.json) đạt **5/5**: ba câu trả lời live, bỏ trùng URL, bỏ trùng tiêu đề, giữ filter policy và facts xác nhận. UI local đã được kiểm tra HTTP 200/health `ok`; chưa deploy public. Đây là kiểm tra một phiên cụ thể, không bảo đảm mọi hội thoại.

[Transcript CLI v3](../transcripts/v3_ollama_20261110T113940609289.transcript.json) cũng có 3 lượt model thật, nhưng lượt policy chọn nhầm area; giữ nguyên làm bằng chứng lịch sử. Các transcript demo/fallback hoặc nhập liệu lỗi không được tính là phiên live thành công của profile cuối.

## B5. Unit tests và sửa lỗi code

Lần chạy full suite gần nhất: **205 passed, 0 failed, 0 skipped**. Tests dùng mock/local; kết nối mạng thật bị chặn. Đã hoàn thành **14 TODO**, có **30 trường hợp cho `deduplicate`** trong [test_tools_todo.py](../tests/test_tools_todo.py), vượt mức tối thiểu 3 test/tool mới.

| Phần | Hành vi đã kiểm tra/sửa |
|---|---|
| Tool mới | Bỏ trùng URL/title; giữ bản đầu, thứ tự, metadata và input; key thiếu/rỗng; input sai trả error dict; gọi qua registry/agent |
| Contract/runtime/scorer | Schema khớp code; required/type/enum/args thừa; so sánh đủ list items; nội dung gửi khớp nguyên văn; lỗi harness tính FAIL |
| `send` | Không nhận chuỗi/số thay boolean xác nhận; text hợp lệ; xử lý API lỗi; che token trong lỗi; dry-run không gửi thật |
| `policy` và UI | Truy vấn tiếng Việt, filter/top_k; giữ lịch sử JSON; phân biệt model live với demo/fallback; lưu transcript/version/hash |
| Provider | JSON sai, retry có giới hạn, không sửa tool/args; checker giữ draft gốc, tính chi phí và báo lỗi rõ |

[Tests checker](../tests/test_direct_answer_check.py) có 18 trường hợp mock. Các tests này kiểm tra code, không thay thế bằng chứng model thật. G04/G08 và hai lượt UI đầu còn kiểm tra tool mới thực sự bỏ đúng 1 mục trùng.

Chạy lại từ `starter_v0`:

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
.\.venv312\Scripts\python.exe -m pytest -v tests/test_tools_todo.py -k deduplicate
```

## B6. Reflection và giới hạn

- Prompt cần ưu tiên yêu cầu mới nhất, giữ ràng buộc còn hiệu lực, hỏi khi thiếu dữ liệu và xác nhận trước hành động gửi. Tool declaration cần phân biệt nguồn và mô tả args cụ thể.
- Không phải vòng nào cũng tăng điểm. Các candidate chưa tốt và run lỗi vẫn nằm trong log; chọn profile dựa trên kết quả đã đo.
- **Chưa đầy đủ execution online:** Tavily, Firecrawl và RapidAPI chưa có key trên máy kiểm tra. Không coi 21 lỗi execution là thành công nghiên cứu; cần cấu hình và thử lại các tool tương ứng khi sử dụng.
- **Chưa gửi Telegram thật**, chưa có UI public. `confirmed=true` ở G10 được chấm với dry-run, không phải bằng chứng đã đăng nội dung.
- Rubric không chấm hết chất lượng câu trả lời, câu hỏi làm rõ và độ đúng của nguồn/trích dẫn. Scope checker có thêm chi phí và vẫn có thể phân loại sai; cần đọc nội dung thực tế.

## B7. Small Local Model Challenge — bonus

Hai đối chứng dưới đây dùng nguyên cặp [prompt v3](system_prompt_v3.md) / [tools v3](tools_v3.yaml), cùng 20 base cases, scorer `schema-v2`, native thuần, không retry/checker, **20 model requests mỗi run**.

| Model | Case đúng | Routing / Args / Multi | Run |
|---|---|---|---|
| `qwen2.5:3b` | 15/20 | 0.80 / 0.75 / 0.8333 | [3B](../runs/v13-v3-qwen3b_B_base_ollama_20261110T215101202969.json) |
| `qwen3.5:4b-q4_K_M` | 17/20 | 0.85 / 0.85 / 1.00 | [4B](../runs/v13-v3-qwen35-4b_B_base_ollama_20261110T215208171859.json) |

Các vòng tối ưu tiêu biểu trên Qwen3.5 4B:

| Version | Giả thuyết/thay đổi | Case đúng | Run |
|---|---|---|---|
| v10-native-retry | Nhắc lại giao thức native khi thiếu call | 17/20, chưa tăng so với v9 | [v10](../runs/v10-native-retry_B_base_ollama_20261110T161125849239.json) |
| v11-schema-retry | Ràng buộc retry bằng schema để giảm thiếu call | 19/20 | [v11](../runs/v11-schema-retry_B_base_ollama_20261110T161728429621.json) |
| v12-local | Giữ ngữ cảnh gốc cho retry và nói rõ kiểu JSON trong prompt | 20/20 | [v12](../runs/v12-local_B_base_ollama_20261110T162157013557.json) |

Schema retry có ích trong các run này nhưng tăng ngân sách suy luận; v12 đổi cả prompt và ngữ cảnh adapter nên chưa tách được đóng góp từng phần. V13-scope-check giữ điểm routing và thêm kiểm tra câu trả lời ngoài phạm vi như B1/B2. Những thay đổi model, trọng số, quantization và runtime cũng phải được phân biệt khi so sánh.

**Bonus chưa hoàn tất:** đã có hai model và nhiều vòng tối ưu có log, nhưng chưa kiểm tra ngược profile local cuối trên cloud và chưa có bảng cloud/local. Nhóm thêm 1 tool mới nên chưa đạt bonus “UI + hơn 3 tool mới”.
