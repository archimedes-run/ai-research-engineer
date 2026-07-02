import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from ai_research_engineer.server.models import RunSessionRequest, SubmissionRequest
from ai_research_engineer.server.run_store import RunStore


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# File-serving: constants, binary detection, secret redaction
# ---------------------------------------------------------------------------

_EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".git", "node_modules", "__pycache__", ".graphify-out", "graphify-out",
    ".next", ".venv", "venv", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "dist", "build", ".turbo", ".cache",
})

_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".pkl", ".parquet", ".h5", ".hdf5", ".npy", ".npz",
    ".pt", ".pth", ".bin", ".safetensors",
})

_DOTFILE_DENY: frozenset[str] = frozenset({
    ".env", ".env.local", ".env.production", ".env.development",
    ".env.staging", ".netrc", ".npmrc", ".pypirc", ".aws",
})

_MAX_TREE_DEPTH = 6
_MAX_TREE_ENTRIES = 500
_MAX_FILE_BYTES = 512 * 1024  # 512 KB

_SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"(AKIA[0-9A-Z]{16})"),
    re.compile(r'(?i)(api[_\-]?key|token|secret|password|passwd|credential)\s*[=:]\s*["\']([^"\']{8,})["\']'),
    re.compile(r'(?i)(api[_\-]?key|auth[_\-]?token|secret[_\-]?key)\s*=\s*(\S{8,})'),
]


def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except Exception:
        return True


def _redact_secrets(text: str) -> tuple[str, bool]:
    redacted = False
    result = text
    for pat in _SECRET_PATTERNS:
        new = pat.sub("[REDACTED]", result)
        if new != result:
            redacted = True
            result = new
    return result, redacted


def _build_file_tree(root: Path, path: Path, depth: int, counter: List[int]) -> List[dict]:
    if depth > _MAX_TREE_DEPTH or counter[0] >= _MAX_TREE_ENTRIES:
        return []
    entries: List[dict] = []
    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except PermissionError:
        return []
    for item in items:
        if item.name in _EXCLUDE_DIRS:
            continue
        counter[0] += 1
        if counter[0] >= _MAX_TREE_ENTRIES:
            break
        rel = str(item.relative_to(root))
        if item.is_dir():
            children = _build_file_tree(root, item, depth + 1, counter)
            entry: dict = {"path": rel, "type": "dir", "size": 0}
            if children:
                entry["children"] = children
            entries.append(entry)
        else:
            try:
                size = item.stat().st_size
            except OSError:
                size = 0
            entries.append({"path": rel, "type": "file", "size": size})
    return entries


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
# session_id → asyncio.Task; cancelled by the stop endpoint
_active_tasks: Dict[str, "asyncio.Task[None]"] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    RunStore.init()
    # Reconcile stale running sessions from before the last restart.
    # Sessions in "awaiting_input" are intentionally paused — leave them alone.
    for session in RunStore.list_sessions():
        sid = session["session_id"]
        status = session.get("status")
        if status == "running" and sid not in _active_sessions:
            RunStore.update_session(sid, {"status": "interrupted"})
            logger.warning("Marked stale session %s as interrupted on startup.", sid)
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
    record = RunStore.save_submission(body.model_dump())
    return {"id": record["id"], "status": "queued", "message": "Submission received. Research will begin soon."}


@app.get("/api/sessions")
async def list_sessions():
    sessions = RunStore.list_sessions()
    for s in sessions:
        if s["session_id"] in _active_sessions:
            s["status"] = "running"
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id in _active_sessions:
        session["status"] = "running"
    return session


@app.post("/api/sessions")
async def create_session(
    request: Request,
    body: RunSessionRequest,
    _: None = Security(_require_token),
):
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    display_id = RunStore.next_display_id()

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
        "use_graphify": int(body.use_graphify),
        "hitl_enabled": int(body.hitl_enabled),
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "duration": None,
        "files_created": [],
    }
    RunStore.save_session(session_record)

    queue: asyncio.Queue = asyncio.Queue()
    _active_sessions[session_id] = queue
    _active_tasks[session_id] = asyncio.create_task(
        _run_agent(
            session_id,
            body.topic,
            body.agent_type,
            body.domain,
            body.research_mode,
            body.template,
            body.use_graphify,
            body.hitl_enabled,
            queue,
        )
    )

    return {"session_id": session_id, "display_id": display_id}


