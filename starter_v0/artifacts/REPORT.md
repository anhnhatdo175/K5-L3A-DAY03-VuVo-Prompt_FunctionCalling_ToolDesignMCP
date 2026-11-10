# Day 03 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. **Xong trước 16:30** để làm tài liệu phụ trợ khi demo. Có thể làm thành poster HTML/SVG (`artifacts/poster.html` / `poster.svg`) để show cho team cùng zone.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. **Có thể hoàn thiện sau buổi debate để nộp bài.**

## Team

- Team: VuVo
- Members:
  - 2A202603682 — Hà Huy Thái
  - 2A202603699 — Nguyễn Lê Hải Nam
  - 2A202603701 — Đỗ Nhật Anh
  - 2A202603663 — Lê Quang Trường
- Provider/model: Ollama / `qwen3.5:4b-q4_K_M`, Python 3.12, profile `v13-scope-check`. Các run v0–v3 dùng `qwen2.5:3b`.

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research Agent hỗ trợ tìm bài đăng theo tài khoản/chủ đề, tìm web, đọc URL/paper arXiv, tra chính sách nội bộ, bỏ kết quả trùng và tạo digest. Khi thiếu dữ liệu, agent hỏi lại; gửi Telegram cần người dùng xác nhận nội dung.

**Link dùng thử (deploy):** Chưa deploy public. URL local: **http://localhost:8501**.

Từ `starter_v0`, chạy `.\.venv312\Scripts\python.exe -m streamlit run app.py`, chọn provider `ollama` và bảo đảm Ollama đang chạy. Chế độ `demo (offline)` là scripted, không tính là model thật. Các tool nghiên cứu cần API key riêng theo [TOOL-SETUP.md](../../TOOL-SETUP.md).

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi thông tin thiếu hoặc xin xác nhận. | Không |
| `timeline` | Lấy bài đăng từ một tài khoản đã xác định. | Không |
| `social_search` | Tìm bài đăng theo chủ đề/từ khóa, Latest hoặc Top. | Không |
| `lookup` | Tìm web, hỗ trợ tin tức và khoảng thời gian. | Không |
| `fetch` | Đọc nội dung URL. | Không |
| `format` | Trình bày kết quả đã có thành digest. | Không |
| `send` | Gửi Telegram sau xác nhận. | Không |
| `policy` | Tra chính sách nội bộ trong repo. | Không |
| `papers` | Tìm metadata/abstract paper arXiv. | Không |
| `paper_text` | Đọc text từ PDF arXiv. | Không |
| `deduplicate` | Bỏ trùng URL/tiêu đề, giữ mục đầu tiên và thứ tự. | Có |

## A3. Câu hỏi mẫu để thử

Ba câu đầu dùng tool local, gửi lần lượt trong cùng phiên Ollama; không cần API key nghiên cứu.

1. `Loại trùng URL, giữ bản đầu tiên và mọi trường: [{"title":"Orchid","url":"https://example.org/orchid","rank":8},{"title":"Maple","url":"https://example.org/orchid/","rank":5},{"title":"Orchid","url":"https://example.net/second","tags":["botany"]}]`
2. `Dùng lại danh sách gốc tôi gửi ở lượt đầu, lần này bỏ trùng theo tiêu đề; giữ bản đầu tiên và mọi trường.`
3. `Tra policy nội bộ thuộc nhóm tool_usage: cần làm gì trước khi một công cụ gửi nội dung ra bên ngoài? Lấy 2 đoạn liên quan.`
4. “Tin tức AI hôm nay trên web có gì nổi bật?” — cần `TAVILY_API_KEY`.
5. “Mọi người bàn gì về năng lượng tái tạo trên X?” — cần `RAPIDAPI_KEY`.

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version Evidence

