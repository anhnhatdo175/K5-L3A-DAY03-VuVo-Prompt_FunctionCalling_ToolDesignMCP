# Tool Setup Guide

Use this guide before class. All keys go into `starter_v0/.env`. Never commit `.env`.

Pricing and quotas can change. The classroom target below is current for this lab setup as of 2026-06-02; re-check the provider page before a new cohort.

Smoke tests below call tools through the registry (`TOOL_FUNCTIONS`) so they only
verify that your API key works — they are not routing hints. Run them from `starter_v0/`.

## 1. Model Provider

Recommended provider:

```bash
OPENROUTER_API_KEY=...
```

Alternatives:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
```

Preflight:

```bash
cd starter_v0
python scripts/preflight_provider.py --provider openrouter
```

Local model (bonus Small Local Model Challenge, không cần API key):

```bash
# Cài Ollama: https://ollama.com/download
ollama pull qwen3.5:4b-q4_K_M
python scripts/preflight_provider.py --provider ollama --model qwen3.5:4b-q4_K_M
```

Tuỳ chọn trong `.env`: `OLLAMA_BASE_URL` (mặc định `http://localhost:11434/v1`), `OLLAMA_MODEL` (mặc định `qwen3.5:4b-q4_K_M`).

Trên Windows dùng Python 3.12 và cài đủ `starter_v0/requirements.txt` vào đúng
môi trường chạy. SDK `openai` cần cho cả Ollama. UI dùng `streamlit` đã được khai
báo trong requirements. `DEFAULT_PROVIDER=demo (offline)` mở demo local không
gọi model/API; để đo provider thật, chọn provider tương ứng và tắt fallback.
Không tính transcript có `fallback_to_demo` là bằng chứng model live thành công.

### Local profile and reproducibility

The current local profile uses `qwen3.5:4b-q4_K_M`, native tool calls and
`OLLAMA_REASONING_EFFORT=none`. Defaults are also listed in `.env.example`.
`OLLAMA_PROTOCOL_RETRIES=1` allows at most one retry when a required response
contains no tool calls, or an auto response is entirely empty. With
`OLLAMA_PROTOCOL_RETRY_FORMAT=structured_plan`, that retry uses a JSON schema
containing **all enabled tools**. The model chooses every tool and argument;
invalid or wrong nonempty native calls are not repaired. Every attempt and usage
is retained in run/transcript metadata. A direct answer remains valid in auto mode.
Set `OLLAMA_PROTOCOL_RETRIES=0` for native-only model comparisons; set
`OLLAMA_CALL_MODE=structured_plan` only when explicitly comparing that protocol.
These configurations have different call budgets, so label them separately.

Measured local runtime: Ollama 0.40.16, context 8192, one parallel request,
flash attention enabled and q8_0 KV cache. To reproduce these server settings in
PowerShell (stop an existing server before starting another):

```powershell
$env:OLLAMA_CONTEXT_LENGTH='8192'
$env:OLLAMA_NUM_PARALLEL='1'
$env:OLLAMA_MAX_LOADED_MODELS='1'
$env:OLLAMA_FLASH_ATTENTION='1'
$env:OLLAMA_KV_CACHE_TYPE='q8_0'
ollama serve
```

In another terminal, from `starter_v0`, using Python 3.12:

```powershell
.\.venv312\Scripts\python.exe scripts/preflight_provider.py --provider ollama
.\.venv312\Scripts\python.exe run_eval.py --provider ollama --version v12-local --suite base --eval-cases data/eval_base.json
.\.venv312\Scripts\python.exe run_eval.py --provider ollama --version v12-local --suite group --eval-cases data/eval_group.json
.\.venv312\Scripts\python.exe run_eval.py --provider ollama --version v12-local --suite cross --eval-cases data/eval_regression.json
.\.venv312\Scripts\python.exe -m streamlit run app.py
```

Eval keeps sending actions in dry-run mode unless `--allow-actions` is explicitly
supplied. Routing/argument accuracy does not prove successful research API calls:
Tavily, Firecrawl and RapidAPI still require their own keys. The independent
regression dataset does not replace the fixed base/group suites. Original v3
prompt and tool snapshots are preserved as `artifacts/system_prompt_v3.md` and
`artifacts/tools_v3.yaml` for unchanged baseline comparisons.

