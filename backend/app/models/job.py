from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
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
    source_url: Optional[str] = None
    separator: str = "demucs"  # "demucs" or "lalal"
    audio_hash: Optional[str] = None  # SHA-256 of original audio for dedup
    title: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0-100


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    bpm: float
    source: str
    separator: str = "demucs"
    title: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None
    progress: float = 0.0


class YouTubeRequest(BaseModel):
    url: str
    bpm: float
    separator: str = "demucs"
