# stream-json reference (Claude Code 2.1.x)

| event | meaning |
|---|---|
| `system` / `init` | session start: `tools`, `model`, `permissionMode`, `agents` |
| `system` / `task_summary`, `post_turn_summary` | short status notes from Claude Code, not model output |
| `assistant` | one model message; `content` holds `text`, `thinking`, `tool_use` blocks |
| `user` | sent back to the model; holds `tool_result` blocks |
| `parent_tool_use_id` set | the event belongs to a subagent started by that tool_use |
| `rate_limit_event` | account rate-limit status (no model content) |
| `result` | end of run: `num_turns`, `result`, `usage`, `is_error` |

Token fields in `usage`: `input_tokens` (new, uncached), `cache_read_input_tokens`
(re-used prompt prefix, cheap), `cache_creation_input_tokens` (written to cache),
`output_tokens` (generated, includes thinking).
