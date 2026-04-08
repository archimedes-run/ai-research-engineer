# API Reference

Complete API reference for the AI Research Engineer.

## Core API

### `DataScientist` (Core Engine)

Main class for interacting with the AI Research Engineer multi-agent workflow.

```python
from ai_research_engineer import DataScientist

ds = DataScientist(
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