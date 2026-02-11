import asyncio
import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, UploadFile

from app.models.job import Job, JobResponse, YouTubeRequest
from app.services.pipeline import run_pipeline
from app.storage.file_manager import file_manager
from app.storage.job_store import job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Hold references to background tasks so they aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()


@router.post("/upload", response_model=JobResponse)
async def upload_file(
    file: UploadFile = File(...),
    bpm: float | None = Form(None),
    auto_detect_bpm: bool = Form(False),
):
    """Create a job from an uploaded MP3 file."""
    job_id = str(uuid.uuid4())
    effective_bpm = 0 if (auto_detect_bpm or bpm is None) else bpm
    job = Job(
        id=job_id,
        bpm=effective_bpm,
        source="upload",
        title=file.filename or "upload",
        created_at=datetime.now(UTC).isoformat(),
    )
    job_store.create(job)

    # Save uploaded file and compute hash for dedup
    original_path = file_manager.original_path(job_id)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    original_path.write_bytes(content)
    job.audio_hash = hashlib.sha256(content).hexdigest()

    # Start pipeline in background
    task = asyncio.create_task(run_pipeline(job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JobResponse(**job.model_dump())


@router.post("/youtube", response_model=JobResponse)
async def youtube_upload(request: YouTubeRequest):
    """Create a job from a YouTube URL."""
    job_id = str(uuid.uuid4())
    effective_bpm = 0 if (request.auto_detect_bpm or request.bpm is None) else request.bpm
    job = Job(
        id=job_id,
        bpm=effective_bpm,
        source="youtube",
        source_url=request.url,
        title=request.url,
        created_at=datetime.now(UTC).isoformat(),
    )
    job_store.create(job)

    # Ensure job directory exists
    file_manager.job_dir(job_id)

    # Start pipeline in background
    task = asyncio.create_task(run_pipeline(job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JobResponse(**job.model_dump())