## 2. Tavily — `lookup`

- Docs/credits: https://docs.tavily.com/documentation/api-credits
- API key page: https://app.tavily.com
- Classroom target: free plan with 1,000 API credits/month.

Setup:

1. Sign in at https://app.tavily.com.
2. Create or copy API key.
3. Add to `starter_v0/.env`:

```bash
TAVILY_API_KEY=tvly-...
```

Quick test:

```bash
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['lookup']('AI', max_results=1)['items'][0]['title'])"
```

## 3. Firecrawl — `fetch`

- Pricing: https://www.firecrawl.dev/pricing
- Docs: https://docs.firecrawl.dev
- Classroom target: free plan with 1,000 credits/month.

Setup:

1. Sign up at https://www.firecrawl.dev.
2. Create API key.
3. Add to `starter_v0/.env`:

```bash
FIRECRAWL_API_KEY=fc-...
```

Quick test:

```bash
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['fetch']('https://openai.com/research/')['items'][0]['title'])"
```

## 4. RapidAPI Twitter API45 — `timeline`, `social_search`

- API page: https://rapidapi.com/alexanderxbx/api/twitter-api45
- Classroom target: free plan with 1,000 requests/month.

Setup:

1. Sign in to RapidAPI.
2. Open https://rapidapi.com/alexanderxbx/api/twitter-api45.
3. Subscribe to the API plan.
4. Copy RapidAPI key.
5. Add to `starter_v0/.env`:

```bash
RAPIDAPI_KEY=...
RAPIDAPI_TWITTER_HOST=twitter-api45.p.rapidapi.com
```

Quick tests:

```bash
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['timeline']('sama', limit=1)['items'][0]['title'])"
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['social_search']('OpenAI', limit=1)['items'][0]['title'])"
```

## 5. arXiv Bonus — `papers`, `paper_text`

No API key is required. arXiv is rate-limited, so the tools wait between requests and retry lightly on HTTP 429.

Setup:

```bash
ARXIV_USER_AGENT=AI20k-Day03-Research-Agent/1.0 (your-team-name)
```

Quick tests:

```bash
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['papers']('AI agent evaluation', max_results=1)['items'][0]['title'])"
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['paper_text']('1706.03762', max_pages=1)['chars_returned'])"
```

Generated paper files go under `starter_v0/arxiv_papers/` and are ignored by git.

## 6. Telegram Bonus — `send`

Bonus action tool that posts text to a Telegram channel.

Official links:

- BotFather: https://t.me/BotFather
- Bot docs: https://core.telegram.org/bots

### Create Bot

1. Open Telegram.
2. Search for the official `@BotFather`.
3. Send:

```text
/newbot
```

4. Enter display name, for example:

```text
AI20k Research Bot
```

5. Enter username ending in `bot`, for example:

```text
ai20k_research_demo_bot
```

6. Copy the token BotFather returns.
7. Add to `starter_v0/.env`:

```bash
TELEGRAM_BOT_TOKEN=1234567890:AA....
```

Never paste this token into reports, screenshots, chat logs, or GitHub.

### Create Channel

1. Create a private Telegram channel.
2. Add your bot as admin.
3. Grant permission to post messages.

### Get Chat ID

For a public channel:

```bash
TELEGRAM_CHAT_ID=@your_channel_username
```

For a private channel:

1. Add bot as admin.
2. Post a fresh message in the channel.
3. Run:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

4. Find:

```json
"chat": {"id": -1001234567890}
```

5. Add to `.env`:

```bash
TELEGRAM_CHAT_ID=-1001234567890
```

Direct tool test (verifies the bot token/chat only):

```bash
python -c "from pathlib import Path; from env_loader import load_lab_env; load_lab_env(Path('.')); from tools import TOOL_FUNCTIONS as T; print(T['send']('AI20k test message', confirmed=True))"
```

## Final Checklist

Before class, at least one person per group should have:

- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `RAPIDAPI_KEY`
- optional `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- optional `ARXIV_USER_AGENT`
- `python scripts/preflight_provider.py --provider openrouter` passes
