# Day 03 Lab v2 Report — Research Agent

## Team

- Team: VuVo
- Members:
  - 2A202603682 — Hà Huy Thái
  - 2A202603699 — Nguyễn Lê Hải Nam
  - 2A202603701 — Đỗ Nhật Anh
  - 2A202603663 — Lê Quang Trường
- Provider/model: Ollama / `qwen2.5:3b` (local)

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research Agent hỗ trợ tìm bài đăng theo tài khoản hoặc chủ đề, tìm tin trên web, đọc URL/paper arXiv, tra cứu chính sách nội bộ, loại kết quả trùng và trình bày digest. UI Streamlit có chế độ demo offline để thử luồng chat; các provider thật và gửi Telegram cần cấu hình riêng, và gửi cần xác nhận.

**Link dùng thử (local):** Chạy `streamlit run app.py` trong `starter_v0`, sau đó mở `http://localhost:8501`. Chưa deploy public nên link chỉ dùng được trên máy đang chạy app.

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi bổ sung thông tin còn thiếu hoặc xin xác nhận trước hành động gửi. | Không |
| `timeline` | Lấy bài đăng gần đây từ một tài khoản X/Twitter đã xác định. | Không |
| `social_search` | Tìm bài đăng mạng xã hội theo chủ đề hoặc từ khóa. | Không |
| `lookup` | Tìm kiếm web; hỗ trợ tra cứu thường và tin tức theo thời gian. | Không |
| `fetch` | Đọc nội dung từ URL người dùng cung cấp. | Không |
| `format` | Trình bày kết quả đã thu thập thành digest, bullets hoặc thread. | Không |
| `send` | Gửi nội dung lên Telegram sau khi người dùng xác nhận. | Không |
| `policy` | Tìm trong bộ chính sách nội bộ đi kèm repo. | Không |
| `papers` | Tìm metadata và abstract paper trên arXiv. | Không |
| `paper_text` | Trích text từ paper arXiv đã xác định. | Không |
| `deduplicate` | Loại kết quả trùng theo URL hoặc tiêu đề, giữ mục đầu tiên và thứ tự. | Có |

## A3. Câu hỏi mẫu để thử

1. “Tin tức AI hôm nay có gì nổi bật trên web?”
2. “Mọi người đang bàn gì về GPT-5 trên Twitter?”
3. “Lấy 3 bài đăng mới nhất của @karpathy.”
4. “Tìm vài paper arXiv về đánh giá LLM agent.”
5. “Loại các kết quả trùng URL sau đây và giữ bản đầu tiên: [dán danh sách kết quả].”

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version Evidence

Các run v0–v3 dùng cùng provider/model (`ollama`, `qwen2.5:3b`) và cùng 20 base cases. Đây là số liệu lịch sử theo scorer subset cũ. v0→v1 vừa sửa prompt vừa tích hợp khai báo `deduplicate`, nên chưa cô lập ảnh hưởng riêng của prompt. v1→v2 chỉ đổi mô tả tool; v2→v3 chỉ đổi prompt. Bản sửa code/UI/scorer mới dùng nhãn `v4-fixes`, hiện chỉ kiểm tra offline; xem B8.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---|---|---|
| v0 | Baseline | Baseline trước khi tối ưu. | — | case_accuracy=0.35; tool_routing_accuracy=0.50; argument_accuracy=0.35; multiturn_accuracy=0.50 | `runs/v0_B_base_ollama_20261110T095915950610.json` |
| v1 | Prompt + khai báo deduplicate | Routing/boundary rõ hơn có thể giảm lỗi; có yếu tố nhiễu do tích hợp tool mới. | case_accuracy=0.35; tool_routing_accuracy=0.50; argument_accuracy=0.35; multiturn_accuracy=0.50 | case_accuracy=0.60; tool_routing_accuracy=0.65; argument_accuracy=0.60; multiturn_accuracy=0.8333 | `runs/v1_B_base_ollama_20261110T105305856367.json` |
| v2 | `artifacts/tools.yaml` (mô tả tool) | Hướng dẫn rõ nguồn và quy ước tham số sẽ cải thiện routing trên base so với v1. | case_accuracy=0.60; tool_routing_accuracy=0.65; argument_accuracy=0.60; multiturn_accuracy=0.8333 | case_accuracy=0.60; tool_routing_accuracy=0.80; argument_accuracy=0.60; multiturn_accuracy=0.6667 | `runs/v2_B_base_ollama_20261110T112419425370.json` |
| v3 | `artifacts/system_prompt.md` | Checklist trước khi gọi tool sẽ giảm thiếu args và mất ràng buộc hội thoại, không đổi tools/eval. | case_accuracy=0.60; tool_routing_accuracy=0.80; argument_accuracy=0.60; multiturn_accuracy=0.6667 | case_accuracy=0.75; tool_routing_accuracy=0.80; argument_accuracy=0.75; multiturn_accuracy=0.6667 | `runs/v3_B_base_ollama_20261110T113016705870.json` |