@app.get("/api/sessions/{session_id}/events")
async def get_session_events(
    session_id: str,
    after_seq: int = Query(default=0, ge=0),
):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return RunStore.get_events(session_id, after_seq=after_seq)


@app.get("/api/sessions/{session_id}/tree")
async def get_session_tree(session_id: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        from ai_research_engineer.core.argument_tree import TreeBuilder

        tree = TreeBuilder(session_id)
        try:
            raw_graph = tree.to_graph()
            redacted_nodes = []
            for node in raw_graph["nodes"]:
                node = dict(node)
                node["label"], _ = _redact_secrets(node.get("label", ""))
                meta = node.get("metadata") or {}
                node["metadata"] = {
                    k: _redact_secrets(v)[0] if isinstance(v, str) else v
                    for k, v in meta.items()
                }
                redacted_nodes.append(node)
            graph = {"nodes": redacted_nodes, "edges": raw_graph["edges"]}
            return {
                "stats": tree.get_stats(),
                "gaps": tree.find_gaps(),
                "context": tree.to_context(),
                "graph": graph,
            }
        finally:
            tree.close()
    except Exception as exc:
        logger.warning("Tree read failed for session %s: %s", session_id, exc)
        return {
            "stats": {"total_nodes": 0, "by_type": {}, "by_status": {}},
            "gaps": [],
            "context": "",
            "graph": {"nodes": [], "edges": []},
        }


@app.get("/api/sessions/{session_id}/hitl")
async def get_session_hitl(session_id: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    pending = RunStore.get_pending_hitl(session_id)
    return {"pending": pending}


@app.post("/api/sessions/{session_id}/answer")
async def answer_hitl(
    session_id: str,
    body: dict,
    _: None = Security(_require_token),
):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pending = RunStore.get_pending_hitl(session_id)
    if not pending:
        raise HTTPException(status_code=409, detail="No pending HITL request for this session")

    answer = body.get("answer", "")
    if not answer:
        raise HTTPException(status_code=422, detail="answer field is required")

    ok = RunStore.answer_hitl_request(pending["request_id"], answer)
    if not ok:
        raise HTTPException(status_code=409, detail="HITL request already answered")

    # Resume the workflow in the background
    queue: asyncio.Queue = asyncio.Queue()
    _active_sessions[session_id] = queue
    RunStore.update_session(session_id, {"status": "running"})
    _active_tasks[session_id] = asyncio.create_task(
        _run_agent_resume(session_id, pending["stage_key"], answer, queue)
    )

    return {"status": "resuming", "request_id": pending["request_id"]}


@app.post("/api/sessions/{session_id}/resume")
async def resume_session(
    session_id: str,
    _: None = Security(_require_token),
):
    """Resume a session that is awaiting_input without providing a new answer
    (re-uses the last answer already stored, or resumes if answer was recorded externally)."""
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") not in ("awaiting_input", "interrupted"):
        raise HTTPException(status_code=409, detail="Session is not in a resumable state")
    if session_id in _active_sessions:
        raise HTTPException(status_code=409, detail="Session is already running")

    checkpoint = RunStore.load_checkpoint(session_id)
    if not checkpoint:
        raise HTTPException(status_code=409, detail="No checkpoint found for this session")

    queue: asyncio.Queue = asyncio.Queue()
    _active_sessions[session_id] = queue
    RunStore.update_session(session_id, {"status": "running"})

    _active_tasks[session_id] = asyncio.create_task(
        _run_agent_resume(session_id, checkpoint["stage_key"], None, queue)
    )

    return {"status": "resuming"}


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    _: None = Security(_require_token),
):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id not in _active_sessions:
        raise HTTPException(status_code=409, detail="Session is not currently running")

    # Mark interrupted before cancelling so status is consistent even if task
    # is slow to notice the CancelledError.
    RunStore.update_session(
        session_id,
        {"status": "interrupted", "completed_at": datetime.now().isoformat()},
    )

    stop_event = {
        "type": "error",
        "content": "Session stopped by user.",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    queue = _active_sessions.pop(session_id, None)
    task = _active_tasks.pop(session_id, None)

    if queue:
        await queue.put(stop_event)
        RunStore.append_event(session_id, stop_event)
        await queue.put(None)  # close SSE stream

    if task and not task.done():
        task.cancel()

    return {"status": "interrupted"}


@app.get("/api/sessions/{session_id}/usage")
async def get_session_usage(session_id: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return RunStore.get_usage(session_id)


@app.get("/api/sessions/{session_id}/files")
async def get_session_files(session_id: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    working_dir = RunStore.DATA_DIR / "runs" / session_id
    if not working_dir.exists():
        raise HTTPException(status_code=404, detail="Working directory not found")
    counter = [0]
    return _build_file_tree(working_dir, working_dir, 0, counter)


@app.get("/api/sessions/{session_id}/files/{file_path:path}")
async def get_session_file_content(session_id: str, file_path: str):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    working_dir = RunStore.DATA_DIR / "runs" / session_id
    if not working_dir.exists():
        raise HTTPException(status_code=404, detail="Working directory not found")

    from ai_research_engineer.tools.file_ops import _validate_path

    try:
        abs_path = _validate_path(file_path, str(working_dir))
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal denied")

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not abs_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    if abs_path.name in _DOTFILE_DENY or (abs_path.name.startswith(".env")):
        raise HTTPException(status_code=403, detail="Access to this file is denied")

    size = abs_path.stat().st_size

    if _is_binary(abs_path):
        return {"path": file_path, "binary": True, "too_large": False, "size": size}

    if size > _MAX_FILE_BYTES:
        return {"path": file_path, "binary": False, "too_large": True, "size": size}

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"path": file_path, "binary": True, "too_large": False, "size": size}

    content, redacted = _redact_secrets(content)
    return {
        "path": file_path,
        "content": content,
        "size": size,
        "binary": False,
        "too_large": False,
        "redacted": redacted,
    }


@app.get("/api/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    after_seq: int = Query(default=0, ge=0),
):
    session = RunStore.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def generate() -> AsyncGenerator[str, None]:
        # Completed session: replay stored events then close
        if session_id not in _active_sessions:
            for event in RunStore.get_events(session_id, after_seq=after_seq):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'completed'})}\n\n"
            return

        # Live session: replay already-persisted events, then drain the live queue
        for event in RunStore.get_events(session_id, after_seq=after_seq):
            yield f"data: {json.dumps(event)}\n\n"

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
    use_graphify: bool,
    hitl_enabled: bool,
    queue: asyncio.Queue,
):
    from ai_research_engineer.core.api import AIEngineer

    working_dir = RunStore.DATA_DIR / "runs" / session_id
    working_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    # Build code graph before starting the agent (fail-soft)
    if use_graphify:
        try:
            from ai_research_engineer.core.graphify import ensure_graph, graphify_available

            if graphify_available():
                await asyncio.to_thread(ensure_graph, working_dir)
        except Exception as _ge:
            logger.warning("graphify ensure_graph failed at run start: %s", _ge)

    try:
        engineer = AIEngineer(
            agent_type=agent_type,
            working_dir=str(working_dir),
            template=template,
            research_mode=research_mode,
            domain=domain,
            use_graphify=use_graphify,
            hitl_enabled=hitl_enabled,
            session_id=session_id,
        )

        from ai_research_engineer.core.pricing import cost_usd as _cost_usd

        gen = await engineer.run_async(topic, stream=True)
        async for event in gen:
            await queue.put(event)
            seq = RunStore.append_event(session_id, event)

            if event.get("type") == "usage":
                u = event.get("usage", {})
                model = event.get("model")
                inp = u.get("input_tokens", 0) or 0
                cached = u.get("cached_input_tokens", 0) or 0
                out = u.get("output_tokens", 0) or 0
                usd = _cost_usd(model, inp, out, cached)
                RunStore.add_usage(
                    session_id=session_id,
                    seq=seq,
                    input_tokens=inp,
                    output_tokens=out,
                    cached_input_tokens=cached,
                    model=model,
                    engine="adk",
                    cost_usd=usd,
                )

        duration = (datetime.now() - start_time).total_seconds()
        files_created = [
            str(p.relative_to(working_dir))
            for p in working_dir.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.parts)
        ]
        RunStore.update_session(
            session_id,
            {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "duration": duration,
                "files_created": files_created,
            },
        )

    except Exception as e:
        logger.error(f"Session {session_id} failed: {e}", exc_info=True)
        err = {"type": "error", "content": str(e), "timestamp": datetime.now().strftime("%H:%M:%S")}
        await queue.put(err)
        RunStore.append_event(session_id, err)
        RunStore.update_session(
            session_id,
            {
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
            },
        )

    finally:
        await queue.put(None)  # sentinel to close SSE connections
        _active_sessions.pop(session_id, None)
        _active_tasks.pop(session_id, None)


