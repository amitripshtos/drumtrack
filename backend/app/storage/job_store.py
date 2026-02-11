import json
import logging

from app.config import settings
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._load_from_disk()

    def _job_json_path(self, job_id: str):
        return settings.jobs_dir / job_id / "job.json"

    def _persist(self, job: Job) -> None:
        path = self._job_json_path(job.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job.model_dump(), indent=2))

    def _load_from_disk(self) -> None:
        jobs_dir = settings.jobs_dir
        if not jobs_dir.exists():
            return
        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            job_json = job_dir / "job.json"
            if not job_json.exists():
                continue
            try:
                data = json.loads(job_json.read_text())
                job = Job(**data)
                self._jobs[job.id] = job
            except Exception:
                logger.warning(f"Failed to load job from {job_json}", exc_info=True)

    def create(self, job: Job) -> Job:
        self._jobs[job.id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        # Try loading from disk (in case it was created by another process)
        path = self._job_json_path(job_id)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                job = Job(**data)
                self._jobs[job.id] = job
                return job
            except Exception:
                logger.warning(f"Failed to load job from {path}", exc_info=True)
        return None

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float = 0.0,
        error: str | None = None,
    ) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = status
        job.progress = progress
        if error is not None:
            job.error = error
        self._persist(job)
        return job

    def find_by_audio_hash(self, audio_hash: str, exclude_id: str) -> Job | None:
        """Find a completed job with the same audio hash (for stem reuse)."""
        for job in self._jobs.values():
            if (
                job.id != exclude_id
                and job.audio_hash == audio_hash
                and job.status == JobStatus.complete
            ):
                return job
        return None

    def list_all(self) -> list[Job]:
        """Return all jobs sorted by creation time (newest first)."""
        jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at or "", reverse=True)
        return jobs


job_store = JobStore()