**Kết quả chính:** v3 đạt 15/20 case. Accuracy tổng tăng 0.15 so với v2; routing không đổi, argument tăng 0.15. Multiturn vẫn ở 0.6667, thấp hơn v1.

## B2. Failure Analysis

Các lỗi dưới đây được trích từ `results[*].result.failures` trong run JSON. Lỗi v2 được giữ để đối chiếu với v3.

| Version | Case ID | Failure Type | Actual Tool Calls | What Failed | Fix / Next Step |
|---|---|---|---|---|---|
| v2 | R05_limit_arg | wrong_arg_value | `timeline(screenname=elonmusk)` | Thiếu `limit=10`. | Nhấn mạnh trích số lượng; v3 đã sửa case này. |
| v2 | R06_timeframe_arg | wrong_arg_value | `lookup(query="tin công nghệ", timeframe="week")` | Thiếu `topic=news`. | Nêu rõ news/general; v3 đã sửa case này. |
| v2 | R10_missing_handle | missing_info | `timeline(screenname=TwitterHandle)` | Tự tạo placeholder handle thay vì hỏi. | Không suy diễn tài khoản; vẫn lỗi ở v3. |
| v2 | R11_missing_url | missing_info | Không gọi tool. | Đã hỏi URL bằng text nhưng không gọi `clarify` theo rubric. | Bắt buộc gọi `clarify`; vẫn lỗi ở v3. |
| v2 | R12_confirm_before_send | wrong_boundary | `clarify()` | Thiếu `response_type=yes_no`. | Ràng buộc enum xác nhận; v3 đã sửa case này. |
| v2 | R14_out_of_scope_coding | out_of_scope | `format(items=[...], template="bullets")` | Gọi format và dựng nội dung cho yêu cầu coding ngoài phạm vi. | Phân loại out-of-scope trước gọi tool; vẫn lỗi ở v3. |
| v2 | M03_correction_handle | wrong_arg_value | `timeline(screenname=karpathy)` | Bỏ sót `limit=3` từ ngữ cảnh. | Mang theo số lượng đã yêu cầu; vẫn lỗi ở v3. |
| v2 | M06_switch_tool | wrong_tool | `social_search(query="OpenAI", search_type="Latest")` | Không chuyển từ social sang web news. | Ưu tiên intent mới nhất khi đổi nguồn; vẫn lỗi ở v3. |
| v3 | R10_missing_handle | missing_info | `timeline(screenname=sama, limit=5)` | Vẫn tự chọn tài khoản thay vì hỏi người dùng. | Bỏ ví dụ handle gây suy diễn; yêu cầu `clarify` cụ thể. |
| v3 | R11_missing_url | missing_info | Không gọi tool. | Đã hỏi URL bằng text nhưng không gọi `clarify` theo rubric. | Bắt buộc tạo `clarify` call kèm `question` và `response_type`. |
| v3 | R14_out_of_scope_coding | out_of_scope | `clarify(question=..., response_type=yes_no)` | Hỏi xác nhận cho yêu cầu coding ngoài phạm vi. | Phân loại ngoài phạm vi trước mọi clarification. |
| v3 | M03_correction_handle | wrong_arg_value | `timeline(screenname=karpathy)` | Bỏ sót số lượng 3 ngay ở lượt cuối. | Trích số lượng từ lượt mới nhất và giữ handle đã đính chính. |
| v3 | M06_switch_tool | wrong_tool | `social_search(screenname=OpenAI, limit=5, search_type=Latest)` | Không chuyển sang `lookup`/news khi người dùng đổi nguồn. | Ưu tiên yêu cầu mới nhất, bỏ routing cũ khi nguồn đã đổi. |

