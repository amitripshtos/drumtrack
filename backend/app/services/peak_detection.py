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
    "kick": {"delta": 0.08, "wait": 3},  # Avoid resonance double-triggers
    "snare": {"delta": 0.06, "wait": 2},  # Ghost notes can be fast
    "toms": {"delta": 0.07, "wait": 3},  # Similar to kick
    "hh": {"delta": 0.05, "wait": 1},  # Hi-hats can be very fast (16ths)
    "cymbals": {"delta": 0.06, "wait": 4},  # Cymbals ring long, avoid retriggers
}

DEFAULT_PARAMS = {"delta": 0.06, "wait": 2}


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
        backtrack=True,
        pre_max=2,
        post_max=2,
        pre_avg=3,
        post_avg=4,
        delta=params["delta"],
        wait=params["wait"],
    )

    if len(onset_frames) == 0:
        return []

    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    onset_samples = librosa.frames_to_samples(onset_frames, hop_length=512)

    logger.info(f"Stem '{stem_name}': detected {len(onset_frames)} raw onsets")

    # Measure velocity (RMS amplitude at each onset)
    events = []
    sixteenth_duration = 60.0 / bpm / 4.0
    quantize_tolerance = 0.30  # 30% tolerance to preserve swing

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