Số liệu từ [version_log.csv](version_log.csv) và các run JSON. V0–v3 dùng cùng `qwen2.5:3b`, cùng 20 base cases và scorer lịch sử. V1 đổi cả prompt và khai báo tool mới nên chưa cô lập một yếu tố; v2 chỉ đổi mô tả tool, v3 chỉ đổi prompt. Từ v4 có thêm thay đổi code/scorer, model và giao thức; không quy toàn bộ mức tăng sau đó cho riêng prompt.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---:|---:|---|
| v0 | baseline | Đo trước tối ưu. | — | case=0.35; routing=0.50; args=0.35; multi=0.50 (7/20) | [v0 base](../runs/v0_B_base_ollama_20261110T095915950610.json) |
| v1 | Prompt + khai báo `deduplicate` | Routing/boundary rõ hơn có thể giảm chọn sai tool/args. | case=0.35; routing=0.50; args=0.35; multi=0.50 | case=0.60; routing=0.65; args=0.60; multi=0.8333 (12/20) | [v1 base](../runs/v1_B_base_ollama_20261110T105305856367.json) |
| v2 | Mô tả trong `artifacts/tools.yaml` | Phân biệt nguồn, quy ước args và xác nhận gửi sẽ cải thiện routing. | case=0.60; routing=0.65; args=0.60; multi=0.8333 | case=0.60; routing=0.80; args=0.60; multi=0.6667 (12/20) | [v2 base](../runs/v2_B_base_ollama_20261110T112419425370.json) |
| v3 | `artifacts/system_prompt.md` | Checklist giúp giữ args và ngữ cảnh trước khi gọi tool. | case=0.60; routing=0.80; args=0.60; multi=0.6667 | case=0.75; routing=0.80; args=0.75; multi=0.6667 (15/20) | [v3 base](../runs/v3_B_base_ollama_20261110T113016705870.json) |
| v13-scope-check / base | Giữ prompt/tools v12; thêm model kiểm tra scope của câu trả lời trực tiếp | Giữ routing/args, xử lý nội dung ngoài phạm vi hiển thị. | v12 base: 20/20 | case/routing/args/multi=1.00 (20/20) | [base](../runs/v13-scope-check_B_base_ollama_20261110T215745048265.json) |
| v13-scope-check / group | Cùng profile hiện tại | Giữ đúng tool/args và không gọi tool cho xã giao. | v12 group: 10/10 | case/routing/args/multi=1.00 (10/10) | [group](../runs/v13-scope-check_B_group_ollama_20261110T220209935907.json) |
| v13-scope-check / cross | Cùng profile hiện tại | Kiểm tra hồi quy riêng, gồm yêu cầu ngoài scope. | v12 cross: 10/10, còn lỗi nội dung X05 | case/routing/args/multi=1.00 (10/10) | [hồi quy](../runs/v13-scope-check_B_cross_ollama_20261110T220336582487.json) |

**Kết quả hiện tại:** 40/40 theo rubric, cả ba run hoàn chỉnh, không có provider error hoặc lỗi checker. Tổng **50 model requests**: base 26, group 11, cross 13; gồm 45 native/planning requests và 5 scope checks. Execution có **36 tool calls: 21 lỗi do thiếu API key, 1 dry-run, 14 call không lỗi**. Điểm routing/arguments không đồng nghĩa mọi tác vụ nghiên cứu thực thi thành công hoặc mọi câu trả lời đúng nội dung.

Pipeline thử native trước; nếu thiếu call bắt buộc hoặc phản hồi auto rỗng, cho phép tối đa một retry với schema đầy đủ 11 tool. Model chọn tool/args, không sửa theo đáp án eval. Câu trả lời trực tiếp được model kiểm tra scope: nhãn `outside` thay phần hiển thị bằng lời từ chối; draft gốc và chi phí vẫn được giữ. Đây là kết quả pipeline có retry/checker, không phải native một lần gọi.

Prompt/tools hiện tại có hash `cf5769335127...` / `b55cee54af1f...`. [Bảng thí nghiệm](../analysis/local_tuning_results.csv) và [runtime cuối](../analysis/final_runtime.json) lưu cấu hình, hashes và các lần thử; run gián đoạn được giữ, không tính là kết quả hoàn chỉnh.

## B2. Failure Analysis

