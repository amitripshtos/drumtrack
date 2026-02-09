import numpy as np
import librosa


def extract_rms_at_onset(
    y: np.ndarray, sr: int, onset_sample: int, window_ms: float = 50.0
) -> float:
    """Extract RMS energy in a window at an onset point (for velocity estimation)."""
    window_samples = int(sr * window_ms / 1000.0)
    start = max(0, onset_sample)
    end = min(len(y), onset_sample + window_samples)
    segment = y[start:end]

    if len(segment) < 256:
        segment = np.pad(segment, (0, 256 - len(segment)))

    rms = librosa.feature.rms(y=segment)
    return float(np.mean(rms))
