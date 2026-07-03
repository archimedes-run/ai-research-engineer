"""Unit tests for event system."""

from ai_research_engineer.core.events import (
    CompletedEvent,
    ErrorEvent,
    EvalResultEvent,
    FunctionCallEvent,
    FunctionResponseEvent,
    GateDecisionEvent,
    IntakeDecisionEvent,
    MessageEvent,
    ProgressHashEvent,
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


class TestProgressHashEvent:
    """Test ProgressHashEvent (S0-3 / S0-9)."""

    def test_progress_hash_event_creation(self):
        event = ProgressHashEvent(hash="abc123", iteration=2, timestamp="12:34:56.789")
        assert event.type == "progress_hash"
        assert event.hash == "abc123"
        assert event.iteration == 2

    def test_progress_hash_registered_in_factory(self):
        payload = event_to_dict(create_event("progress_hash", hash="deadbeef", iteration=3))
        assert payload["type"] == "progress_hash"
        assert payload["hash"] == "deadbeef"
        assert payload["iteration"] == 3


class TestEvalResultEvent:
    """Test EvalResultEvent (S0-4 / S0-9)."""

    def test_eval_result_event_creation(self):
        event = EvalResultEvent(gen=2, score=0.9, status="success", duration_s=1.25, timestamp="12:34:56.789")
        assert event.type == "eval_result"
        assert event.gen == 2
        assert event.score == 0.9
        assert event.status == "success"
        assert event.duration_s == 1.25

    def test_eval_result_success_round_trip(self):
        payload = event_to_dict(create_event("eval_result", gen=1, score=0.7, status="success", duration_s=2.0))
        assert payload["type"] == "eval_result"
        assert payload["score"] == 0.7
        assert payload["status"] == "success"
        assert payload["duration_s"] == 2.0

    def test_eval_result_none_score_omitted(self):
        """A failed/timeout eval has score=None, which event_to_dict omits."""
        payload = event_to_dict(create_event("eval_result", gen=3, score=None, status="timeout", duration_s=0.5))
        assert payload["status"] == "timeout"
        assert payload.get("score") is None
        assert "score" not in payload


class TestIntakeDecisionEvent:
    """Test IntakeDecisionEvent (S0-5 / S0-9)."""

    def test_intake_decision_event_creation(self):
        event = IntakeDecisionEvent(
            detected_intent="replicate", selected_mode="replication", action="switch", timestamp="12:34:56.789"
        )
        assert event.type == "intake_decision"
        assert event.detected_intent == "replicate"
        assert event.selected_mode == "replication"
        assert event.action == "switch"

    def test_intake_decision_registered_in_factory(self):
        payload = event_to_dict(
            create_event("intake_decision", detected_intent="optimize", selected_mode="evolve", action="switch")
        )
        assert payload["type"] == "intake_decision"
        assert payload["detected_intent"] == "optimize"
        assert payload["action"] == "switch"


class TestStageStatusEvent:
    """Test StageStatusEvent (S0-2 / S0-9)."""

    def test_stage_status_round_trip(self):
        payload = event_to_dict(create_event("stage_status", index=2, status="completed_unverified"))
        assert payload["type"] == "stage_status"
        assert payload["index"] == 2
        assert payload["status"] == "completed_unverified"


# Fields for each S0-9 typed event (used by the session-store round-trip test).
_S0_9_EVENT_SAMPLES = [
    ("gate_decision", {"loop": "implementation_loop", "outcome": "exhausted", "reason": "max_iterations"}),
    ("stage_status", {"index": 3, "status": "completed_unverified"}),
    ("eval_result", {"gen": 1, "score": 0.9, "status": "success", "duration_s": 1.5}),
    ("progress_hash", {"hash": "deadbeef", "iteration": 4}),
    ("intake_decision", {"detected_intent": "replicate", "selected_mode": "replication", "action": "switch"}),
]


class TestS0_9EventSessionStoreRoundTrip:
    """S0-9: each new typed event serializes and round-trips through the session
    store (RunStore) unchanged."""

    def test_all_new_event_types_round_trip(self, tmp_path):
        from datetime import datetime

        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "events.db")
        RunStore.save_session(
            {
                "session_id": "sess-events",
                "status": "running",
                "title": "T",
                "topic": "x",
                "agent_type": "adk",
                "started_at": datetime.now().isoformat(),
            }
        )

        for etype, fields in _S0_9_EVENT_SAMPLES:
            payload = event_to_dict(create_event(etype, **fields))
            RunStore.append_event("sess-events", payload)

        stored_by_type = {e["type"]: e for e in RunStore.get_events("sess-events")}

        for etype, fields in _S0_9_EVENT_SAMPLES:
            assert etype in stored_by_type, f"{etype} did not survive the session store"
            stored = stored_by_type[etype]
            for key, value in fields.items():
                assert stored.get(key) == value, f"{etype}.{key} changed: {stored.get(key)!r} != {value!r}"


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