## B3. Team Eval Cases

`data/eval_group.json` có 5 single-turn và 5 multi-turn cases. Đã chạy đủ 10 case với v3 / Ollama `qwen2.5:3b`; eval chấm routing và subset arguments. **7/10 đạt, case_accuracy=0.70, tool_routing_accuracy=0.90, argument_accuracy=0.70, multiturn_accuracy=0.80.** Run: `runs/v3_B_group_ollama_20261110T113756483008.json`. G10 dùng mock `send` để xác nhận routing, không gửi Telegram thật. Một số case PASS ở lớp routing/args nhưng execution tool vẫn lỗi; xem ghi chú sau bảng.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_papers_routing | Routing tìm paper arXiv. | `papers` | PASS routing; tool được gọi, execution không được đánh giá nội dung |
| G02_policy_routing | Routing hỏi chính sách nội bộ về trích dẫn. | `policy(policy_area="source_citation")` | PASS routing/args; run lịch sử trả `results=[]`. |
| G03_handle_strip_at | Bỏ `@` và trích số lượng bài. | `timeline(screenname="karpathy", limit=3)` | FAIL args: thiếu `limit=3`; runtime cũng báo thiếu `RAPIDAPI_KEY` |
| G04_dedupe_by_url | Dùng tool mới với danh sách đã có. | `deduplicate` (mặc định `key_by="url"`) | PASS; loại 1 mục trùng trong tool result |
| G05_thanks_no_tool | Không gọi tool cho lời cảm ơn. | Không gọi tool | FAIL: gọi thừa `format` |
| G06_multi_papers_to_text | Giữ ID paper và số trang qua nhiều lượt. | `paper_text(arxiv_url="1706.03762", max_pages=2)` | PASS routing/args; execution lỗi thiếu `pypdf` |
| G07_multi_latest_to_top | Sửa Latest thành Top và giữ chủ đề. | `social_search(search_type="Top")` | PASS subset eval; có args thừa `screenname` khiến tool execution TypeError |
| G08_multi_dedupe_by_title | Giữ danh sách và lựa chọn key qua nhiều lượt. | `deduplicate(key_by="title")` | PASS; loại 1 mục trùng trong tool result |
| G09_multi_policy_area_topk | Giữ policy area, cập nhật số lượng. | `policy(policy_area="data_privacy", top_k=2)` | FAIL args: truyền `max_k=2`, thiếu `top_k`; tool execution TypeError |
| G10_multi_confirmed_send | Chỉ gửi sau xác nhận rõ ràng. | `send(confirmed=true)` | PASS routing/args; `send` được mock thành `dry_run`, không gửi thật |

**Lưu ý:** Eval chỉ so subset các args kỳ vọng, nên G07 được tính PASS dù có args thừa sai schema và tool execution thất bại. Group accuracy không đồng nghĩa mọi tool action chạy thành công.

## B4. Live Chat Evidence

