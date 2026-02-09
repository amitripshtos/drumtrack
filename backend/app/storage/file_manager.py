from pathlib import Path

from app.config import settings


class FileManager:
    def job_dir(self, job_id: str) -> Path:
        d = settings.jobs_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def original_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "original.mp3"

    def drum_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "drum.mp3"

    def other_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "other.mp3"

    def midi_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "output.mid"

    def events_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "events.json"

    def clusters_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "clusters.json"


file_manager = FileManager()
