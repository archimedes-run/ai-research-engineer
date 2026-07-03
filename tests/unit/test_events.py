"""Unit tests for event system."""

from ai_research_engineer.core.events import (
    CompletedEvent,
    ErrorEvent,
    FunctionCallEvent,
    FunctionResponseEvent,
    GateDecisionEvent,
    MessageEvent,
    UsageEvent,
    create_event,
    event_to_dict,
)


class TestMessageEvent:
    """Test MessageEvent."""

    def test_message_event_creation(self):
        """Test MessageEvent creation."""
        event = MessageEvent(
            content="Test message",
            author="test_agent",
            timestamp="12:34:56.789",
            is_thought=False,
            is_partial=False,
            event_number=1,
        )
        assert event.type == "message"
        assert event.content == "Test message"
        assert event.author == "test_agent"
        assert event.is_thought is False
        assert event.is_partial is False
        assert event.event_number == 1

    def test_thought_message_event(self):
        """Test MessageEvent for thoughts."""
        event = MessageEvent(
            content="Thinking...",
            author="test_agent",
            timestamp="12:34:56.789",
            is_thought=True,
            is_partial=False,
            event_number=1,
        )
        assert event.is_thought is True


class TestFunctionCallEvent:
    """Test FunctionCallEvent."""

    def test_function_call_event(self):
        """Test FunctionCallEvent creation."""
        event = FunctionCallEvent(
            name="test_function",
            arguments={"param1": "value1", "param2": 42},
            author="test_agent",
            timestamp="12:34:56.789",
            event_number=2,
        )
        assert event.type == "function_call"
        assert event.name == "test_function"
        assert event.arguments["param1"] == "value1"
        assert event.arguments["param2"] == 42


class TestFunctionResponseEvent:
    """Test FunctionResponseEvent."""

    def test_function_response_event(self):
        """Test FunctionResponseEvent creation."""
        event = FunctionResponseEvent(
            name="test_function",
            response={"result": "success"},
            author="test_agent",
            timestamp="12:34:56.789",
            event_number=3,
        )
        assert event.type == "function_response"
        assert event.name == "test_function"
        assert event.response["result"] == "success"


class TestUsageEvent:
    """Test UsageEvent."""

    def test_usage_event(self):
        """Test UsageEvent creation."""
        usage_info = {
            "total_input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 50,
        }
        event = UsageEvent(usage=usage_info, timestamp="12:34:56.789")
        assert event.type == "usage"
        assert event.usage["total_input_tokens"] == 100
        assert event.usage["cached_input_tokens"] == 20
        assert event.usage["output_tokens"] == 50


class TestErrorEvent:
    """Test ErrorEvent."""

    def test_error_event(self):
        """Test ErrorEvent creation."""
        event = ErrorEvent(content="Test error", timestamp="12:34:56.789")
        assert event.type == "error"
        assert event.content == "Test error"


class TestCompletedEvent:
    """Test CompletedEvent."""

    def test_completed_event(self):
        """Test CompletedEvent creation."""
        event = CompletedEvent(
            session_id="test_session",
            duration=1.5,
            total_events=10,
            files_created=["output.txt", "data.csv"],
            files_count=2,
            timestamp="12:34:56.789",
        )
        assert event.type == "completed"
        assert event.session_id == "test_session"
        assert event.duration == 1.5
        assert event.total_events == 10
        assert event.files_count == 2
        assert len(event.files_created) == 2

    def test_completed_event_manuscript_status_default_omitted(self):
        """manuscript_status defaults to None and is omitted from the dict (S0-1)."""
        event = CompletedEvent(session_id="s", timestamp="12:34:56.789")
        assert event.manuscript_status is None
        assert "manuscript_status" not in event_to_dict(event)

    def test_completed_event_manuscript_status_serialized_when_set(self):
        """A DRAFT_UNVERIFIED manuscript surfaces on the completed event (S0-1)."""
        event = CompletedEvent(
            session_id="s",
            manuscript_status="DRAFT_UNVERIFIED",
            timestamp="12:34:56.789",
        )
        assert event_to_dict(event)["manuscript_status"] == "DRAFT_UNVERIFIED"


class TestGateDecisionEvent:
    """Test GateDecisionEvent (S0-1 / S0-9)."""

    def test_gate_decision_event_creation(self):
        event = GateDecisionEvent(
            loop="implementation_loop",
            outcome="exhausted",
            reason="max_iterations reached without approval",
            timestamp="12:34:56.789",
        )
        assert event.type == "gate_decision"
        assert event.loop == "implementation_loop"
        assert event.outcome == "exhausted"

    def test_gate_decision_registered_in_factory(self):
        """create_event must know the gate_decision type and round-trip it."""
        event = create_event(
            "gate_decision",
            loop="ideation_loop",
            outcome="approved",
            reason="confirmation agent approved",
        )
        payload = event_to_dict(event)
        assert payload["type"] == "gate_decision"
        assert payload["loop"] == "ideation_loop"
        assert payload["outcome"] == "approved"
        assert payload["reason"] == "confirmation agent approved"


class TestEventToDict:
    """Test event_to_dict function."""

    def test_message_event_to_dict(self):
        """Test converting MessageEvent to dict."""
        event = MessageEvent(
            content="Test",
            author="agent",
            timestamp="12:34:56.789",
            is_thought=False,
            is_partial=False,
            event_number=1,
        )
        event_dict = event_to_dict(event)
        assert event_dict["type"] == "message"
        assert event_dict["content"] == "Test"
        assert event_dict["author"] == "agent"
        assert event_dict["is_thought"] is False

    def test_function_call_to_dict(self):
        """Test converting FunctionCallEvent to dict."""
        event = FunctionCallEvent(
            name="func",
            arguments={"x": 1},
            author="agent",
            timestamp="12:34:56.789",
            event_number=1,
        )
        event_dict = event_to_dict(event)
        assert event_dict["type"] == "function_call"
        assert event_dict["name"] == "func"
        assert event_dict["arguments"] == {"x": 1}

    def test_completed_event_to_dict(self):
        """Test converting CompletedEvent to dict."""
        event = CompletedEvent(
            session_id="test",
            duration=1.0,
            total_events=5,
            files_created=[],
            files_count=0,
            timestamp="12:34:56.789",
        )
        event_dict = event_to_dict(event)
        assert event_dict["type"] == "completed"
        assert event_dict["session_id"] == "test"
        assert event_dict["duration"] == 1.0
