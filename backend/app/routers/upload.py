import asyncio
import hashlib
import uuid

from fastapi import APIRouter, File, Form, UploadFile

from app.models.job import Job, JobResponse, JobStatus, YouTubeRequest
from app.services.pipeline import run_pipeline
from app.storage.file_manager import file_manager
from app.storage.job_store import job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/upload", response_model=JobResponse)
async def upload_file(
    file: UploadFile = File(...),
    bpm: float = Form(...),
    separator: str = Form("demucs"),
):
    """Create a job from an uploaded MP3 file."""
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, bpm=bpm, source="upload", separator=separator)
    job_store.create(job)

    # Save uploaded file and compute hash for dedup
    original_path = file_manager.original_path(job_id)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    original_path.write_bytes(content)
    job.audio_hash = hashlib.sha256(content).hexdigest()

    # Start pipeline in background
    asyncio.create_task(run_pipeline(job_id))

    return JobResponse(**job.model_dump())


@router.post("/youtube", response_model=JobResponse)
async def youtube_upload(request: YouTubeRequest):
    """Create a job from a YouTube URL."""
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        bpm=request.bpm,
        source="youtube",
        source_url=request.url,
        separator=request.separator,
    )
    job_store.create(job)

    # Ensure job directory exists
    file_manager.job_dir(job_id)

    # Start pipeline in background
    asyncio.create_task(run_pipeline(job_id))

    return JobResponse(**job.model_dump())
