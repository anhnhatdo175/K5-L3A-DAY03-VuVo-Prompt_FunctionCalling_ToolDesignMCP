---
name: deduplicate
track: bonus
kind: local_formatter
provider: none
requires_env: []
inputs: [items, key_by]
outputs: [tool, items, removed_count]
side_effect: false
---
# deduplicate

Loại các kết quả nghiên cứu bị trùng theo URL hoặc tiêu đề trước khi tổng hợp.
Tool chạy local, cho kết quả xác định, không gọi API, không cần model hoặc API
key, không ghi file và không thay đổi danh sách đầu vào.

## Khi nào dùng

- Đã có danh sách kết quả từ một hay nhiều nguồn và cần loại mục trùng.
- Người dùng yêu cầu giữ lần xuất hiện đầu tiên theo URL hoặc tiêu đề.
- Cần làm sạch kết quả trước khi gọi tool `format` để tạo bản tổng hợp.

## Khi nào không dùng

- Chưa có kết quả và cần tìm kiếm hoặc tải nội dung mới.
- Cần xếp hạng, kiểm tra độ tin cậy, gộp nội dung hoặc phát hiện hai bài viết
  có cùng ý nghĩa nhưng khác URL/tiêu đề.
- Cần chuẩn hóa URL đầy đủ, chẳng hạn bỏ tham số theo dõi, fragment hay
  chuyển hướng. Tool chỉ xử lý khoảng trắng, chữ hoa/thường và dấu `/` cuối.

## Arguments

Hàm: `deduplicate(items, key_by="url")`.

| Argument | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `items` | List các dict | Có | — | Danh sách kết quả; giữ nguyên mọi trường như `title`, `url`, `source`, `summary` hoặc trường bổ sung. |
| `key_by` | Chuỗi enum: `"url"`, `"title"` | Không | `"url"` | Trường dùng để nhận diện mục trùng. |

## Quy tắc xử lý

1. Duyệt theo thứ tự đầu vào; giữ mục xuất hiện đầu tiên cho mỗi key không rỗng.
2. Khi so sánh, bỏ khoảng trắng ở hai đầu và dùng `casefold()` để so sánh không
   phân biệt chữ hoa/thường. Với `key_by="url"`, bỏ thêm các dấu `/` ở cuối.
3. Không sửa URL, tiêu đề hay các trường khác trong những mục được giữ lại.
4. Mục thiếu trường được chọn, có giá trị `None`, hoặc có key rỗng sau chuẩn hóa
   đều được giữ; các mục này không bị coi là trùng nhau.
5. Danh sách rỗng là hợp lệ và trả `items: []`, `removed_count: 0`.

Ví dụ URL `" HTTPS://EXAMPLE.COM/a/ "` trùng với `"https://example.com/a"`.
URL `"https://example.com/a?ref=1"` vẫn khác `"https://example.com/a"`.

## Output và lỗi

Kết quả thành công:

```json
{
  "tool": "deduplicate",
  "items": [{"title": "Bài được giữ đầu tiên", "url": "https://example.com/a/"}],
  "removed_count": 1
}
```

Các trường hợp dữ liệu không hợp lệ trong bảng dưới được xử lý bằng error dict
theo chuẩn chung của project:

```json
{
  "tool": "deduplicate",
  "error": "ValueError",
  "message": "key_by must be 'url' or 'title'"
}
```

| Input không hợp lệ | `error` |
|---|---|
| `items` không phải list | `TypeError` |
| Một phần tử trong `items` không phải dict | `TypeError` |
| Giá trị của trường được chọn không phải chuỗi hoặc `None` | `TypeError` |
| `key_by` khác `"url"` hoặc `"title"` | `ValueError` |

Nếu có phần tử không hợp lệ, trả lỗi cho cả lần gọi, không trả danh sách đã xử
lý dở. Giá trị ở trường không được chọn không tham gia kiểm tra key.
`items` là argument bắt buộc; gọi hàm Python thiếu argument này vẫn phát sinh
`TypeError` của Python trước khi vào phần kiểm tra dữ liệu.

