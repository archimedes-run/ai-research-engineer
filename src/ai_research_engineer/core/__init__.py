"""Core API and session management for Agentic Data Scientist."""

from ai_research_engineer.core.api import DataScientist, FileInfo, Result, SessionConfig
from ai_research_engineer.core.events import (
    CompletedEvent,
    ErrorEvent,
    FunctionCallEvent,
    FunctionResponseEvent,
    MessageEvent,
    UsageEvent,
    event_to_dict,
)


__all__ = [
    "DataScientist",
    "Result",
    "SessionConfig",
    "FileInfo",
    "MessageEvent",
    "FunctionCallEvent",
    "FunctionResponseEvent",
    "CompletedEvent",
    "ErrorEvent",
    "UsageEvent",
    "event_to_dict",
]