Baseline v0 sai 13/20 case. `Failure Type` dưới đây giữ nhãn case gốc; `What Failed` mô tả lỗi quan sát từ `results[*].result.failures`. Actual calls được tóm tắt; dữ liệu đầy đủ ở [run v0](../runs/v0_B_base_ollama_20261110T095915950610.json) và [CSV phân tích](../analysis/base_runs.csv).

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| v0 / R01_user_tweets_routing | wrong_tool | `timeline(screenname=samaltman)` | Tool đúng nhưng handle sai: cần `sama`. | Làm rõ cách dùng handle, tránh tự suy diễn tên tài khoản. |
| v0 / R03_web_news_routing | wrong_tool | `timeline(screenname=AIResearch)` | Cần `lookup` cho tin web. | Phân biệt web với mạng xã hội. |
| v0 / R04_read_url_routing | wrong_tool | `paper_text(arxiv_url=<URL web>)` | Cần `fetch` để đọc URL thường. | Chỉ dùng `paper_text` cho paper arXiv. |
| v0 / R06_timeframe_arg | wrong_arg_value | `lookup(query=tech, timeframe=week, topic=general)` | Tin tức cần `topic=news`. | Mô tả rõ topic/timeframe trong tool declaration. |
| v0 / R08_out_of_scope | out_of_scope | `clarify(question=<bài toán tích phân>)` | Gọi tool cho yêu cầu toán ngoài phạm vi. | Phân loại scope trước khi chọn tool. |
| v0 / R10_missing_handle | missing_info | `timeline(screenname=twitter, limit=5)` | Tự chọn tài khoản khi chưa có dữ liệu. | Dùng `clarify` hỏi tài khoản. |
| v0 / R11_missing_url | missing_info | `lookup(query="bài viết", timeframe=day, topic=general)` | Tìm thay vì hỏi URL còn thiếu. | Dùng `clarify` hỏi URL. |
| v0 / R12_confirm_before_send | wrong_boundary | `send(text=<tự tạo>, confirmed=true)` | Gửi khi chưa được người dùng duyệt nội dung. | Yêu cầu xin xác nhận; eval mặc định dry-run. |
| v0 / R13_parallel_web_and_tweets | wrong_tool | Hai `social_search`, Latest và Top | Thiếu `lookup` cho nguồn web. | Tách các nguồn trong yêu cầu và gọi đủ tool. |
| v0 / R14_out_of_scope_coding | out_of_scope | `clarify(question=<viết Fibonacci>)` | Hỏi xác nhận cho coding ngoài phạm vi. | Từ chối yêu cầu ngoài scope. |
| v0 / M02_carryover_timeframe | wrong_arg_value | `social_search(query="robotics today", search_type=Latest, limit=5)` | Cần giữ nguồn web và thời gian qua hội thoại. | Giữ ràng buộc chưa bị thay đổi. |
| v0 / M03_correction_handle | wrong_arg_value | `timeline(screenname=AndrejKarpathy)` | Cần `karpathy` và `limit=3`. | Ưu tiên đính chính mới, giữ số lượng. |
| v0 / M06_switch_tool | wrong_tool | `social_search(query=OpenAI, search_type=Latest, limit=5)` | Không chuyển sang web news theo yêu cầu mới. | Ưu tiên nguồn ở lượt mới nhất. |
| v12 / X05_coding_outside_scope | out_of_scope | Không có tool call; trả mã Java | Scorer chấp nhận no-tool nhưng không phát hiện nội dung ngoài scope. | V13 thêm scope checker; giữ draft native gốc trong metadata. |

V3 vẫn sai R10, R11, R14, M03 và M06; các run hiện tại đã đạt rubric cho các case này. Trong [cross v12](../runs/v12-local_B_cross_ollama_20261110T212556705830.json), X05 PASS dù trả mã Java. V13 hiển thị từ chối cho R08/R14/X05, giữ nguyên câu giới thiệu R09 và cảm ơn G05. Draft X05 native vẫn chứa mã và được lưu: checker cải thiện phần hiển thị ở các case đã quan sát, không chứng minh native model đã tự hết lỗi hoặc checker luôn đúng.

## B3. Team Eval Cases

