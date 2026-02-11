from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    pending = "pending"
    downloading_youtube = "downloading_youtube"
    uploading_to_lalal = "uploading_to_lalal"
    separating_stems = "separating_stems"
    separating_drum_instruments = "separating_drum_instruments"
    detecting_onsets = "detecting_onsets"
    generating_midi = "generating_midi"
    complete = "complete"
    failed = "failed"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.pending
    bpm: float
    source: str  # "upload" or "youtube"
    source_url: str | None = None
    separator: str = "demucs"  # "demucs" or "lalal"
    audio_hash: str | None = None  # SHA-256 of original audio for dedup
    title: str | None = None
    created_at: str | None = None
    error: str | None = None
    progress: float = 0.0  # 0-100


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    bpm: float
    source: str
    separator: str = "demucs"
    title: str | None = None
    created_at: str | None = None
    error: str | None = None
    progress: float = 0.0


class YouTubeRequest(BaseModel):
    url: str
    bpm: float
    separator: str = "demucs"
