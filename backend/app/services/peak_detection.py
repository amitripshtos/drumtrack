"""Simple peak detection for isolated drum stems.

Each stem has been separated by DrumSep, so we just need to find
*when* and *how loud* each hit is — no classification needed.
"""

import logging
from pathlib import Path

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Stem-specific onset detection parameters
STEM_PARAMS: dict[str, dict] = {
    "kick": {
        "delta": 0.08,
        "wait": 3,
        "backtrack": False,
        "refine": True,
        "quantize_tolerance": 0.15,
    },
    "snare": {
        "delta": 0.06,
        "wait": 2,
        "backtrack": False,
        "refine": True,
        "quantize_tolerance": 0.15,
    },
    "toms": {
        "delta": 0.07,
        "wait": 3,
        "backtrack": False,
        "refine": True,
        "quantize_tolerance": 0.15,
    },
    "hh": {
        "delta": 0.05,
        "wait": 1,
        "backtrack": True,
        "refine": False,
        "quantize_tolerance": 0.30,
    },
    "cymbals": {
        "delta": 0.06,
        "wait": 4,
        "backtrack": True,
        "refine": False,
        "quantize_tolerance": 0.30,
    },
}

DEFAULT_PARAMS = {
    "delta": 0.06,
    "wait": 2,
    "backtrack": True,
    "refine": False,
    "quantize_tolerance": 0.30,
}


def _refine_onset_time(
    y: np.ndarray, sr: int, coarse_sample: int, window_ms: float = 15.0, threshold_frac: float = 0.3
) -> int:
    """Find the true transient attack point near a coarse onset.

    Searches a ±window_ms region around the coarse onset for the first sample
    that exceeds threshold_frac of the local peak amplitude. This gives
    sample-accurate timing (~0.02ms at 44.1kHz).
    """
    window = int(window_ms / 1000.0 * sr)
    start = max(0, coarse_sample - window)
    end = min(len(y), coarse_sample + window)
    segment = np.abs(y[start:end])
    peak_val = np.max(segment)
    if peak_val == 0:
        return coarse_sample
    above = np.where(segment >= threshold_frac * peak_val)[0]
    return start + int(above[0]) if len(above) > 0 else coarse_sample


def detect_peaks(stem_path: Path, bpm: float, stem_name: str | None = None) -> list[dict]:
    """Detect drum hits in an isolated stem WAV.

    Args:
        stem_path: Path to the stem WAV file
        bpm: Song BPM for quantization
        stem_name: Name of the stem (kick/snare/toms/hh/cymbals) for
                   stem-specific onset detection parameters

    Returns:
        List of dicts with keys: time, quantized_time, velocity
    """
    # Load audio
    y, sr = librosa.load(str(stem_path), sr=44100, mono=True)

    if len(y) == 0:
        return []

    # Get stem-specific params
    params = STEM_PARAMS.get(stem_name, DEFAULT_PARAMS) if stem_name else DEFAULT_PARAMS

    # Onset detection
    onset_frames = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        units="frames",
        hop_length=512,
        backtrack=params.get("backtrack", True),
        pre_max=2,
        post_max=2,
        pre_avg=3,
        post_avg=4,
        delta=params["delta"],
        wait=params["wait"],
    )

    if len(onset_frames) == 0:
        return []

    onset_samples = librosa.frames_to_samples(onset_frames, hop_length=512)

    # Sub-frame refinement for percussive stems
    if params.get("refine", False):
        onset_samples = np.array([_refine_onset_time(y, sr, int(s)) for s in onset_samples])

    onset_times = onset_samples / sr

    logger.info(f"Stem '{stem_name}': detected {len(onset_frames)} raw onsets")

    # Measure velocity (RMS amplitude at each onset)
    events = []
    sixteenth_duration = 60.0 / bpm / 4.0
    quantize_tolerance = params.get("quantize_tolerance", 0.30)

    for time_sec, sample in zip(onset_times, onset_samples, strict=True):
        # RMS in a window around the onset
        window_samples = int(0.05 * sr)  # 50ms window
        start = max(0, int(sample))
        end = min(len(y), start + window_samples)
        segment = y[start:end]

        if len(segment) == 0:
            continue

        rms = np.sqrt(np.mean(segment**2))

        # Map RMS to MIDI velocity (0-127)
        # Use log scale for more natural dynamics
        if rms > 0:
            db = 20 * np.log10(rms + 1e-10)
            # Typical range: -60 dB (very quiet) to 0 dB (max)
            velocity = int(np.clip((db + 50) / 50 * 127, 20, 127))
        else:
            velocity = 20

        # Quantize to 16th note grid with tolerance
        grid_position = round(time_sec / sixteenth_duration)
        quantized_time = grid_position * sixteenth_duration
        deviation = abs(time_sec - quantized_time) / sixteenth_duration

        # Only snap if within tolerance, otherwise keep original time
        if deviation > quantize_tolerance:
            quantized_time = time_sec

        events.append(
            {
                "time": round(float(time_sec), 4),
                "quantized_time": round(float(quantized_time), 4),
                "velocity": velocity,
            }
        )

    return events