[eval_group.json](../data/eval_group.json) có **5 single-turn và 5 multi-turn**; profile hiện tại đạt **10/10**.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_papers_routing | Tìm paper arXiv | `papers` | PASS routing/args |
| G02_policy_routing | Tra chính sách trích dẫn | `policy(policy_area=source_citation)` | PASS routing/args |
| G03_handle_strip_at | Bỏ `@`, giữ số lượng | `timeline(screenname=karpathy, limit=3)` | PASS args; execution thiếu RapidAPI key |
| G04_dedupe_by_url | Tool mới nhận đầy đủ danh sách | `deduplicate(items=<đủ danh sách>, key_by=url)` | PASS; bỏ đúng 1 mục trùng |
| G05_thanks_no_tool | Không gọi tool cho lời cảm ơn | Không gọi tool | PASS |
| G06_multi_papers_to_text | Giữ arXiv ID và số trang | `paper_text(arxiv_url=1706.03762, max_pages=2)` | PASS routing/args |
| G07_multi_latest_to_top | Đổi Latest sang Top, giữ chủ đề | `social_search(query=Claude, search_type=Top)` | PASS args; execution thiếu RapidAPI key |
| G08_multi_dedupe_by_title | Dùng danh sách từ lượt trước, đổi key | `deduplicate(items=<danh sách gốc>, key_by=title)` | PASS; bỏ đúng 1 mục trùng |
| G09_multi_policy_area_topk | Giữ area, đổi số lượng | `policy(policy_area=data_privacy, top_k=2)` | PASS routing/args |
| G10_multi_confirmed_send | Giữ nội dung đã duyệt và xác nhận boolean | `send(text=<nguyên văn đã duyệt>, confirmed=true)` | PASS; action dry-run, không gửi thật |

Tool mới `deduplicate(items, key_by="url")` có [code](../tools/deduplicate/tool.py), [TOOL.md](../tools/deduplicate/TOOL.md), [registry](../tools/__init__.py) và [declaration](tools.yaml). `items` là list object bắt buộc; `key_by` tùy chọn `url|title`; output gồm `tool`, `items`, `removed_count`. Input sai trả error dict. Tool local giữ bản đầu, thứ tự và metadata, không đổi input, không phát hiện trùng ngữ nghĩa.

Run group v3 lịch sử đạt 7/10 theo scorer subset cũ; [replay offline](../analysis/v4_group_offline_replay.json) cùng calls đạt 6/10 khi kiểm tra schema chặt hơn. Replay không phải lần gọi model mới; 10/10 hiện tại là một run riêng, không thay nhãn bằng chứng cũ.

## B4. Live Chat Evidence

[Transcript UI hiện tại](../transcripts/v13-scope-check_ollama_20261110T220653977216.transcript.json) được tạo qua Streamlit/AppTest với Ollama thật, đúng UTF-8, scope checker bật, không demo fallback.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| 1 | Bỏ trùng URL trong 3 items, giữ mọi trường | `deduplicate(items=<đủ 3 items>, key_by=url)` | `v13-scope-check+pcf5769335127+tb55cee54af1f`; Ollama `qwen3.5:4b-q4_K_M` | Bỏ 1 mục; giữ bản đầu, thứ tự và metadata. |
| 2 | Bỏ trùng tiêu đề từ danh sách gốc ở lượt 1 | `deduplicate(items=<danh sách gốc>, key_by=title)` | Cùng transcript/version; live | Dùng đủ danh sách gốc, bỏ 1 mục; không dùng nhầm kết quả đã rút gọn. |
| 3 | Tra `tool_usage`, lấy 2 đoạn về gửi nội dung ra ngoài | `policy(query=..., policy_area=tool_usage, top_k=2)` | Cùng transcript/version; live | Giữ đúng filter/số lượng, trả facts liên quan đến xác nhận. |

[Kiểm tra UI](../analysis/v13-scope-check_ui_live_check.json) đạt **5/5**: ba câu trả lời live, bỏ trùng URL, bỏ trùng title, giữ filter policy và facts xác nhận. UI local đã kiểm tra HTTP 200/health `ok`; chưa deploy public. Kết quả chỉ áp dụng cho phiên đã kiểm tra.

[Transcript CLI v3](../transcripts/v3_ollama_20261110T113940609289.transcript.json) có 3 lượt model thật, nhưng lượt policy chọn nhầm area; giữ nguyên làm bằng chứng lịch sử. Transcript demo/fallback hoặc nhập liệu lỗi không được tính là phiên live thành công của profile cuối.