## Ví dụ chạy trực tiếp

Từ thư mục `starter_v0`, gọi qua registry:

```python
from tools import TOOL_FUNCTIONS

deduplicate = TOOL_FUNCTIONS["deduplicate"]

items = [
    {"title": "Bài đầu", "url": " HTTPS://EXAMPLE.COM/a/ ", "source": "Nguồn A"},
    {"title": "Bản trùng", "url": "https://example.com/a", "source": "Nguồn B"},
    {"title": "Chưa có URL", "summary": "Vẫn được giữ"},
]
result = deduplicate(items)
assert result == {
    "tool": "deduplicate",
    "items": [items[0], items[2]],
    "removed_count": 1,
}

by_title = deduplicate(
    [{"title": "  Research Agent  "}, {"title": "research agent"}],
    key_by="title",
)
assert by_title["removed_count"] == 1
assert len(by_title["items"]) == 1
```

## Kiểm thử offline

Dự án dùng Python 3.12, được cố định bằng `.python-version` tại thư mục gốc repo.

Trên Windows, dùng môi trường Python 3.12 riêng để cài các thư viện phục vụ
tests. Nếu dùng Python 3.15 mà PyYAML phải build từ source và báo thiếu Microsoft
Visual C++, có thể dùng các lệnh dưới đây từ thư mục `starter_v0`:

```powershell
uv venv --python 3.12 .venv312
uv pip install --python .venv312\Scripts\python.exe --only-binary PyYAML -r requirements.txt
```

`uv` tự tải Python 3.12 nếu chưa có. `--only-binary pyyaml` yêu cầu bản PyYAML
đóng gói sẵn thay vì build bằng C++. Thư mục `.venv312/` được gitignore; môi
trường `.venv/` đang có không bị thay đổi.

Chạy tests bằng chính Python của môi trường mới:

```powershell
.\.venv312\Scripts\python.exe -m pytest -v tests/test_tools_todo.py -k deduplicate
.\.venv312\Scripts\python.exe -m pytest -v tests/test_tool_contract.py
.\.venv312\Scripts\python.exe -m pytest -q
```

Tests kiểm tra loại trùng và giữ thứ tự/mục đầu tiên, xử lý key thiếu/rỗng,
chuẩn hóa URL/tiêu đề, cùng các input không hợp lệ. Không cần mock HTTP vì tool
không sử dụng mạng.

## Tích hợp và bàn giao eval

- Hàm đã được đăng ký dưới tên `deduplicate` trong `tools/__init__.py` và khai
  báo trong `artifacts/tools.yaml`: `items` là array các object bắt buộc;
  `key_by` là string enum `[url, title]`, mặc định `url` và không bắt buộc.
- Bạn phụ trách eval dùng cùng tên và arguments. Câu hỏi mẫu: “Loại các kết quả
  trùng URL trong danh sách sau, giữ bản đầu tiên:
  `[{"title":"A","url":"https://example.com/a/"},{"title":"B","url":"https://example.com/a"}]`”.
  Tool mong đợi là `deduplicate`; `items` là danh sách trên, `key_by` có thể bỏ
  qua hoặc đặt `"url"`; kết quả giữ bản A và `removed_count` bằng `1`.
- Đã có bằng chứng model trong `runs/v3_B_group_ollama_20261110T113756483008.json`:
  G04 bỏ trùng URL và G08 bỏ trùng tiêu đề đều nhận đủ danh sách, giữ đúng mục
  đầu tiên và trả `removed_count=1`.
- Group dataset hiện so sánh đầy đủ `items` và `key_by`. Scorer mới đọc được
  list-of-dict và kiểm tra schema; bản chấm lại offline nằm trong
  `analysis/v4_group_offline_replay.json`, không phải một lần gọi model mới.
- UI demo offline dùng danh sách JSON thật của người dùng; có thể gửi danh sách
  ở lượt trước rồi yêu cầu đổi sang xét tiêu đề. Không có HTTP hay API credit.
