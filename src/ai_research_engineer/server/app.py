import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Dict, List

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from ai_research_engineer.server.models import RunSessionRequest, SubmissionRequest
from ai_research_engineer.server.storage import Storage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# session_id → asyncio.Queue; present only while agent is running
_active_sessions: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Storage.init()
    yield


app = FastAPI(title="AI Research Engineer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/submissions")
async def create_submission(body: SubmissionRequest):
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
async def create_session(body: RunSessionRequest, background_tasks: BackgroundTasks):
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
        session_id, body.topic, body.agent_type,
        body.domain, body.research_mode, body.template, queue,
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

        duration = (datetime.now() - start_time).total_seconds()
        files_created = [
            str(p.relative_to(working_dir))
            for p in working_dir.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.parts)
        ]
        Storage.update_session(session_id, {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "duration": duration,
            "events": events_log,
            "files_created": files_created,
        })

    except Exception as e:
        logger.error(f"Session {session_id} failed: {e}", exc_info=True)
        err = {"type": "error", "content": str(e), "timestamp": datetime.now().strftime("%H:%M:%S")}
        await queue.put(err)
        events_log.append(err)
        Storage.update_session(session_id, {
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "events": events_log,
        })

    finally:
        await queue.put(None)  # sentinel to close SSE connections
        _active_sessions.pop(session_id, None)