async def _run_agent_resume(
    session_id: str,
    gate_key: str,
    answer: Optional[str],
    queue: asyncio.Queue,
):
    """Resume a paused HITL session from its last checkpoint."""
    from ai_research_engineer.core.api import AIEngineer

    session_rec = RunStore.get_session(session_id)
    if not session_rec:
        logger.error("Resume: session %s not found", session_id)
        await queue.put(None)
        _active_sessions.pop(session_id, None)
        return

    working_dir = RunStore.DATA_DIR / "runs" / session_id
    working_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    # Load checkpoint state
    checkpoint = RunStore.load_checkpoint(session_id)
    initial_state: dict = checkpoint["state"] if checkpoint else {}

    # Inject the answer into state so agents can read it
    if answer is not None:
        initial_state[f"_hitl_answer:{gate_key}"] = answer

    # Clear pause keys so the next run continues normally
    for key in ("_hitl_paused", "_hitl_request_id", "_hitl_question", "_hitl_context_md"):
        initial_state.pop(key, None)

    try:
        engineer = AIEngineer(
            agent_type=session_rec.get("agent_type", "adk"),
            working_dir=str(working_dir),
            template=session_rec.get("template", "NeurReps_2024_Template"),
            research_mode=session_rec.get("research_mode", "novelty"),
            domain=session_rec.get("domain", "aiml"),
            use_graphify=bool(session_rec.get("use_graphify", 0)),
            hitl_enabled=bool(session_rec.get("hitl_enabled", 0)),
            session_id=session_id,
        )

        from ai_research_engineer.core.pricing import cost_usd as _cost_usd

        topic = session_rec.get("topic", "")
        gen = await engineer.run_async(topic, stream=True, initial_state=initial_state)
        async for event in gen:
            await queue.put(event)
            seq = RunStore.append_event(session_id, event)

            if event.get("type") == "usage":
                u = event.get("usage", {})
                model = event.get("model")
                inp = u.get("input_tokens", 0) or 0
                cached = u.get("cached_input_tokens", 0) or 0
                out = u.get("output_tokens", 0) or 0
                usd = _cost_usd(model, inp, out, cached)
                RunStore.add_usage(
                    session_id=session_id,
                    seq=seq,
                    input_tokens=inp,
                    output_tokens=out,
                    cached_input_tokens=cached,
                    model=model,
                    engine="adk",
                    cost_usd=usd,
                )

        # Check if paused again (another gate hit)
        final_status = "awaiting_input" if initial_state.get("_hitl_paused") else "completed"
        if final_status == "completed":
            duration = (datetime.now() - start_time).total_seconds()
            files_created = [
                str(p.relative_to(working_dir))
                for p in working_dir.rglob("*")
                if p.is_file() and not any(part.startswith(".") for part in p.parts)
            ]
            RunStore.update_session(
                session_id,
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "duration": duration,
                    "files_created": files_created,
                },
            )
        else:
            RunStore.update_session(session_id, {"status": "awaiting_input"})

    except Exception as e:
        logger.error(f"Resume session {session_id} failed: {e}", exc_info=True)
        err = {"type": "error", "content": str(e), "timestamp": datetime.now().strftime("%H:%M:%S")}
        await queue.put(err)
        RunStore.append_event(session_id, err)
        RunStore.update_session(
            session_id,
            {
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
            },
        )

    finally:
        await queue.put(None)
        _active_sessions.pop(session_id, None)
        _active_tasks.pop(session_id, None)
