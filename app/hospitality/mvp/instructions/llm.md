<!-- Prefab: llm-call v0.1.0 -->

# LLM Call Prefab — Agent Instructions

This prefab provides a **litellm-backed chat completion endpoint** at `POST /api/llm/chat`.

## Architecture

- **Backend**: `backend/app/llm/router.py` — FastAPI router with a single `/api/llm/chat` endpoint
- **Config**: `backend/app/config.py` — `LLM_MODEL` field (env var: `PREFAB_LLM_MODEL`)
- **Frontend**: `frontend/app/(authenticated)/sample-llm-call/page.tsx` — sample chat page

## Configuration

The LLM model is set via `PREFAB_LLM_MODEL` in `.env`. litellm supports 100+ providers:

| Provider | Model format | Example |
|----------|-------------|---------|
| AWS Bedrock | `bedrock/<model-id>` | `bedrock/anthropic.claude-3-5-haiku-20241022-v1:0` |
| OpenAI | `openai/<model>` | `openai/gpt-4o` |
| Anthropic | `anthropic/<model>` | `anthropic/claude-sonnet-4-20250514` |

AWS Bedrock requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN` in `.env`.

## API Contract

### `POST /api/llm/chat`

**Request:**
```json
{
  "messages": [
    { "role": "user", "content": "Hello" }
  ],
  "model": null,
  "max_tokens": 1000
}
```

- `model` — override `PREFAB_LLM_MODEL` for this request (optional)
- `messages` — array of `{ role, content }` following the OpenAI chat format
- `max_tokens` — max completion tokens (default 1000)

**Response:**
```json
{
  "content": "Hello! How can I help?",
  "model": "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  }
}
```

## Rules

- Always call `/api/llm/chat` from the frontend — never call litellm directly from client code.
- The `model` field in the request is optional — omit it to use the configured default.
- When adding new LLM features (summarization, extraction, etc.), create a new endpoint in `backend/app/llm/router.py` that calls `litellm.acompletion()`, or `complete_json()` when the feature needs JSON back, with the appropriate system prompt.
- **Structured output** — any feature that needs structured output (JSON) from the model MUST use `complete_json(...)` from `backend/app/llm/complete_json.py`. NEVER call `json.loads` on `message.content` (the raw reply) directly: the model commonly wraps the object in a ` ```json ` fence or adds prose around it, so a direct parse breaks.
- **Ask for an object, not a bare list** — `complete_json` returns only a JSON *object*. Prompt the model for an object; if a feature needs a list, wrap it as `{"items": [...]}`. A reply whose top level is an array raises `LlmJsonError`.
- **Raise `max_tokens` for large outputs** — the default is small; a large structured reply that gets truncated does not parse and raises, and the retry fails the same way. Pass a higher `max_tokens` when the expected JSON is big.
- **On failure, do not store placeholders** — `complete_json` raises `LlmJsonError` when the reply is empty or has no parseable JSON object. When it raises, follow the feature's use-case error or retry path; do NOT persist a placeholder value (such as a `0` score) as if scoring succeeded. Storing a placeholder "success" row suppresses the automatic retry the use case promises.
- Do NOT hardcode API keys — all credentials come from environment variables.
- **use `react-markdown`** (`ReactMarkdown` from `"react-markdown"`) when displaying AI/LLM response text. See `sample-llm-call/page.tsx` for the reference pattern.
