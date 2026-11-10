# Tool Folder Contract

Each tool lives in its own folder:

```text
tools/<tool_name>/
  TOOL.md   # frontmatter + human notes
  tool.py   # self-contained implementation
```

`tools/__init__.py` is the registry. `agent.py`, `chat.py`, and `run_eval.py`
import `TOOL_FUNCTIONS` from that registry.

`tool_runtime.py` validates required arguments, types, enums and unsupported
argument names before agent/chat dispatch. Keep defaults and required fields in
the declaration consistent with the implementation. Offline scripted sessions
can execute only local tools; eval actions default to dry-run.

## Frontmatter Fields

Every `TOOL.md` uses the same fields:

```yaml
---
name: tool_name
track: core | bonus
kind: live_api | local_formatter | local_knowledge | action | control
provider: Provider name if any
requires_env: [ENV_VAR]
inputs: [arg_name]
outputs: [field_name]
side_effect: false | true | local_file_write
requires_confirmation: true   # only for write/action tools
---
```

Core tools are enough to pass the base lab. Bonus tools are for teams that want
extra scope, extra eval cases, or a live delivery action.

