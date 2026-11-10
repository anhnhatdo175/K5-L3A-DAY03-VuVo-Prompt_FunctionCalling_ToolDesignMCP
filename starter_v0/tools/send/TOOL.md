---
name: send
track: bonus
kind: action
provider: Telegram Bot API
requires_env: [TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]
inputs: [text, confirmed]
outputs: [status]
side_effect: true
requires_confirmation: true
---
# send

Posts text to a Telegram channel. The message is only sent when `confirmed` is true.

`confirmed` phải là boolean; chuỗi `"true"`/`"false"`, số và null trả error dict
trước khi gọi HTTP. Khi đã xác nhận, `text` phải là chuỗi không rỗng. Kiểm tra cả
HTTP status và Telegram `ok=true`; lỗi có URL gửi sẽ được che bot token.
`run_eval.py` giả lập action theo mặc định và ghi `dry_run`; đó không phải gửi thành công.