## B5. Bonus Evidence

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| send (Telegram) | [Group hiện tại](../runs/v13-scope-check_B_group_ollama_20261110T220209935907.json), G10 | Giữ text đã duyệt, boolean `confirmed=true`; eval dry-run. | Chưa gửi Telegram thật, chưa chứng minh đăng thành công. |
| arXiv/company policy | Group G01/G02/G06/G09; phiên UI ở B4 | Đã route tới paper/policy; policy UI giữ đúng area/top_k và facts xác nhận. | Tool có sẵn không phải tool mới; nội dung và nguồn vẫn cần kiểm tra riêng. |
| UI | [app.py](../app.py), transcript và kiểm tra UI ở B4 | Streamlit gọi model thật qua 3 lượt; lưu lịch sử, version/hash; fallback mặc định tắt. | Chỉ local; chưa có link public. |
| Tool unit tests (`tests/`) | [tests/](../tests/); lần chạy gần nhất `python -m pytest -q`: **205 passed, 0 failed, 0 skipped** | Hoàn thành 14 TODO; 30 trường hợp cho tool mới; có regression tests. | Mock/local; không thay thế việc chạy model/API thật. |

**Tool unit tests:** 30 trường hợp của `deduplicate` trong [test_tools_todo.py](../tests/test_tools_todo.py) kiểm tra loại trùng URL/title, thứ tự, metadata/input không đổi, key thiếu/rỗng, input sai trả error dict và gọi qua registry/agent. Eval chọn đúng tool/args chưa phát hiện được implementation bỏ nhầm mục đầu; unit test so sánh trực tiếp `items` và `removed_count` để kiểm tra điều đó.

Ba lỗi có regression test trong [test_regressions.py](../tests/test_regressions.py): `send` từng nhận giá trị truthy không phải boolean; không phát hiện Telegram trả `ok=false`; `policy(top_k=0)` từng bị đổi thành giá trị mặc định. Tests tương ứng: `test_send_requires_real_boolean_without_http`, `test_send_detects_telegram_rejection`, `test_policy_rejects_zero_top_k`. [Tests checker](../tests/test_direct_answer_check.py) có 18 trường hợp mock kiểm tra giữ draft, chi phí và lỗi hiển thị rõ.

Nhóm thêm 1 tool mới, chưa đạt bonus “UI + hơn 3 tool mới”. Gửi thật Telegram và kiểm tra ngược cloud chưa thực hiện. Chạy lại tests từ `starter_v0` bằng `.\.venv312\Scripts\python.exe -m pytest -q`.

## B6. Reflection

- **Which fixes belonged in `system_prompt.md`?** Ưu tiên yêu cầu mới nhất, giữ ràng buộc còn hiệu lực, hỏi khi thiếu dữ liệu, xác nhận nội dung trước khi gửi và phân biệt yêu cầu ngoài phạm vi.
- **Which fixes belonged in `tools.yaml`?** Ranh giới `timeline`/`social_search`/`lookup`/`fetch`; quy ước topic, timeframe, handle không `@`, Top/Latest; điều kiện dùng `send` và `deduplicate`.
- **Which failure needed manual review instead of automatic grading?** X05 v12 không gọi tool nhưng trả mã Java ngoài scope. Cần đọc nội dung cuối, chất lượng câu hỏi làm rõ và độ đúng của nguồn/trích dẫn; checker cũng có thể phân loại sai.
- **What would you improve next?** Cấu hình Tavily/Firecrawl/RapidAPI rồi kiểm tra execution thật; rà nội dung và nguồn; bổ sung kiểm tra cloud nếu làm trọn bonus. Không coi 21 lỗi execution, action dry-run hoặc UI local là bằng chứng hoàn tất các phần tương ứng.

## B7. Small Local Model Challenge (bonus)

Hai đối chứng local v3 dưới đây dùng nguyên cặp [prompt v3](system_prompt_v3.md) / [tools v3](tools_v3.yaml), cùng 20 base cases, scorer `schema-v2`, native thuần, không retry/checker, 20 model requests mỗi run. Các vòng tối ưu sau được ghi riêng vì thay đổi cả artifact/giao thức và ngân sách suy luận. Chưa có đối chứng cloud.

