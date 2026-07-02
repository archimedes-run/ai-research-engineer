"""
Agent-graph construction smoke tests.

Calls the same factory paths the server uses (create_app / AIEngineer.__init__ +
_setup_agent) and asserts they construct without raising — no run(), no LLM call,
no network.

Why this catches the ClaudeCodeAgent bug
-----------------------------------------
`agents/adk/agent.py` used `ClaudeCodeAgent(...)` inside `create_agent` / `create_app`
without importing the class.  Calling `create_app(...)` triggers that code path and
would have raised `NameError: name 'ClaudeCodeAgent' is not defined` immediately,
with zero LLM interaction.

The same matrix tests `use_graphify=True` so the optional graphify wiring is also
exercised at construction time (it is fail-soft, so the graph import failure must
not abort construction either).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_working_dir(tmp_path, name: str):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


# ---------------------------------------------------------------------------
# create_app / create_agent — ADK factory
# ---------------------------------------------------------------------------

class TestADKAppConstruction:
    """create_app(...) must construct without raising for every param combination."""

    def test_create_app_novelty_aiml(self, tmp_path):
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_novel_aiml"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        assert app is not None

    def test_create_app_replication_aiml(self, tmp_path):
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_rep_aiml"),
            research_mode="replication",
            domain="aiml",
            use_graphify=False,
        )
        assert app is not None

    def test_create_app_novelty_algorithms(self, tmp_path):
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_novel_algo"),
            research_mode="novelty",
            domain="algorithms",
            use_graphify=False,
        )
        assert app is not None

    def test_create_app_evolve_mode(self, tmp_path):
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_evolve"),
            research_mode="evolve",
            domain="aiml",
            use_graphify=False,
        )
        assert app is not None

    def test_create_app_with_graphify_flag(self, tmp_path):
        """use_graphify=True must not crash construction (graphify import is fail-soft)."""
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_graphify"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=True,
        )
        assert app is not None

    def test_create_agent_returns_root_agent(self, tmp_path):
        from ai_research_engineer.agents.adk import create_agent
        agent = create_agent(
            working_dir=_make_working_dir(tmp_path, "adk_agent_direct"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        assert agent is not None

    def test_app_has_root_agent(self, tmp_path):
        from ai_research_engineer.agents.adk import create_app
        app = create_app(
            working_dir=_make_working_dir(tmp_path, "adk_root_check"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        assert hasattr(app, "root_agent")
        assert app.root_agent is not None


# ---------------------------------------------------------------------------
# ClaudeCodeAgent direct construction
# ---------------------------------------------------------------------------

class TestClaudeCodeAgentConstruction:
    """ClaudeCodeAgent must construct without raising."""

    def test_construct_default(self, tmp_path):
        from ai_research_engineer.agents.claude_code import ClaudeCodeAgent
        agent = ClaudeCodeAgent(
            working_dir=_make_working_dir(tmp_path, "cc_default"),
        )
        assert agent is not None

    def test_construct_named(self, tmp_path):
        from ai_research_engineer.agents.claude_code import ClaudeCodeAgent
        agent = ClaudeCodeAgent(
            name="test_cc_agent",
            description="Smoke test agent",
            working_dir=_make_working_dir(tmp_path, "cc_named"),
            output_key="test_output",
        )
        assert agent.name == "test_cc_agent"


# ---------------------------------------------------------------------------
# AIEngineer construction (mirrors what _run_agent does in the server)
# ---------------------------------------------------------------------------

class TestAIEngineerConstruction:
    """
    AIEngineer.__init__ for every agent_type must succeed.
    _setup_agent() exercises the full construction path including the
    ClaudeCodeAgent import inside agents/adk/agent.py — the exact site of the bug.
    """

    def test_adk_engineer_init(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="adk",
            working_dir=_make_working_dir(tmp_path, "eng_adk"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        assert eng is not None
        assert eng.config.agent_type == "adk"

    def test_claude_code_engineer_init(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="claude_code",
            working_dir=_make_working_dir(tmp_path, "eng_cc"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        assert eng is not None
        assert eng.config.agent_type == "claude_code"

    def test_evolve_engineer_init(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="evolve",
            working_dir=_make_working_dir(tmp_path, "eng_evolve"),
            research_mode="evolve",
            domain="aiml",
            use_graphify=False,
        )
        assert eng is not None

    def test_adk_engineer_with_graphify(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="adk",
            working_dir=_make_working_dir(tmp_path, "eng_adk_gph"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=True,
        )
        assert eng is not None

    @pytest.mark.asyncio
    async def test_adk_setup_agent_constructs(self, tmp_path):
        """
        _setup_agent() is the exact path _run_agent calls before any LLM work.
        This would have raised NameError: 'ClaudeCodeAgent' is not defined on the
        broken commit.  It must complete without error.
        """
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="adk",
            working_dir=_make_working_dir(tmp_path, "eng_setup_adk"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        await eng._setup_agent()
        assert eng.agent is not None
        assert eng.app is not None
        assert eng.runner is not None

    @pytest.mark.asyncio
    async def test_claude_code_setup_agent_constructs(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="claude_code",
            working_dir=_make_working_dir(tmp_path, "eng_setup_cc"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )
        await eng._setup_agent()
        assert eng.agent is not None
        assert eng.app is not None

    @pytest.mark.asyncio
    async def test_evolve_setup_agent_constructs(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="evolve",
            working_dir=_make_working_dir(tmp_path, "eng_setup_evolve"),
            research_mode="evolve",
            domain="aiml",
            use_graphify=False,
        )
        await eng._setup_agent()
        assert eng.agent is not None

    @pytest.mark.asyncio
    async def test_adk_setup_with_graphify(self, tmp_path):
        from ai_research_engineer.core.api import AIEngineer
        eng = AIEngineer(
            agent_type="adk",
            working_dir=_make_working_dir(tmp_path, "eng_setup_gph"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=True,
        )
        await eng._setup_agent()
        assert eng.agent is not None
