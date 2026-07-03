"""
ClaudeCodeAgent - A coding agent using Claude Agent SDK.

This agent provides a simplified interface to Claude Code for implementing
tasks and plans.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv
from google.adk.agents import Agent, InvocationContext
from google.adk.events import Event
from google.genai import types

from ai_research_engineer.agents.adk.utils import is_network_disabled
from ai_research_engineer.agents.claude_code.templates import (
    get_claude_context,
    get_claude_instructions,
    get_minimal_pyproject,
)


try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import McpHttpServerConfig
except ImportError:
    # Fallback if claude_agent_sdk is not available
    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    async def query(prompt, options):
        yield {"type": "error", "error": "claude_agent_sdk not installed"}


# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# Skills repository, pinned to a specific commit so runs are reproducible and
# the clone can be cached (S0-8). Bump SKILLS_REPO_SHA to update the skills.
SKILLS_REPO_URL = "https://github.com/K-Dense-AI/claude-scientific-skills.git"
SKILLS_REPO_SHA = "8b1c0e6a0c0b4f3a2d5e6f7a8b9c0d1e2f3a4b5c"  # pinned commit; update to bump skills


def _skills_cache_dir() -> Path:
    """Shared on-disk cache for the pinned skills checkout."""
    return Path.home() / ".archimedes" / "cache" / "skills" / SKILLS_REPO_SHA


def _ensure_skills_cache() -> Optional[Path]:
    """Clone the pinned skills repo into the shared cache ONCE; reuse thereafter.

    Returns the populated cache directory, or ``None`` if the clone failed and no
    cache is available. Subsequent calls short-circuit on the completion marker so
    the repo is cloned at most once per pinned SHA.
    """
    import subprocess

    cache_dir = _skills_cache_dir()
    marker = cache_dir / ".complete"
    if marker.exists():
        return cache_dir  # already cached — do NOT clone again

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Shallow-fetch exactly the pinned commit, then check it out.
        subprocess.run(["git", "init"], cwd=str(cache_dir), check=True, capture_output=True, timeout=60)
        subprocess.run(
            ["git", "remote", "add", "origin", SKILLS_REPO_URL],
            cwd=str(cache_dir),
            check=True,
            capture_output=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", SKILLS_REPO_SHA],
            cwd=str(cache_dir),
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "checkout", "FETCH_HEAD"], cwd=str(cache_dir), check=True, capture_output=True, timeout=60
        )
        marker.write_text("ok")
        logger.info("[Claude Code] Cached skills repo at pinned SHA in %s", cache_dir)
        return cache_dir
    except Exception as e:
        logger.warning("[Claude Code] Failed to populate skills cache: %s", e)
        return None


def setup_skills_directory(working_dir: str) -> None:
    """
    Populate ``.claude/skills/`` from the pinned skills repo (S0-8).

    The repo is cloned once into a shared cache (``~/.archimedes/cache/skills/
    <sha>/``); every run copies from that cache instead of re-cloning.

    Parameters
    ----------
    working_dir : str
        Working directory to set up skills in
    """
    import shutil

    working_path = Path(working_dir)
    skills_dir = working_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = _ensure_skills_cache()
    if cache_dir is None:
        logger.warning("[Claude Code] Skills cache unavailable — skipping skills setup.")
        return

    source_path = cache_dir / "scientific-skills"
    if not source_path.exists():
        logger.warning("[Claude Code] scientific-skills directory not found in cache %s", source_path)
        return

    for skill_dir in source_path.iterdir():
        if skill_dir.is_dir():
            dest_path = skills_dir / skill_dir.name
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(skill_dir, dest_path)
    logger.info("[Claude Code] Skills copied from cache to %s", skills_dir)


def _git_push_config() -> tuple[str, bool]:
    """Remote-push configuration (S0-8). Push happens ONLY if a remote URL is set
    AND push is explicitly enabled. Read from env so nothing is hardcoded."""
    remote_url = os.getenv("GIT_REMOTE_URL", "").strip()
    push = os.getenv("GIT_PUSH", "").strip().lower() in ("1", "true", "yes")
    return remote_url, push


def _setup_git_repo(working_dir: str) -> None:
    """Initialize a local git repo with a baseline commit (S0-8).

    Always: ``git init`` + local identity + initial commit. Never creates a
    hardcoded remote. A remote push happens ONLY when ``git.remote_url`` is set
    AND ``git.push=true`` (env: GIT_REMOTE_URL / GIT_PUSH). Auth is supplied via
    env at push time through a one-shot ``http.extraHeader`` and is NEVER written
    into ``.git/config``.
    """
    import subprocess

    working_path = Path(working_dir)
    if (working_path / ".git").exists():
        return

    try:
        subprocess.run(["git", "init"], cwd=working_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "AI Research Agent"], cwd=working_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "ai-research-engineer@localhost"],
            cwd=working_dir,
            check=True,
            capture_output=True,
        )
        (working_path / ".gitignore").write_text(
            ".claude/\n__pycache__/\n*.pyc\n.env\n*.pt\n*.pth\n*.safetensors\ndata/\n"
        )
        subprocess.run(["git", "add", ".gitignore"], cwd=working_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from Orchestrator"],
            cwd=working_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "branch", "-M", "main"], cwd=working_dir, check=True, capture_output=True)
        logger.info("[Claude Code] Initialized local git repository with baseline commit in %s", working_dir)

        remote_url, do_push = _git_push_config()
        if remote_url and do_push:
            token = os.getenv("GIT_PUSH_TOKEN", "").strip()
            push_cmd = ["git"]
            if token:
                # One-shot auth header for THIS command only — not persisted to .git/config.
                push_cmd += ["-c", f"http.extraHeader=Authorization: Bearer {token}"]
            push_cmd += ["push", remote_url, "HEAD:main"]
            subprocess.run(push_cmd, cwd=working_dir, check=True, capture_output=True)
            logger.info("[Claude Code] Pushed initial commit to the configured remote.")
        else:
            logger.info("[Claude Code] No remote push configured (GIT_REMOTE_URL/GIT_PUSH) — local commit only.")
    except Exception as e:
        logger.warning("[Claude Code] Local git setup failed (non-fatal): %s", e)


def setup_working_directory(working_dir: str) -> None:
    """
    Set up the working directory with required files and structure.
    Parameters
    ----------
    working_dir : str
        The working directory path to set up.
    """
    working_path = Path(working_dir)
    working_path.mkdir(parents=True, exist_ok=True)

    # Initialize a local git repository with a baseline commit (S0-8). No remote
    # is created and no push happens unless explicitly configured.
    _setup_git_repo(working_dir)

    # We added 'knowledge_base' and 'literature' to the standard subdirectories
    subdirs = ["user_data", "workflow", "results", "literature", "knowledge_base"]

    for subdir in subdirs:
        (working_path / subdir).mkdir(exist_ok=True)

    # Set up skills directory
    setup_skills_directory(working_dir)

    # Create pyproject.toml if it doesn't exist
    pyproject_path = working_path / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_path.write_text(get_minimal_pyproject())
        logger.info(f"[Claude Code] Created pyproject.toml in {working_dir}")

    # Initialize the Knowledge Base Vault
    kb_path = working_path / "knowledge_base"
    
    # 1. Literature Review Synthesis
    lit_review = kb_path / "01_literature_review.md"
    if not lit_review.exists():
        lit_review.write_text("# Literature Review & Context\n\n*Agents: Document summaries of read papers, gaps in the current research, and why our approach is novel here.*")
        
    # 2. Methodology & Equations
    methodology = kb_path / "02_methodology_specs.md"
    if not methodology.exists():
        methodology.write_text("# Methodology & Architecture Specs\n\n*Agents: Document exact mathematical formulations, network architectures, hyperparameters, and dataset requirements here so the Coding Agent can implement them precisely.*")

    # Create initial Workspace README.md
    readme_path = working_path / "README.md"
    if not readme_path.exists():
        readme_content = f"""# AI Research Engineer Session

            Working Directory: `{working_dir}`

            ## Directory Structure

            - `literature/` - Raw downloaded PDFs from arXiv
            - `knowledge_base/` - Synthesized research notes, equations, and methodology specs (The "Brain")
            - `user_data/` - Input datasets or user files
            - `workflow/` - Implementation scripts, neural networks, and notebooks
            - `results/` - Final analysis outputs, model weights, and plots

            ## Implementation Progress

            _This file will be updated as the implementation progresses._
            """
        readme_path.write_text(readme_content)
        logger.info(f"[Claude Code] Created README.md and Knowledge Base in {working_dir}")


class ClaudeCodeAgent(Agent):
    """
    Agent that uses Claude Agent SDK for coding tasks.

    This agent:
    - Uses Claude Agent SDK which handles tools internally
    - Provides instructions via system prompt
    - Wraps responses as ADK Events for streaming
    - Uses Claude Code preset for coding-focused behavior
    """

    # Add model config to allow extra attributes
    model_config = {"extra": "allow"}

    # Define working_dir and output_key as instance variables
    _working_dir: Optional[str] = None
    _output_key: str = "implementation_summary"
    _task_prompt: str = ""

    def __init__(
        self,
        name: str = "claude_coding_agent",
        description: Optional[str] = None,
        working_dir: Optional[str] = None,
        output_key: str = "implementation_summary",
        task_prompt: str = "",
        after_agent_callback: Optional[Any] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Claude Code agent.

        Parameters
        ----------
        name : str
            Agent name used in ADK event stream.
        description : str, optional
            Human-readable description for the agent.
        working_dir : str, optional
            Working directory for the agent
        output_key : str
            State key where the final implementation summary will be stored.
        after_agent_callback : callable, optional
            Callback function to be invoked after the agent completes execution.
            Useful for event compression or post-processing.

        Notes
        -----
        Claude Agent SDK has a 1MB JSON buffer limit for tool responses. When reading
        large files (>1MB), the agent will fail with a JSON buffer overflow error.
        Instructions are provided to Claude to avoid reading large files directly.
        """
        # Get model from environment variable
        model = os.getenv("CODING_MODEL", "claude-sonnet-4-5-20250929")
        # Pass model to parent Agent class (it has a model field)
        super().__init__(
            name=name,
            description=description or "A coding agent that uses Claude Agent SDK to implement plans",
            model=model,
            after_agent_callback=after_agent_callback,
            **kwargs,
        )
        self._working_dir = working_dir
        self._output_key = output_key
        self._task_prompt = task_prompt

    @property
    def working_dir(self) -> Optional[str]:
        return self._working_dir

    @property
    def output_key(self) -> str:
        return self._output_key

    def _truncate_summary(self, summary: str) -> str:
        """
        Truncate implementation summary to prevent token overflow.

        Parameters
        ----------
        summary : str
            The full implementation summary.

        Returns
        -------
        str
            Truncated summary.
        """
        MAX_CHARS = 40000  # ~10k tokens

        if not summary or len(summary) <= MAX_CHARS:
            return summary

        # Keep start and end
        keep_start = MAX_CHARS * 3 // 4
        keep_end = MAX_CHARS // 4
        truncated = (
            summary[:keep_start]
            + "\n\n[... middle section truncated to fit token limits ...]\n\n"
            + summary[-keep_end:]
        )
        logger.info(
            f"[Claude Code] [{self.name}] Truncated implementation_summary from {len(summary)} to {len(truncated)} chars"
        )
        return truncated

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Execute Claude Agent with the implementation plan."""
        try:
            # Get working directory
            working_dir = self._working_dir
            if not working_dir:
                import tempfile

                working_dir = tempfile.mkdtemp(prefix="claude_session_")

            # Get state
            state = ctx.session.state
            current_stage = state.get("current_stage")

            # Format stage information for the prompt
            if current_stage:
                stage_info = (
                    f"Stage {current_stage.get('index', 0) + 1}: {current_stage.get('title', 'Unknown')}\n\n"
                    f"{current_stage.get('description', '')}"
                )
            else:
                stage_info = ""

            # Set up working directory
            setup_working_directory(working_dir)

            # Install graphify MCP hooks so Claude Code picks them up (fail-soft)
            if state.get("use_graphify"):
                try:
                    import subprocess as _sp

                    from ai_research_engineer.core.graphify import graphify_available

                    if graphify_available():
                        _sp.run(
                            ["python", "-m", "graphify", "claude", "install"],
                            cwd=working_dir,
                            capture_output=True,
                            timeout=30,
                        )
                        logger.info("[Claude Code] graphify claude install done in %s", working_dir)
                except Exception as _ge:
                    logger.warning("[Claude Code] graphify claude install failed: %s", _ge)

            # Yield starting event
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text="Preparing Claude Agent (coding mode)...")]
                ),
            )

            # Generate the prompt with full context (but NOT success criteria - don't show the "answers")
            if stage_info:
                prompt = get_claude_context(
                    implementation_plan=stage_info,
                    working_dir=working_dir,
                    original_request=state.get("original_user_input", ""),
                    completed_stages=state.get("stage_implementations", []),
                    all_stages=state.get("high_level_stages", []),
                )
            elif self._task_prompt:
                # Agent-level task prompt (e.g. paper_writer_agent uses summary.md)
                # Substitute any $variables from state
                from string import Template  # noqa: PLC0415
                tmpl = Template(self._task_prompt)
                subs = {"working_dir": working_dir}
                for k, v in state.items():
                    subs[k] = str(v) if v is not None else ""
                prompt = tmpl.safe_substitute(**subs)
            else:
                # Fallback: Try multiple state keys to find the task
                task_prompt = (
                    state.get("implementation_task", "")
                    or state.get("original_user_input", "")
                    or state.get("latest_user_input", "")
                    or state.get("user_message", "")
                )

                # Also check if there's a message in the context's initial message
                if not task_prompt and hasattr(ctx, 'initial_message'):
                    initial_msg = ctx.initial_message
                    if initial_msg and hasattr(initial_msg, 'parts'):
                        for part in initial_msg.parts:
                            if hasattr(part, 'text'):
                                task_prompt = part.text
                                break

                if not task_prompt:
                    error_msg = "No implementation task or plan found in state."
                    logger.warning(
                        f"[Claude Code] [{self.name}] {error_msg}. Available state keys: {list(state.keys())}"
                    )
                    yield Event(
                        author=self.name,
                        content=types.Content(role="model", parts=[types.Part.from_text(text=f"Error: {error_msg}")]),
                    )
                    return

                prompt = f"""Create and execute a comprehensive implementation plan.

                    User Request: {task_prompt}

                    Working directory: {working_dir}

                    Requirements:
                    1. Analyze the request and create a structured plan
                    2. Execute the plan step by step
                    3. Save all outputs with descriptive filenames
                    4. Generate comprehensive documentation
                    5. Create final execution summary when done"""

            # Generate system instructions
            system_instructions = get_claude_instructions(state=state, working_dir=working_dir)

            env = os.environ.copy()
            env["ANTHROPIC_MODEL"] = self.model
            
            # Phase 3: Global Environment Lock & HF Integration
            env["UV_PROJECT_ENVIRONMENT"] = "/home/ec2-user/ai-research-engineer/.venv"
            env["HF_TOKEN"] = os.getenv("HF_TOKEN", "")

            # Create options for Claude Agent SDK
            # Skills are loaded from .claude/skills/ via setting_sources
            # MCP servers are loaded from .claude/settings.json via setting_sources
            options = ClaudeAgentOptions(
                cwd=working_dir,
                permission_mode="bypassPermissions",
                model=self.model,
                env=env,
                system_prompt={"type": "preset", "preset": "claude_code", "append": system_instructions},
                setting_sources=["project", "user", "local"],
                disallowed_tools=["WebFetch", "WebSearch"] if is_network_disabled() else None,
                mcp_servers={
                    "context7": McpHttpServerConfig(
                        type="http",
                        url="https://mcp.context7.com/mcp",
                    )
                },
            )

            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=f"Starting Claude Agent (coding mode) with model: {self.model}")],
                ),
            )

            # Execute with Claude Code SDK - stream messages in real-time
            output_lines = []
            received_final_result = False  # After ResultMessage, keep draining to let SDK close cleanly

            # Track tool calls to match with their results
            # Claude uses tool_use_id to link ToolUseBlock with ToolResultBlock
            tool_id_to_name = {}

            # CRITICAL MAPPING: Claude Agent SDK → Google GenAI → ADK Events
            #
            # Claude Message Types:
            #   - AssistantMessage: Contains content blocks from Claude (TextBlock, ThinkingBlock, ToolUseBlock)
            #   - UserMessage: User input including ToolResultBlock (tool execution results)
            #   - SystemMessage: System messages
            #   - ResultMessage: Final completion indicator (subtype: 'success' or 'error')
            #
            # Claude Content Block Types → Google GenAI Part Types → ADK Event Types:
            #   AssistantMessage blocks:
            #     - TextBlock              → Part.from_text(text=...)                        → MessageEvent
            #     - ThinkingBlock          → Part(text=..., thought=True)                    → MessageEvent (is_thought=True)
            #     - ToolUseBlock           → Part.from_function_call(name=..., args=...)     → FunctionCallEvent
            #   UserMessage blocks:
            #     - ToolResultBlock        → Part.from_function_response(name=..., response=...) → FunctionResponseEvent
            #     - TextBlock              → Part.from_text(text=...)                        → MessageEvent
            #
            # This mapping ensures proper event parsing and emission.

            # Stream messages as they arrive for real-time processing
            try:
                async for message in query(prompt=prompt, options=options):
                    # If we've already seen the final ResultMessage, ignore any subsequent messages
                    # and continue draining so the SDK can shut down its internal task group cleanly.
                    if received_final_result:
                        continue
                    if message is None:
                        continue

                    # Get the type name dynamically to avoid import issues
                    message_type = type(message).__name__

                    if message_type == "AssistantMessage":
                        # Assistant message contains content blocks - convert to Google GenAI Parts
                        # Each AssistantMessage becomes one Event with multiple Parts
                        content_blocks = getattr(message, 'content', [])

                        # Collect all parts for a single Event
                        google_parts = []

                        for block in content_blocks:
                            block_type = type(block).__name__

                            if block_type == "TextBlock":
                                # Regular text output from Claude
                                # Map to: Part.from_text(text=...)
                                text = getattr(block, 'text', '')
                                if text:
                                    output_lines.append(text)
                                    google_parts.append(types.Part.from_text(text=text))
                                    logger.info(f"[Claude Code] [TextBlock] {len(text)} chars")

                            elif block_type == "ThinkingBlock":
                                # Extended thinking (if enabled)
                                # Map to: Part(text=..., thought=True)
                                thinking = getattr(block, 'thinking', '')
                                if thinking:
                                    logger.info(
                                        f"[Claude Code] [ThinkingBlock] {len(thinking)} chars: {thinking[:100]}..."
                                    )
                                    # Create Part with thought flag set to True
                                    # This will be parsed as MessageEvent with is_thought=True
                                    google_parts.append(types.Part(text=thinking, thought=True))

                            elif block_type == "ToolUseBlock":
                                # Claude is requesting to use a tool
                                # Map to: Part.from_function_call(name=..., args=...)
                                tool_id = getattr(block, 'id', '')
                                tool_name = getattr(block, 'name', 'unknown')
                                tool_input = getattr(block, 'input', {})

                                logger.info(
                                    f"[Claude Code] [ToolUseBlock] {tool_name} (id: {tool_id}) with args: {list(tool_input.keys())}"
                                )

                                # Store mapping from tool_use_id to tool_name for later matching
                                if tool_id:
                                    tool_id_to_name[tool_id] = tool_name

                                # Convert to Google GenAI function call format
                                # This will be parsed as FunctionCallEvent downstream
                                google_parts.append(types.Part.from_function_call(name=tool_name, args=tool_input))

                            else:
                                # Unknown content block type in AssistantMessage
                                logger.info(
                                    f"[Claude Code] [AssistantMessage] Unknown ContentBlock type: {block_type} - {block}"
                                )
                                google_parts.append(types.Part.from_text(text=f"[Unknown block: {block_type}]"))

                        # Yield a single Event with all converted Parts from this AssistantMessage
                        if google_parts:
                            yield Event(author=self.name, content=types.Content(role="model", parts=google_parts))

                    elif message_type == "UserMessage":
                        # User message - contains ToolResultBlock (tool execution results) and possibly TextBlock
                        # In Claude Agent SDK, tool results come back as UserMessage with ToolResultBlock
                        content_blocks = getattr(message, 'content', [])
                        logger.info(f"[Claude Code] Received UserMessage with {len(content_blocks)} content blocks")

                        # Parse content blocks and convert to Google GenAI Parts
                        google_parts = []

                        for block in content_blocks:
                            block_type = type(block).__name__

                            if block_type == "ToolResultBlock":
                                # Result from a tool execution (comes from user/system after executing tool)
                                # Map to: Part.from_function_response(name=..., response=...)
                                tool_use_id = getattr(block, 'tool_use_id', '')
                                is_error = getattr(block, 'is_error', False)
                                content = getattr(block, 'content', '')

                                # Retrieve the tool name from our tracking dict
                                tool_name = tool_id_to_name.get(tool_use_id, f"tool_{tool_use_id}")

                                # Convert Claude's content format to Google's response format
                                # Claude returns content as list of content items, Google expects dict
                                response_data = {}

                                if isinstance(content, list):
                                    # Extract text from content blocks
                                    text_parts = []
                                    for content_item in content:
                                        if isinstance(content_item, dict):
                                            if content_item.get('type') == 'text':
                                                text_parts.append(content_item.get('text', ''))
                                        elif hasattr(content_item, 'text'):
                                            text_parts.append(getattr(content_item, 'text', ''))

                                    combined_text = '\n'.join(text_parts) if text_parts else ''
                                    if is_error:
                                        response_data = {'error': combined_text}
                                        logger.info(
                                            f"[Claude Code] [ToolResultBlock] ERROR for {tool_name}: {combined_text[:200]}..."
                                        )
                                    else:
                                        response_data = {'output': combined_text}
                                        logger.info(
                                            f"[Claude Code] [ToolResultBlock] SUCCESS for {tool_name}: {combined_text[:200]}..."
                                        )
                                elif isinstance(content, str):
                                    if is_error:
                                        response_data = {'error': content}
                                    else:
                                        response_data = {'output': content}
                                    logger.info(f"[Claude Code] [ToolResultBlock] {tool_name}: {content[:200]}...")
                                else:
                                    # Fallback for other content types
                                    content_str = str(content)
                                    if is_error:
                                        response_data = {'error': content_str}
                                    else:
                                        response_data = {'output': content_str}
                                    logger.info(
                                        f"[Claude Code] [ToolResultBlock] {tool_name} (converted to str): {content_str[:200]}..."
                                    )

                                # Convert to Google GenAI function response format
                                # This will be parsed as FunctionResponseEvent downstream
                                google_parts.append(
                                    types.Part.from_function_response(name=tool_name, response=response_data)
                                )

                            elif block_type == "TextBlock":
                                # User can also send text input
                                text = getattr(block, 'text', '')
                                if text:
                                    logger.info(f"[Claude Code] [UserMessage.TextBlock] {len(text)} chars")
                                    google_parts.append(types.Part.from_text(text=text))

                            else:
                                # Unknown content block type in UserMessage
                                logger.info(
                                    f"[Claude Code] [UserMessage] Unknown ContentBlock type: {block_type} - {block}"
                                )
                                google_parts.append(types.Part.from_text(text=f"[Unknown user block: {block_type}]"))

                        # Yield Event with all converted Parts from this UserMessage
                        # Use role="model" since this is from the user/system executing tools
                        # COMMENTED OUT: Prevents long tool responses from polluting ADK context
                        # Tool responses are still logged above for debugging
                        # if google_parts:
                        #     yield Event(author=self.name, content=types.Content(role="model", parts=google_parts))

                    elif message_type == "SystemMessage":
                        # System message
                        logger.info(f"[Claude Code] Received SystemMessage: {message}")

                    elif message_type == "ResultMessage":
                        # Final result from Claude - indicates task completion
                        subtype = getattr(message, 'subtype', None)

                        if subtype == 'success':
                            result_text = "\n=== Task Completed Successfully ==="
                            output_lines.append(result_text)

                            # Create summary from all output and truncate to prevent downstream token overflow
                            summary = "\n".join(output_lines)
                            state[self._output_key] = self._truncate_summary(summary)

                            yield Event(
                                author=self.name,
                                content=types.Content(role="model", parts=[types.Part.from_text(text=result_text)]),
                            )
                        elif subtype == 'error':
                            error_text = "\n=== Task Failed ==="
                            error_details = getattr(message, 'error', '')
                            if error_details:
                                error_text += f"\nError: {error_details}"

                            output_lines.append(error_text)
                            state[self._output_key] = self._truncate_summary(error_text)

                            yield Event(
                                author=self.name,
                                content=types.Content(role="model", parts=[types.Part.from_text(text=error_text)]),
                            )

                        # Mark that we've received the final result but DO NOT break the loop.
                        # Draining the generator avoids injecting GeneratorExit into the SDK
                        # which triggers anyio cancel-scope cross-task errors.
                        received_final_result = True

                    else:
                        # Unknown message type - log it with full details
                        logger.info(f"[Claude Code] [Unknown Message type: {message_type}] - Message: {message}")

                # If no result message, create summary from output
                if self._output_key not in state:
                    summary = "\n".join(output_lines[-20:]) if output_lines else "Task completed (no output captured)"
                    state[self._output_key] = self._truncate_summary(summary)

            except asyncio.CancelledError:
                # If the query was cancelled, just propagate the cancellation
                logger.info(f"[Claude Code] [{self.name}] Agent cancelled during Claude query execution")
                raise
            except Exception as e:
                # Specific handling for JSON buffer overflow errors
                error_msg = str(e)
                if "JSON message exceeded maximum buffer" in error_msg:
                    logger.error(
                        f"[Claude Code] [{self.name}] Claude SDK buffer overflow - likely tried to read file >1MB. "
                        "Claude Agent SDK has a 1MB limit on tool response sizes."
                    )
                    summary = (
                        "Error: File too large for Claude SDK buffer (>1MB limit).\n\n"
                        "Claude attempted to read a large file which exceeded the internal 1MB buffer limit "
                        "of the Claude Agent SDK subprocess communication channel.\n\n"
                        "To fix this issue:\n"
                        "1. Use command-line tools (head, tail, wc, ls -lh) to inspect file sizes and contents\n"
                        "2. For large CSV/data files, use pandas with nrows parameter to load only portions\n"
                        "3. Process large files in chunks rather than loading entirely\n"
                        "4. Use streaming or iterative processing for files over 1MB\n\n"
                        f"Full error: {error_msg[:500]}"
                    )
                    state[self._output_key] = self._truncate_summary(summary)
                    yield Event(
                        author=self.name,
                        content=types.Content(role="model", parts=[types.Part.from_text(text=summary)]),
                    )
                else:
                    # Re-raise other exceptions for generic handling
                    raise

        except Exception as e:
            # Generic exception handler for all other errors
            logger.error(f"[Claude Code] [{self.name}] Error in Claude Agent: {e}", exc_info=True)
            state[self._output_key] = self._truncate_summary(f"Error: {str(e)}")
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part.from_text(text=f"Error: {str(e)}")]),
            )