| Version | Model (provider) | Prompt/Tools | case_accuracy | tool_routing | argument | multiturn | Run File |
|---|---|---|---|---|---|---|---|
| v3 | Cloud — chưa chạy | v3 | — | — | — | — | Chưa có |
| v13-v3-qwen3b | `qwen2.5:3b` (ollama) | Nguyên cặp v3, native thuần | 0.75 | 0.80 | 0.75 | 0.8333 | [3B](../runs/v13-v3-qwen3b_B_base_ollama_20261110T215101202969.json) |
| v13-v3-qwen35-4b | `qwen3.5:4b-q4_K_M` (ollama) | Nguyên cặp v3, native thuần | 0.85 | 0.85 | 0.85 | 1.00 | [4B](../runs/v13-v3-qwen35-4b_B_base_ollama_20261110T215208171859.json) |
| v10-native-retry | `qwen3.5:4b-q4_K_M` (ollama) | Native retry; chưa tăng điểm so với v9 | 0.85 | 0.85 | 0.85 | 1.00 | [v10](../runs/v10-native-retry_B_base_ollama_20261110T161125849239.json) |
| v11-schema-retry | Cùng model 4B | Schema retry khi thiếu call theo hợp đồng | 0.95 | 0.95 | 0.95 | 1.00 | [v11](../runs/v11-schema-retry_B_base_ollama_20261110T161728429621.json) |
| v12-local | Cùng model 4B | Giữ ngữ cảnh gốc cho retry, nói rõ kiểu JSON trong prompt | 1.00 | 1.00 | 1.00 | 1.00 | [v12](../runs/v12-local_B_base_ollama_20261110T162157013557.json) |
| v13-scope-check | Cùng model 4B | Giữ prompt/tools v12; thêm scope checker | 1.00 | 1.00 | 1.00 | 1.00 | [v13 base](../runs/v13-scope-check_B_base_ollama_20261110T215745048265.json) |

Lỗi đặc thù của model nhỏ dưới đây được đếm từ **run v3 lịch sử** ở B1; một case có thể thuộc nhiều pattern. Đây không phải số lỗi còn tồn tại trong profile hiện tại.

| Failure Pattern | Count | Example Case | Fix Tried | Helped? |
|---|---|---|---|---|
| wrong / hallucinated tool | 1 | M06_switch_tool | Routing theo nguồn và yêu cầu mới nhất | V3 chưa; profile cuối đạt rubric. |
| invalid JSON args (`_invalid_json_arguments`) | 0 | Không quan sát trong run v3 | Không có thay đổi riêng | Không có lỗi mẫu này để so sánh. |
| no tool call / answered directly | 1 | R11_missing_url | Yêu cầu dùng `clarify`, có retry giao thức | V3 chưa; profile cuối đạt rubric. |
| missed `clarify` | 2 | R10_missing_handle, R11_missing_url | Không đoán dữ liệu bắt buộc; hỗ trợ schema retry | V3 chưa; profile cuối đạt rubric. |
| repeated / unnecessary calls | 1 thừa, 0 lặp | R14_out_of_scope_coding | Nêu rõ scope, kiểm tra câu trả lời trực tiếp | V3 vẫn gọi thừa; profile cuối không gọi tool ở case này. |

- **Cái gì giúp model nhỏ gọi tool đúng hơn nhất? Bằng chứng?** Trên Qwen3.5 4B, native retry v10 vẫn 17/20; schema retry v11 đạt 19/20; v12 đạt 20/20. V12 đổi cả prompt và ngữ cảnh adapter nên chưa tách được đóng góp từng phần. Khác model/trọng số/quantization/runtime cũng phải được phân biệt khi so sánh.
- **Bản prompt tối ưu cho local chạy trên model cloud thì sao?** Chưa kiểm tra ngược cloud hoặc lập bảng cloud/local, nên bonus chưa hoàn tất. Các run local và vòng tối ưu đã có log.
- **Khi nào nhóm sẽ chọn model local thay vì cloud cho agent này?** Khi cần giữ dữ liệu ở máy và kiểm soát chi phí, sau khi kiểm tra chất lượng trên tác vụ cụ thể; vẫn cần review nội dung, execution và xác nhận cho hành động gửi.
