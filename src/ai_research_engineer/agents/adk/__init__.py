"""ADK-based agent system."""

from ai_research_engineer.agents.adk.agent import NonEscalatingLoopAgent, create_agent, create_app
from ai_research_engineer.agents.adk.loop_detection import LoopDetectionAgent


__all__ = ["create_agent", "create_app", "LoopDetectionAgent", "NonEscalatingLoopAgent"]
