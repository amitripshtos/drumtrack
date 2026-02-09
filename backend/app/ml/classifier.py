import numpy as np

from app.ml.drum_classifier_model import drum_classifier


def classify_drum(features: np.ndarray) -> tuple[str, int, float]:
    """
    Classify a 29-dim feature vector using the SVM model.
    Returns (drum_type, midi_note, confidence).
    """
    return drum_classifier.classify(features)


def estimate_velocity(rms: float, min_vel: int = 40, max_vel: int = 127) -> int:
    """Map RMS energy to MIDI velocity."""
    # Normalize RMS to 0-1 range (typical RMS for drums: 0.01 - 0.5)
    normalized = min(1.0, max(0.0, rms / 0.3))
    velocity = int(min_vel + normalized * (max_vel - min_vel))
    return min(max_vel, max(min_vel, velocity))