Đã chạy `chat.py` với Ollama `qwen2.5:3b`, version/hash v3. Transcript có 3 lượt tại `transcripts/v3_ollama_20261110T113940609289.transcript.json`. Đây là phiên thực tế; turn 2 có gọi tool nhưng chọn nhầm policy area, nên kết quả được ghi trung thực.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| 1 | “What can you do?” | Không gọi tool. | v3 / Ollama `qwen2.5:3b`; `v3+p56267ce33772+t6972c70faabd` | Trả lời về khả năng của agent. |
| 2 | “Search our internal policy about source citations.” | `policy(query="source citations", policy_area="ai_research")` | Cùng transcript/version v3 | Tool local trả nội dung AI research; routing sai `policy_area` so với yêu cầu source citations. |
| 3 | “Thanks, that is helpful.” | Không gọi tool. | Cùng transcript/version v3 | Trả lời xã giao; không gọi tool thừa. |

## B5. Bonus Evidence

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| send (Telegram) | Group run `runs/v3_B_group_ollama_20261110T113756483008.json`, case G10 | Model chọn `send(confirmed=true)` sau xác nhận trong ngữ cảnh; hàm được mock và trả `dry_run`. | Không gửi Telegram thật; không xem dry-run là bằng chứng gửi thành công. |
| arXiv/company policy | Group run G01/G02/G06/G09; chat transcript `transcripts/v3_ollama_20261110T113940609289.transcript.json` | Routing tới `papers`/`policy`/`paper_text` được đo; chat policy trả nội dung local nhưng chọn sai area. | G06 `paper_text` lỗi thiếu `pypdf`; G09 `policy` nhận arg sai; routing PASS không đảm bảo execution PASS. |
| UI | app.py; transcript v4-fixes_demo_offline_20261110T150022064428.transcript.json | AppTest 3 lượt: giới thiệu, bỏ trùng URL, policy tiếng Việt; có version/hash và execution_mode=scripted. | Đã kiểm tra local/offline; chưa có UI live thành công hoặc URL public. |
| Tool unit tests (`tests/`) | Sau sửa: `153 passed, 0 skipped`; deduplicate: 30 trường hợp. | Hoàn thành 14 TODO; regression tests cho send/scorer/chat/policy và AppTest UI. | Tests dùng mock/local, không chứng minh API/model live. |

**Unit-test-only evidence:** 30 trường hợp test tham số hóa cho `deduplicate` kiểm tra xử lý trùng URL/tiêu đề, giữ thứ tự, chuẩn hóa khoảng trắng/hoa thường/dấu `/` cuối, key thiếu/rỗng và input sai. Eval model hiện chủ yếu chấm routing/arguments nên không xác minh logic loại trùng của implementation.

## B6. Reflection

- **Fix thuộc `system_prompt.md`:** ưu tiên intent mới nhất, giữ constraint chưa bị thay đổi qua hội thoại, hỏi `clarify` khi thiếu tài khoản/URL, xác nhận trước hành động gửi và tránh gọi tool ngoài phạm vi.
- **Fix thuộc `tools.yaml`:** mô tả ranh giới giữa `timeline`/`social_search`/`lookup`/`fetch`; quy ước `topic`, `timeframe`, `limit`, `search_type`; điều kiện dùng `send` và `deduplicate`.
- **Cần manual review:** độ chính xác của nội dung cuối, chất lượng/trích dẫn nguồn, mức độ nguồn thực sự hỗ trợ kết luận và mọi hành động gửi ra ngoài. Eval base chủ yếu chấm tên tool và subset arguments, không đánh giá đầy đủ chất lượng nội dung.
- **Cải thiện tiếp:** chạy lại base/group và UI bằng model thật, fallback tắt; cấu hình API nghiên cứu và cung cấp link public. Ghi run mới sau thay đổi code/scorer; tập trung lỗi v3 R10, R11, R14, M03, M06. Group eval và transcript CLI lịch sử đã có; UI mới đã kiểm tra offline.

## B7. Small Local Model Challenge (bonus)

