from pydantic import BaseModel


class DrumEvent(BaseModel):
    time: float  # seconds
    quantized_time: float  # seconds, snapped to grid
    drum_type: str  # e.g. "kick", "snare", "closed_hihat"
    midi_note: int  # GM drum map note number
    velocity: int  # 0-127
    confidence: float  # 0-1
    cluster_id: int = -1
