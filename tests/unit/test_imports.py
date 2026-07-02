"""
Import smoke tests — guards against NameError / ImportError at module load.

The ClaudeCodeAgent NameError that crashed every run would have been caught
here: importing `agents.adk.agent` (which uses ClaudeCodeAgent) without the
corresponding import statement would raise NameError immediately.

Zero network, zero API keys, zero LLM calls.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterator


def _iter_modules(package_name: str) -> Iterator[str]:
    """Yield every importable dotted module name under *package_name*."""
    root = importlib.import_module(package_name)
    root_path = getattr(root, "__path__", None)
    if root_path is None:
        yield package_name
        return
    yield package_name
    for info in pkgutil.walk_packages(root_path, prefix=f"{package_name}."):
        yield info.name


# Collect once so parametrize has a stable list at collection time


_ALL_MODULES = sorted(_iter_modules("ai_research_engineer"))


class TestImportSmoke:
    """Every module under ai_research_engineer must import without error."""

    def test_module_list_non_empty(self):
        assert len(_ALL_MODULES) > 10, "expected at least 10 modules in the package"

    def test_top_level_package(self):
        mod = importlib.import_module("ai_research_engineer")
        assert isinstance(mod, ModuleType)

    def test_agents_adk(self):
        # This is THE module that used ClaudeCodeAgent without importing it.
        # The NameError would have surfaced here.
        mod = importlib.import_module("ai_research_engineer.agents.adk.agent")
        assert isinstance(mod, ModuleType)

    def test_agents_adk_init(self):
        mod = importlib.import_module("ai_research_engineer.agents.adk")
        assert hasattr(mod, "create_app")
        assert hasattr(mod, "create_agent")

    def test_agents_claude_code(self):
        mod = importlib.import_module("ai_research_engineer.agents.claude_code.agent")
        assert hasattr(mod, "ClaudeCodeAgent")

    def test_agents_claude_code_init(self):
        mod = importlib.import_module("ai_research_engineer.agents.claude_code")
        assert hasattr(mod, "ClaudeCodeAgent")

    def test_core_api(self):
        mod = importlib.import_module("ai_research_engineer.core.api")
        assert hasattr(mod, "AIEngineer")

    def test_core_events(self):
        mod = importlib.import_module("ai_research_engineer.core.events")
        assert hasattr(mod, "event_to_dict")

    def test_core_pricing(self):
        mod = importlib.import_module("ai_research_engineer.core.pricing")
        assert hasattr(mod, "cost_usd")

    def test_server_app(self):
        mod = importlib.import_module("ai_research_engineer.server.app")
        assert hasattr(mod, "app")

    def test_server_run_store(self):
        mod = importlib.import_module("ai_research_engineer.server.run_store")
        assert hasattr(mod, "RunStore")

    def test_server_models(self):
        mod = importlib.import_module("ai_research_engineer.server.models")
        assert hasattr(mod, "RunSessionRequest")

    def test_all_modules_importable(self):
        """
        Walk every module and import it. Any NameError / ImportError / SyntaxError
        in any module will surface as a test failure with the offending module name.
        """
        failures: list[tuple[str, Exception]] = []
        for name in _ALL_MODULES:
            try:
                importlib.import_module(name)
            except Exception as exc:
                failures.append((name, exc))

        if failures:
            lines = [f"  {name}: {type(exc).__name__}: {exc}" for name, exc in failures]
            raise AssertionError("Modules failed to import:\n" + "\n".join(lines))