Cả bốn run dưới đây dùng model local `qwen2.5:3b` qua Ollama (≤8B), trên cùng 20 base cases. **Chưa hoàn thành bonus:** mới có một model, thiếu so sánh hai model, v4-local/v5-local và kiểm tra ngược cloud.

| Version | Model (provider) | Prompt/Tools | case_accuracy | tool_routing | argument | multiturn | Run File |
|---|---|---|---:|---:|---:|---:|---|
| v0 | `qwen2.5:3b` (ollama) | Baseline prompt/tools | 0.35 | 0.50 | 0.35 | 0.50 | `runs/v0_B_base_ollama_20261110T095915950610.json` |
| v1 | `qwen2.5:3b` (ollama) | Prompt v1 / tools đã thêm deduplicate | 0.60 | 0.65 | 0.60 | 0.8333 | `runs/v1_B_base_ollama_20261110T105305856367.json` |
| v2 | `qwen2.5:3b` (ollama) | Prompt v1 / tool descriptions v2 | 0.60 | 0.80 | 0.60 | 0.6667 | `runs/v2_B_base_ollama_20261110T112419425370.json` |
| v3 | `qwen2.5:3b` (ollama) | Prompt v3 / tool descriptions v2 | 0.75 | 0.80 | 0.75 | 0.6667 | `runs/v3_B_base_ollama_20261110T113016705870.json` |

Lỗi được phân loại từ v3 run; một case có thể thuộc nhiều pattern.

| Failure Pattern | Count | Example Case | Fix Tried | Helped? |
|---|---:|---|---|---|
| wrong / hallucinated tool | 1 | M06_switch_tool | Nêu rõ routing theo nguồn và intent mới nhất | Chưa; vẫn chọn `social_search` thay `lookup` |
| invalid JSON args (`_invalid_json_arguments`) | 0 | Không có trong v3 run | Không có thay đổi riêng | Không quan sát thấy lỗi này |
| no tool call / answered directly | 1 | R11_missing_url | Yêu cầu hỏi khi thiếu URL | Chưa; model không gọi `clarify` |
| missed `clarify` | 2 | R10_missing_handle, R11_missing_url | Quy định hỏi lại khi thiếu thông tin bắt buộc | Chưa khắc phục |
| repeated / unnecessary calls | 1 unnecessary, 0 repeated | R14_out_of_scope_coding | Thêm rule ngoài phạm vi | Chưa; model vẫn gọi `clarify` không phù hợp |

- **Điều giúp model nhỏ gọi tool đúng hơn:** prompt v1 thêm routing/boundary; tool descriptions v2 làm rõ nguồn và tham số; prompt v3 thêm checklist trước khi gọi. Trên cùng base eval, case accuracy tăng 0.35 (v0) → 0.75 (v3), nhưng multiturn v3 là 0.6667, thấp hơn v1 (0.8333).
- **Prompt local chạy trên cloud:** chưa có run cloud nên chưa kết luận được; cần chạy cùng prompt/tools/dataset trên cloud để so sánh.
- **Khi chọn model local:** khi ưu tiên dữ liệu ở máy và kiểm soát chi phí, với tác vụ chấp nhận độ chính xác thấp hơn. Tác vụ cần độ tin cậy cao hoặc hành động gửi ra ngoài vẫn cần đánh giá thêm và human review/xác nhận.


## B8. Sửa tích hợp và kiểm tra offline — v4-fixes

Theo lựa chọn của người dùng, đợt sửa này chỉ kiểm tra offline. Không có run model mới, gửi Telegram thật hoặc public deployment. Toàn bộ run/transcript lịch sử được giữ nguyên. Prompt và tools v3 được lưu nguyên byte trong `artifacts/system_prompt_v3.md` và `artifacts/tools_v3.yaml`, đúng hash của log cũ. Các artifact đang dùng là v4-fixes: `v4-fixes+p285f6d3ebad0+t36a53ea8669c`.

