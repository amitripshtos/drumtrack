from typing import Optional

from app.models.job import Job, JobStatus


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float = 0.0,
        error: Optional[str] = None,
    ) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = status
        job.progress = progress
        if error is not None:
            job.error = error
        return job

    def find_by_audio_hash(self, audio_hash: str, exclude_id: str) -> Optional[Job]:
        """Find a completed job with the same audio hash (for stem reuse)."""
        for job in self._jobs.values():
            if (
                job.id != exclude_id
                and job.audio_hash == audio_hash
                and job.status == JobStatus.complete
            ):
                return job
        return None


job_store = JobStore()
