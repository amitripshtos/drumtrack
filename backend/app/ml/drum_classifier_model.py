"""SVM-RBF drum classifier trained from reference samples at startup."""

import logging
from pathlib import Path

import librosa
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from app.ml.drum_map import DRUM_MAP

logger = logging.getLogger(__name__)

# Map sample filenames to drum type keys in DRUM_MAP
SAMPLE_TO_TYPE = {
    "kick.wav": "kick",
    "snare.wav": "snare",
    "hihat-closed.wav": "closed_hihat",
    "hihat-open.wav": "open_hihat",
    "tom-high.wav": "tom_high",
    "tom-mid.wav": "tom_mid",
    "tom-low.wav": "tom_low",
    "crash.wav": "crash",
    "ride.wav": "ride",
}

# 6 frequency band boundaries in Hz
FREQ_BANDS = [(0, 80), (80, 250), (250, 1000), (1000, 3000), (3000, 8000), (8000, None)]

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "public" / "samples"


class DrumClassifierModel:
    """SVM-RBF classifier trained from 9 reference drum samples with augmentation."""

    def __init__(self):
        self.scaler: StandardScaler | None = None
        self.svm: SVC | None = None
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def train(self, samples_dir: Path | None = None, augmentations_per_class: int = 50):
        """Load reference WAVs, augment, extract features, and fit SVM."""
        if samples_dir is None:
            samples_dir = SAMPLES_DIR

        logger.info(f"Training drum classifier from {samples_dir}")

        X = []  # feature vectors
        y = []  # labels (drum type strings)
        rng = np.random.default_rng(42)

        for filename, drum_type in SAMPLE_TO_TYPE.items():
            wav_path = samples_dir / filename
            if not wav_path.exists():
                logger.warning(f"Sample not found: {wav_path}")
                continue

            audio, sr = librosa.load(str(wav_path), sr=22050, mono=True)

            for _ in range(augmentations_per_class):
                augmented = self._augment(audio, sr, rng)
                features = self.extract_features(augmented, sr, onset_sample=0)
                X.append(features)
                y.append(drum_type)

        X = np.array(X)
        y = np.array(y)

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.svm = SVC(kernel="rbf", probability=True, random_state=42)
        self.svm.fit(X_scaled, y)
        self._trained = True

        logger.info(
            f"Drum classifier trained: {len(X)} samples, "
            f"{len(set(y))} classes, {X.shape[1]} features"
        )

    def _augment(self, y: np.ndarray, sr: int, rng: np.random.Generator) -> np.ndarray:
        """Apply random pitch shift, volume scaling, and noise."""
        augmented = y.copy()

        # Pitch shift ±2.5 semitones
        n_steps = rng.uniform(-2.5, 2.5)
        augmented = librosa.effects.pitch_shift(augmented, sr=sr, n_steps=n_steps)

        # Volume scaling 0.3–2.0x
        gain = rng.uniform(0.3, 2.0)
        augmented = augmented * gain

        # Additive Gaussian noise 0–3%
        noise_level = rng.uniform(0, 0.03)
        if noise_level > 0:
            noise = rng.normal(0, noise_level, len(augmented)).astype(augmented.dtype)
            augmented = augmented + noise

        return augmented

    def extract_features(self, y: np.ndarray, sr: int, onset_sample: int) -> np.ndarray:
        """Extract 29-dimensional feature vector at an onset point.

        Features:
          [0:6]   - 6 frequency band energy ratios
          [6:11]  - spectral centroid, bandwidth, flatness, ZCR, rolloff
          [11:24] - 13 MFCCs (mean)
          [24:28] - 4 temporal decay quartiles
          [28]    - sustain ratio
        """
        # 50ms window for main features
        window_50ms = int(sr * 0.050)
        start = max(0, onset_sample)
        end_50 = min(len(y), start + window_50ms)
        segment = y[start:end_50]

        if len(segment) < 256:
            segment = np.pad(segment, (0, 256 - len(segment)))

        n_fft = min(1024, len(segment))
        S = np.abs(librosa.stft(segment, n_fft=n_fft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # --- 6 frequency band energy ratios ---
        total_energy = np.sum(S**2) + 1e-10
        band_energies = []
        for low_hz, high_hz in FREQ_BANDS:
            if high_hz is None:
                mask = freqs >= low_hz
            else:
                mask = (freqs >= low_hz) & (freqs < high_hz)
            band_energies.append(np.sum(S[mask] ** 2) / total_energy)

        # --- 5 spectral shape features ---
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=segment, sr=sr)))
        bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=segment, sr=sr)))
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=segment)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(segment)))
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=segment, sr=sr)))

        # --- 13 MFCCs ---
        mfccs = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=13)
        mfcc_means = [float(np.mean(m)) for m in mfccs]

        # --- 4 temporal decay quartiles ---
        quarter = len(segment) // 4
        if quarter > 0:
            seg_energy = segment**2
            total_seg = np.sum(seg_energy) + 1e-10
            quartiles = [
                np.sum(seg_energy[i * quarter : (i + 1) * quarter]) / total_seg
                for i in range(4)
            ]
        else:
            quartiles = [0.25, 0.25, 0.25, 0.25]

        # --- Sustain ratio: energy[50-150ms] / energy[0-50ms] ---
        window_150ms = int(sr * 0.150)
        end_150 = min(len(y), start + window_150ms)
        extended = y[start:end_150]

        energy_first = np.sum(segment**2) + 1e-10
        if len(extended) > len(segment):
            tail = extended[len(segment) :]
            energy_tail = np.sum(tail**2)
            sustain_ratio = energy_tail / energy_first
        else:
            sustain_ratio = 0.0

        # Assemble 29-dim vector
        features = (
            band_energies          # 6
            + [centroid, bandwidth, flatness, zcr, rolloff]  # 5
            + mfcc_means           # 13
            + quartiles            # 4
            + [sustain_ratio]      # 1
        )
        return np.array(features, dtype=np.float64)

    def classify(self, features: np.ndarray) -> tuple[str, int, float]:
        """Classify a 29-dim feature vector into a drum type.

        Returns (drum_type, midi_note, confidence).
        """
        if not self._trained:
            raise RuntimeError("Drum classifier not trained. Call train() first.")

        scaled = self.scaler.transform(features.reshape(1, -1))
        proba = self.svm.predict_proba(scaled)[0]
        best_idx = np.argmax(proba)
        drum_type = self.svm.classes_[best_idx]
        confidence = float(proba[best_idx])

        return drum_type, DRUM_MAP[drum_type], confidence


# Module-level singleton
drum_classifier = DrumClassifierModel()
