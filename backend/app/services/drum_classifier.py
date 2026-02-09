import logging
from pathlib import Path

import librosa
import numpy as np

from app.ml.classifier import classify_drum, estimate_velocity
from app.ml.drum_classifier_model import drum_classifier
from app.ml.feature_extractor import extract_rms_at_onset
from app.models.drum_event import DrumEvent

logger = logging.getLogger(__name__)


def quantize_time(time_sec: float, bpm: float) -> float:
    """Snap time to nearest 16th note grid position."""
    sixteenth_duration = 60.0 / bpm / 4.0
    grid_position = round(time_sec / sixteenth_duration)
    return grid_position * sixteenth_duration


def detect_and_classify(drum_audio_path: Path, bpm: float) -> list[DrumEvent]:
    """
    Full drum detection pipeline:
    1. Load audio
    2. Ensure SVM classifier is trained
    3. Detect onsets
    4. Extract features + classify each onset
    5. Quantize to 16th-note grid
    """
    logger.info(f"Loading drum audio from {drum_audio_path}")
    y, sr = librosa.load(str(drum_audio_path), sr=22050, mono=True)

    # Lazy-init: train the SVM classifier if not yet trained
    if not drum_classifier.is_trained:
        drum_classifier.train()

    # Onset detection with percussion-tuned parameters
    logger.info("Detecting onsets...")
    onset_frames = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        units="frames",
        hop_length=512,
        backtrack=True,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=5,
        delta=0.07,
        wait=4,
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    onset_samples = librosa.frames_to_samples(onset_frames, hop_length=512)

    logger.info(f"Found {len(onset_frames)} onsets")

    events: list[DrumEvent] = []
    for i, (frame, time_sec, sample) in enumerate(
        zip(onset_frames, onset_times, onset_samples)
    ):
        # Extract 29-dim features for SVM classification
        features = drum_classifier.extract_features(y, sr, sample)
        drum_type, midi_note, confidence = classify_drum(features)

        # RMS for velocity estimation
        rms = extract_rms_at_onset(y, sr, sample)
        velocity = estimate_velocity(rms)

        # Quantize
        quantized = quantize_time(time_sec, bpm)

        events.append(
            DrumEvent(
                time=round(time_sec, 4),
                quantized_time=round(quantized, 4),
                drum_type=drum_type,
                midi_note=midi_note,
                velocity=velocity,
                confidence=round(confidence, 3),
            )
        )

    logger.info(f"Classified {len(events)} drum events")
    return events
