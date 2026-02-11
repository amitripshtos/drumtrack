import logging
from pathlib import Path

import librosa

logger = logging.getLogger(__name__)


def detect_tempo(audio_path: Path) -> float:
    """Detect the BPM of an audio file using librosa."""
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
    bpm = round(bpm)
    logger.info(f"Detected tempo: {bpm} BPM from {audio_path.name}")
    return bpm