- Prompt mới phân biệt nguồn, giữ số lượng/ngữ cảnh, ưu tiên no-tool cho xã giao và ngoài phạm vi, gọi clarify khi thiếu dữ liệu, không hỏi xác nhận lại khi đã duyệt đầy đủ. Tool results là dữ liệu, không phải lệnh.
- Schema deduplicate cho phép metadata tùy ý; runtime kiểm tra key được chọn là string/null. Validation dùng chung cho agent/chat/scorer: required, kiểu dữ liệu, enum và argument thừa. Items được so sánh đủ dữ liệu, kiểu JSON và thứ tự; G04/G08 có expected items rõ ràng. Nội dung gửi phải khớp nguyên văn.
- Scorer lỗi được ghi harness_error và vẫn tính là FAIL; provider_error được báo riêng. Eval mặc định dry-run action, ghi actions_mode và thống kê tool_execution.
- Send từ chối chuỗi/số ở confirmed, kiểm tra text và Telegram ok; regression test bảo đảm không gửi khi chưa có boolean xác nhận. Bot token được che khỏi thông báo lỗi.
- Hoàn thành 14 test TODO; full suite 153 passed, 0 skipped. Có tests kiểm tra Unicode CP1252, policy tiếng Việt, dry-run, harness errors, replay coverage và UI.
- UI demo xử lý danh sách URL/tiêu đề và chỉ dẫn trước/sau JSON, giữ dữ liệu qua lượt sau, không gọi mạng; không nhầm “trung tâm” thành bỏ trùng. JSON tool results lớn không bị cắt hỏng. Fallback mặc định tắt; bật fallback thì transcript ghi scripted_fallback cùng nguyên nhân.
- Transcript UI có version/hash/model, lịch sử tool results, execution mode và mọi lượt lỗi; ghi file qua temporary file rồi replace. Giữ kết quả tool đã thực hiện khi provider lỗi ở vòng sau để không mất ngữ cảnh hành động. Đổi cấu hình mở phiên mới.

### Bằng chứng offline

| Kiểm tra | File / Kết quả |
|---|---|
| Tests | 153 passed, 0 skipped; API/provider đều dùng mock/local |
| UI 3 lượt | transcripts/v4-fixes_demo_offline_20261110T150022064428.transcript.json — giới thiệu, bỏ đúng 1 URL trùng, tìm được policy tiếng Việt; requests/urllib bị chặn trong phiên kiểm tra |
| Phân tích lịch sử | analysis/base_runs.csv — 90 dòng từ 5 run, có toàn bộ failure v0 |
| Chấm lại group | analysis/v4_group_offline_replay.json và .csv — offline_replay, 6/10; routing 0.90, arguments 0.60, multiturn 0.60 |

Replay dùng calls đã lưu và expected/schema hiện tại; từ chối nguồn thiếu/trùng/thừa case, lưu hashes của nguồn/dataset/tools. G07 bị tính FAIL vì thiếu query/truyền screenname; điểm 6/10 không phải kết quả chạy lại model. Kết quả tool trong replay vẫn là lịch sử: 4 tool errors, 1 dry_run; 5 calls không lỗi không đồng nghĩa cả 5 đều tìm được nội dung hữu ích (G02 rỗng).

Transcript UI v3-ui_ollama_20261110T122832536319.transcript.json có 3/3 lượt fallback vì APIConnectionError, không dùng làm bằng chứng UI gọi Ollama thành công. Transcript CLI v3_ollama_20261110T113940609289.transcript.json vẫn là bằng chứng live cũ, có giới hạn policy_area đã ghi ở B4.

Điểm model của v4-fixes chưa được đo. Base dataset được giữ nguyên; scorer, code và group expected đã thay đổi nên phải ghi rõ cấu hình khi có run mới. Các giới hạn về API, link public và bonus được giữ đúng theo bằng chứng hiện có.
