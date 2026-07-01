# API Reference

Complete API reference for the AI Research Engineer.

## Core API

### `AIEngineer` (Core Engine)

Main class for interacting with the AI Research Engineer multi-agent workflow.

```python
from ai_research_engineer import AIEngineer

ds = AIEngineer(
    agent_type="adk",           # "adk" (recommended) or "claude_code" (direct mode)
    mcp_servers=None,           # Optional: list of MCP servers
)
```

#### Parameters

- **agent_type** (str, default="adk"): Type of agent to use
  - `"adk"`: (Recommended) Full multi-agent research workflow with ideation, planning, validation, and manuscript synthesis.
  - `"claude_code"`: Direct mode - bypasses workflow for simple scripting tasks.
- **mcp_servers** (list, optional): List of MCP servers to enable.

#### Model Configuration

Models are configured via environment variables and routed through OpenRouter:

- ADK agents: `DEFAULT_MODEL` (default: `google/gemini-2.5-pro`)
- Coding agent: `CODING_MODEL` (default: `claude-sonnet-4-5-20250929`)
- Review agents: `REVIEW_MODEL` (default: same as DEFAULT_MODEL)

#### Attributes

- **session_id** (str): Unique session identifier
- **working_dir** (Path): Temporary working directory (The "Research Vault") for the session
- **config** (SessionConfig): Session configuration

#### Methods

##### `run(message, files=None, **kwargs) -> Result`

Synchronous method to run a research query through the workflow.

**Parameters:**
- `message` (str): The user's research topic or hypothesis.
- `files` (list[tuple], optional): List of (filename, content) tuples.

**Returns:**
- Result object with response (final manuscript), files_created, duration, etc.

##### `run_async(message, files=None, stream=False, context=None) -> Union[Result, AsyncGenerator]`

Asynchronous method to run a query. If `stream=True`, returns an async generator for streaming events (live logs).

## Event System

When using streaming mode (`stream=True`), the workflow emits events as it progresses.

### Workflow Event Flow

For the ADK multi-agent workflow, you'll see events in exactly this order:

```
Ideation Phase:
  idea_generator_agent → novelty_scorer_agent → ideation_review_confirmation_agent

Planning Phase:
  plan_maker_agent → plan_reviewer_agent → plan_review_confirmation_agent →
  high_level_plan_parser

Execution Phase (repeated for each stage):
  stage_orchestrator → coding_agent → review_agent →
  implementation_review_confirmation_agent → success_criteria_checker →
  stage_reflector

Synthesis Phase:
  summary_agent (Academic Paper Writer)
```

### Event Types

- **MessageEvent**: Regular text output from agents.
- **FunctionCallEvent**: Agent is using a tool (e.g., `semantic_search_papers`).
- **FunctionResponseEvent**: Tool returned a result (e.g., ArXiv JSON data).
- **UsageEvent**: Token usage information.
- **ErrorEvent**: An error occurred during execution.
- **CompletedEvent**: Workflow finished successfully, yielding the final manuscript.

## Server API

The FastAPI server exposes REST endpoints for running and monitoring sessions.

### Authentication

`POST /api/sessions` and `POST /api/submissions` are protected by an API token when
the `ARCHIMEDES_API_TOKEN` environment variable is set.  Pass the token in the
`X-API-Token` header:

```
POST /api/sessions
X-API-Token: your-secret-token-here
Content-Type: application/json
```

If `ARCHIMEDES_API_TOKEN` is not set, a warning is logged on startup and the
endpoints are unauthenticated (suitable for local development only).

### Rate Limiting

`POST /api/sessions` is rate-limited to 5 requests per IP per 60 seconds.
A `429 Too Many Requests` response is returned when the limit is exceeded.
Note: the limit is in-process; deploy behind a shared store (e.g. Redis) for
multi-worker setups.

### CORS

Allowed origins are read from the `ALLOWED_ORIGINS` environment variable
(comma-separated).  The default is `http://localhost:3000,http://localhost:8000`.

### Endpoints

| Method | Path | Auth required | Description |
|--------|------|---------------|-------------|
| GET | `/api/health` | No | Health check |
| POST | `/api/sessions` | Yes (if token set) | Start a new research run |
| GET | `/api/sessions` | No | List all sessions |
| GET | `/api/sessions/{id}` | No | Get a specific session |
| GET | `/api/sessions/{id}/stream` | No | SSE stream of live events |
| POST | `/api/submissions` | Yes (if token set) | Submit a research interest form |