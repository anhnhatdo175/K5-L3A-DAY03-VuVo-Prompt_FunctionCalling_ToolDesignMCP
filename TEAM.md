# Team VuVo

## Thành viên và phân công

| Vai trò                   | Họ tên            | MSSV        | Việc phụ trách                                                                                                                                      | Phạm vi file chính                                                                      |
| ------------------------- | ----------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Máy chạy AI local         | Đỗ Nhật Anh       | 2A202603701 | Cài Ollama/model, chạy preflight; chạy baseline v0 rồi các vòng v1–v3; ghi metric/version log. Khi phần này ổn, chạy so sánh model local cho bonus. | `artifacts/system_prompt.md`, `artifacts/version_log.csv`, các file `runs/`             |
| Tool mới                  | Hà Huy Thái       | 2A202603682 | Làm một tool mới, viết `TOOL.md` và ít nhất 3 unit test. Thống nhất tên/arguments với nhóm trước khi đăng ký tool.                                  | `tools/<tên-tool>/`, `tests/test_tools_todo.py`, phần đăng ký trong `tools/__init__.py` |
| Eval nhóm                 | Lê Quang Trường   | 2A202603663 | Soạn 10 case: 5 single-turn, 5 multi-turn; kiểm tra đúng schema và khớp tên tool đã thống nhất.                                                     | `data/eval_group.json`                                                                  |
| UI và giới thiệu          | Nguyễn Lê Hải Nam | 2A202603699 | Làm UI chạy được bằng Streamlit hoặc Vercel; điền Phần A của report và chuẩn bị câu hỏi demo.                                                       | UI mới (ví dụ `app.py`), Phần A trong `artifacts/REPORT.md`                             |

---
