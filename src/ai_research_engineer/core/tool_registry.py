"""Tool registry (S1-3 seed; formalized in S1-6).

Tools register with a ``requires`` list of requirement tokens; the registry
resolves availability against the environment and exposes the subset of tools
whose requirements are all satisfied.

Requirement tokens:
  * ``"network"``                    — outbound network is enabled,
  * ``"key:ENV_NAME"``               — env var ENV_NAME is set,
  * ``"binary:NAME"``                — NAME is on PATH,
  * ``"config:search.web_provider"`` — a web-search provider is configured+keyed.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, List


logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    func: Callable
    requires: List[str] = field(default_factory=list)


_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(name: str, func: Callable, requires: List[str] | None = None) -> Callable:
    """Register a tool with its requirements. Returns ``func`` (usable as sugar)."""
    _REGISTRY[name] = ToolSpec(name=name, func=func, requires=list(requires or []))
    return func


def _config_requirement_met(key: str) -> bool:
    if key == "search.web_provider":
        from ai_research_engineer.core.config import web_provider_ready

        return web_provider_ready()
    logger.warning("[tool_registry] unknown config requirement: %s", key)
    return True


def _requirement_met(req: str) -> bool:
    if req == "network":
        try:
            from ai_research_engineer.agents.adk.utils import is_network_disabled

            return not is_network_disabled()
        except Exception:
            return True
    if req.startswith("key:"):
        return bool(os.getenv(req[len("key:") :], "").strip())
    if req.startswith("binary:"):
        return shutil.which(req[len("binary:") :]) is not None
    if req.startswith("config:"):
        return _config_requirement_met(req[len("config:") :])
    logger.warning("[tool_registry] unknown requirement token: %s", req)
    return True


def is_available(name: str) -> bool:
    """Whether every requirement of the named tool is currently satisfied."""
    spec = _REGISTRY.get(name)
    return bool(spec) and all(_requirement_met(r) for r in spec.requires)


def available_tools() -> List[Callable]:
    """Callables for every registered tool whose requirements are met."""
    return [spec.func for spec in _REGISTRY.values() if is_available(spec.name)]


def available_tool_names() -> List[str]:
    return [name for name in _REGISTRY if is_available(name)]


def registered_names() -> List[str]:
    return list(_REGISTRY)


def requirements(name: str) -> List[str]:
    spec = _REGISTRY.get(name)
    return list(spec.requires) if spec else []
