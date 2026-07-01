import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from ai_research_engineer.server.models import RunSessionRequest, SubmissionRequest
from ai_research_engineer.server.storage import Storage


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_API_TOKEN: Optional[str] = os.environ.get("ARCHIMEDES_API_TOKEN")
_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

if not _API_TOKEN:
    logger.warning("ARCHIMEDES_API_TOKEN is not set. POST /api/sessions and POST /api/submissions are unauthenticated.")


def _require_token(token: Optional[str] = Security(_api_key_header)) -> None:
    """Raise 403 if a token is configured and the request does not match it."""
    if _API_TOKEN and token != _API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing API token.")


# ---------------------------------------------------------------------------
# Per-IP rate limiting (token-bucket, in-process)
# NOTE: a shared store (Redis, etc.) is required for multi-worker deployments.
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_REQUESTS = 5  # per IP per window

# ip -> deque of request timestamps
_rate_buckets: Dict[str, deque] = {}


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has exceeded the session-creation rate limit."""
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(ip, deque())

    # Evict timestamps outside the current window
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW:
        bucket.popleft()

    if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: at most {_RATE_LIMIT_MAX_REQUESTS} session "
                f"creations per {_RATE_LIMIT_WINDOW}s per IP."
            ),
        )
    bucket.append(now)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

# session_id → asyncio.Queue; present only while agent is running
_active_sessions: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Storage.init()
    # Reconcile stale running sessions from before the last restart.
    for session in Storage.list_sessions():
        if session.get("status") == "running" and session["session_id"] not in _active_sessions:
            Storage.update_session(session["session_id"], {"status": "interrupted"})
            logger.warning("Marked stale session %s as interrupted on startup.", session["session_id"])
    yield


app = FastAPI(title="AI Research Engineer API", lifespan=lifespan)

# CORS: read allowed origins from env; default to localhost only.
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/submissions")
async def create_submission(
    body: SubmissionRequest,
    _: None = Security(_require_token),
):
    record = Storage.save_submission(body.model_dump())
    return {"id": record["id"], "status": "queued", "message": "Submission received. Research will begin soon."}


@app.get("/api/sessions")
async def list_sessions():
    sessions = Storage.list_sessions()
    for s in sessions:
        if s["session_id"] in _active_sessions:
            s["status"] = "running"
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = Storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id in _active_sessions:
        session["status"] = "running"
    return session


@app.post("/api/sessions")
async def create_session(
    request: Request,
    body: RunSessionRequest,
    background_tasks: BackgroundTasks,
    _: None = Security(_require_token),
):
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    display_id = Storage.next_display_id()

    session_record = {
        "session_id": session_id,
        "display_id": display_id,
        "title": f"Research: {body.topic[:80]}",
        "topic": body.topic,
        "status": "running",
        "agent_type": body.agent_type,
        "domain": body.domain,
        "research_mode": body.research_mode,
        "template": body.template,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "duration": None,
        "events": [],
        "files_created": [],
    }
    Storage.save_session(session_record)

    queue: asyncio.Queue = asyncio.Queue()
    _active_sessions[session_id] = queue

    background_tasks.add_task(
        _run_agent,
        session_id,
        body.topic,
        body.agent_type,
        body.domain,
        body.research_mode,
        body.template,
        queue,
    )

    return {"session_id": session_id, "display_id": display_id}


@app.get("/api/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    session = Storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def generate() -> AsyncGenerator[str, None]:
        # Completed session: replay stored events then close
        if session_id not in _active_sessions:
            for event in session.get("events", []):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'completed'})}\n\n"
            return

        # Live session: drain the queue until sentinel (None)
        queue = _active_sessions[session_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                if event is None:
                    yield f"data: {json.dumps({'type': 'completed'})}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.now().strftime('%H:%M:%S')})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tells nginx not to buffer SSE
        },
    )


_FLUSH_INTERVAL = 10  # persist events to storage every N new events


async def _run_agent(
    session_id: str,
    topic: str,
    agent_type: str,
    domain: str,
    research_mode: str,
    template: str,
    queue: asyncio.Queue,
):
    from ai_research_engineer.core.api import AIEngineer

    working_dir = Storage.DATA_DIR / "runs" / session_id
    working_dir.mkdir(parents=True, exist_ok=True)
    events_log: List[Dict] = []
    unflushed = 0
    start_time = datetime.now()

    try:
        engineer = AIEngineer(
            agent_type=agent_type,
            working_dir=str(working_dir),
            template=template,
            research_mode=research_mode,
            domain=domain,
        )

        gen = await engineer.run_async(topic, stream=True)
        async for event in gen:
            await queue.put(event)
            events_log.append(event)
            unflushed += 1

            # Incremental flush so a crash mid-run doesn't lose everything
            if unflushed >= _FLUSH_INTERVAL:
                Storage.update_session(session_id, {"events": list(events_log)})
                unflushed = 0

        duration = (datetime.now() - start_time).total_seconds()
        files_created = [
            str(p.relative_to(working_dir))
            for p in working_dir.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.parts)
        ]
        Storage.update_session(
            session_id,
            {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "duration": duration,
                "events": events_log,
                "files_created": files_created,
            },
        )

    except Exception as e:
        logger.error(f"Session {session_id} failed: {e}", exc_info=True)
        err = {"type": "error", "content": str(e), "timestamp": datetime.now().strftime("%H:%M:%S")}
        await queue.put(err)
        events_log.append(err)
        Storage.update_session(
            session_id,
            {
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "events": events_log,
            },
        )

    finally:
        await queue.put(None)  # sentinel to close SSE connections
        _active_sessions.pop(session_id, None)
