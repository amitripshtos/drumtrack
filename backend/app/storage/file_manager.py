import shutil
from pathlib import Path

from app.config import settings

CHECKPOINT_ARTIFACTS: dict[str, list[str]] = {
    "stem_separation": [
        "drum.mp3",
        "other.mp3",
        "stems/",
        "events.json",
        "clusters.json",
        "output.mid",
    ],
    "drumsep": ["stems/", "events.json", "clusters.json", "output.mid"],
    "onset_detection": ["events.json", "clusters.json", "output.mid"],
}

CHECKPOINT_REQUIRED: dict[str, list[str]] = {
    "stem_separation": ["original.mp3"],
    "drumsep": ["drum.mp3"],
    "onset_detection": ["drum.mp3"],
}


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

    def stems_dir(self, job_id: str) -> Path:
        d = self.job_dir(job_id) / "stems"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def drum_stem_path(self, job_id: str, stem_name: str) -> Path:
        return self.stems_dir(job_id) / f"{stem_name}.wav"

    def clear_from_checkpoint(self, job_id: str, checkpoint: str) -> None:
        """Delete downstream artifacts for a given checkpoint."""
        artifacts = CHECKPOINT_ARTIFACTS.get(checkpoint, [])
        job = self.job_dir(job_id)
        for name in artifacts:
            path = job / name
            if name.endswith("/"):
                if path.exists():
                    shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)

    def has_required_artifacts(self, job_id: str, checkpoint: str) -> bool:
        """Check if required artifacts exist for a checkpoint."""
        required = CHECKPOINT_REQUIRED.get(checkpoint, [])
        job = self.job_dir(job_id)
        return all((job / name).exists() for name in required)


file_manager = FileManager()
