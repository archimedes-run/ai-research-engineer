"""
Deprecated: flat-JSON storage backend.

All callers have been migrated to RunStore (run_store.py). This shim
delegates every call to RunStore so that any third-party code importing
Storage continues to work without changes.
"""

from ai_research_engineer.server.run_store import RunStore as _RS


class Storage:
    DATA_DIR = _RS.DATA_DIR
    SESSIONS_DIR = _RS._SESSIONS_DIR
    SUBMISSIONS_FILE = _RS._SUBMISSIONS_FILE
    COUNTER_FILE = _RS._COUNTER_FILE

    @classmethod
    def init(cls):
        _RS.init()

    @classmethod
    def next_display_id(cls) -> str:
        return _RS.next_display_id()

    @classmethod
    def save_submission(cls, data):
        return _RS.save_submission(data)

    @classmethod
    def save_session(cls, session):
        return _RS.save_session(session)

    @classmethod
    def get_session(cls, session_id):
        return _RS.get_session(session_id)

    @classmethod
    def list_sessions(cls):
        return _RS.list_sessions()

    @classmethod
    def update_session(cls, session_id, updates):
        return _RS.update_session(session_id, updates)
