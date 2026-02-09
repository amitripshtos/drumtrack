"""Cluster-then-label drum classification pipeline.

Replaces the SVM per-onset classifier with:
1. Aggressive onset detection (low wait threshold)
2. Feature extraction (reuses DrumClassifierModel.extract_features)
3. K-means clustering of similar-sounding onsets
4. Spectral heuristic auto-labeling per cluster
5. Per-type deduplication
"""

import logging
from pathlib import Path

import librosa
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.ml.classifier import estimate_velocity
from app.ml.drum_classifier_model import DrumClassifierModel
from app.ml.drum_map import DRUM_MAP, DRUM_TYPE_MIN_GAP_MS
from app.ml.feature_extractor import extract_rms_at_onset
from app.models.cluster import ClusterInfo
from app.models.drum_event import DrumEvent

logger = logging.getLogger(__name__)

# Feature indices from DrumClassifierModel.extract_features (29-dim):
#  [0:6]   - 6 freq band energy ratios: sub_bass, bass, mid, hi_mid, high, air
#  [6:11]  - centroid, bandwidth, flatness, zcr, rolloff
#  [11:24] - 13 MFCCs
#  [24:28] - 4 temporal decay quartiles
#  [28]    - sustain ratio
IDX_SUB_BASS = 0
IDX_BASS = 1
IDX_MID = 2
IDX_HI_MID = 3
IDX_HIGH = 4
IDX_CENTROID = 6
IDX_FLATNESS = 8
IDX_SUSTAIN = 28


def quantize_time(time_sec: float, bpm: float) -> float:
    """Snap time to nearest 16th note grid position."""
    sixteenth_duration = 60.0 / bpm / 4.0
    grid_position = round(time_sec / sixteenth_duration)
    return grid_position * sixteenth_duration


def detect_cluster_and_label(
    drum_audio_path: Path, bpm: float
) -> tuple[list[DrumEvent], list[ClusterInfo]]:
    """Full clustering pipeline: detect onsets, cluster, auto-label, dedup, quantize.

    Returns (events, clusters).
    """
    logger.info(f"Loading drum audio from {drum_audio_path}")
    y, sr = librosa.load(str(drum_audio_path), sr=22050, mono=True)

    # --- Onset detection with aggressive params ---
    logger.info("Detecting onsets (aggressive params for fast passages)...")
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
        delta=0.06,
        wait=1,
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    onset_samples = librosa.frames_to_samples(onset_frames, hop_length=512)
    logger.info(f"Found {len(onset_frames)} raw onsets")

    if len(onset_frames) == 0:
        return [], []

    # --- Extract features for all onsets ---
    extractor = DrumClassifierModel()
    features_list = []
    rms_list = []
    for sample in onset_samples:
        features = extractor.extract_features(y, sr, int(sample))
        features_list.append(features)
        rms_list.append(extract_rms_at_onset(y, sr, int(sample)))

    features_matrix = np.array(features_list)

    # --- Cluster ---
    labels, k = cluster_onsets(features_matrix)
    logger.info(f"Clustered into {k} groups")

    # --- Auto-label ---
    clusters = auto_label_clusters(features_matrix, labels)

    # Build label lookup: cluster_id -> drum_type
    label_map = {c.id: c.label for c in clusters}

    # --- Build events ---
    events: list[DrumEvent] = []
    for i, (time_sec, sample) in enumerate(zip(onset_times, onset_samples)):
        cid = int(labels[i])
        drum_type = label_map[cid]
        midi_note = DRUM_MAP[drum_type]
        velocity = estimate_velocity(rms_list[i])
        quantized = quantize_time(time_sec, bpm)

        events.append(
            DrumEvent(
                time=round(float(time_sec), 4),
                quantized_time=round(quantized, 4),
                drum_type=drum_type,
                midi_note=midi_note,
                velocity=velocity,
                confidence=round(clusters[cid].suggestion_confidence, 3)
                if cid < len(clusters)
                else 0.5,
                cluster_id=cid,
            )
        )

    # --- Deduplicate ---
    events = deduplicate_events(events)

    # --- Update cluster stats after dedup ---
    clusters = _recompute_cluster_stats(events, clusters, features_matrix, labels)

    logger.info(f"Final: {len(events)} events in {k} clusters")
    return events, clusters


def cluster_onsets(features_matrix: np.ndarray) -> tuple[np.ndarray, int]:
    """Cluster onset feature vectors using K-means.

    Returns (labels, k).
    """
    n = len(features_matrix)

    if n < 3:
        return np.zeros(n, dtype=int), 1

    # Standardize features
    scaler = StandardScaler()
    X = scaler.fit_transform(features_matrix)

    # PCA dimensionality reduction for large onset sets
    if n > 50:
        n_components = min(15, X.shape[1])
        pca = PCA(n_components=n_components)
        X = pca.fit_transform(X)

    # Try k from 2 to min(8, n//3), pick best silhouette
    k_min = 2
    k_max = min(8, max(2, n // 3))

    if k_max <= k_min:
        km = KMeans(n_clusters=2, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        return labels, 2

    best_k = 3
    best_score = -1.0
    best_labels = None

    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        trial_labels = km.fit_predict(X)
        score = silhouette_score(X, trial_labels)
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = trial_labels

    # If all silhouettes are very low, default to k=3
    if best_score < 0.15:
        km = KMeans(n_clusters=3, random_state=42, n_init=10)
        best_labels = km.fit_predict(X)
        best_k = 3

    return best_labels, best_k


def auto_label_clusters(
    features_matrix: np.ndarray, labels: np.ndarray
) -> list[ClusterInfo]:
    """Assign drum type labels to clusters based on spectral heuristics.

    Returns a ClusterInfo per unique cluster id, sorted by id.
    """
    unique_ids = sorted(set(labels))
    clusters: list[ClusterInfo] = []

    # Compute per-cluster mean features
    cluster_means = {}
    for cid in unique_ids:
        mask = labels == cid
        cluster_means[cid] = features_matrix[mask].mean(axis=0)

    # Track assigned labels to avoid duplicate toms
    assigned_labels: set[str] = set()
    tom_candidates: list[tuple[int, np.ndarray]] = []

    for cid in unique_ids:
        mean = cluster_means[cid]
        sub_bass = mean[IDX_SUB_BASS]
        bass = mean[IDX_BASS]
        mid = mean[IDX_MID]
        hi_mid = mean[IDX_HI_MID]
        high = mean[IDX_HIGH]
        centroid = mean[IDX_CENTROID]
        flatness = mean[IDX_FLATNESS]
        sustain = mean[IDX_SUSTAIN]

        label = None
        confidence = 0.5

        # Priority 1: Kick
        if sub_bass + bass > 0.65 and centroid < 1500:
            label = "kick"
            confidence = min(0.95, (sub_bass + bass) * 1.2)
        # Priority 2: Crash
        elif hi_mid + high > 0.45 and flatness > 0.20 and sustain > 0.6:
            label = "crash"
            confidence = min(0.9, flatness * 3)
        # Priority 3: Ride
        elif hi_mid + high > 0.40 and flatness > 0.15 and sustain > 0.5:
            label = "ride"
            confidence = min(0.85, flatness * 3)
        # Priority 4: Closed hi-hat
        elif hi_mid + high > 0.35 and sustain < 0.4:
            label = "closed_hihat"
            confidence = min(0.85, (hi_mid + high) * 1.1)
        # Priority 5: Open hi-hat
        elif hi_mid + high > 0.35 and sustain >= 0.4:
            label = "open_hihat"
            confidence = min(0.8, sustain * 1.0)
        # Priority 6: Snare
        elif mid + hi_mid > 0.45 and flatness > 0.08 and centroid > 2000:
            label = "snare"
            confidence = min(0.8, (mid + hi_mid) * 1.0)
        else:
            # Could be a tom or unknown — collect for tom sorting
            tom_candidates.append((cid, mean))

        if label is not None:
            assigned_labels.add(label)
            clusters.append(
                ClusterInfo(
                    id=cid,
                    suggested_label=label,
                    label=label,
                    suggestion_confidence=round(confidence, 3),
                    event_count=int(np.sum(labels == cid)),
                    mean_velocity=0,
                    representative_time=0.0,
                )
            )

    # Assign toms by sorting remaining clusters by centroid
    if tom_candidates:
        tom_candidates.sort(key=lambda x: x[1][IDX_CENTROID])
        tom_types = ["tom_low", "tom_mid", "tom_high"]
        for idx, (cid, mean) in enumerate(tom_candidates):
            if idx < len(tom_types):
                label = tom_types[idx]
            else:
                label = "closed_hihat"  # fallback
            clusters.append(
                ClusterInfo(
                    id=cid,
                    suggested_label=label,
                    label=label,
                    suggestion_confidence=0.4,
                    event_count=int(np.sum(labels == cid)),
                    mean_velocity=0,
                    representative_time=0.0,
                )
            )

    # Sort by cluster id
    clusters.sort(key=lambda c: c.id)
    return clusters


def deduplicate_events(events: list[DrumEvent]) -> list[DrumEvent]:
    """Remove duplicate onsets per cluster using type-specific minimum gaps.

    Within each cluster, events closer than the type's min gap are merged,
    keeping the higher-velocity event.
    """
    if not events:
        return events

    # Group by cluster_id
    by_cluster: dict[int, list[DrumEvent]] = {}
    for e in events:
        by_cluster.setdefault(e.cluster_id, []).append(e)

    kept: list[DrumEvent] = []
    for cid, cluster_events in by_cluster.items():
        cluster_events.sort(key=lambda e: e.time)
        drum_type = cluster_events[0].drum_type
        min_gap_s = DRUM_TYPE_MIN_GAP_MS.get(drum_type, 40) / 1000.0

        last_kept = cluster_events[0]
        result = [last_kept]

        for e in cluster_events[1:]:
            gap = e.time - last_kept.time
            if gap >= min_gap_s:
                result.append(e)
                last_kept = e
            else:
                # Merge: keep the higher-velocity event
                if e.velocity > last_kept.velocity:
                    result[-1] = e
                    last_kept = e

        kept.extend(result)

    # Sort all events by time
    kept.sort(key=lambda e: e.time)
    return kept


def relabel_and_regenerate(
    events: list[DrumEvent],
    clusters: list[ClusterInfo],
    cluster_labels: dict[str, str],
    bpm: float,
) -> tuple[list[DrumEvent], list[ClusterInfo]]:
    """Re-label clusters and regenerate events with new drum types.

    Called when user updates cluster labels via the API.
    """
    # Update cluster labels
    label_map: dict[int, str] = {}
    for c in clusters:
        new_label = cluster_labels.get(str(c.id))
        if new_label and new_label in DRUM_MAP:
            c.label = new_label
        label_map[c.id] = c.label

    # Update events with new types
    for e in events:
        new_type = label_map.get(e.cluster_id, e.drum_type)
        e.drum_type = new_type
        e.midi_note = DRUM_MAP.get(new_type, e.midi_note)

    # Re-deduplicate with new type-specific gaps
    events = deduplicate_events(events)

    # Re-quantize
    for e in events:
        e.quantized_time = round(quantize_time(e.time, bpm), 4)

    return events, clusters


def _recompute_cluster_stats(
    events: list[DrumEvent],
    clusters: list[ClusterInfo],
    features_matrix: np.ndarray,
    original_labels: np.ndarray,
) -> list[ClusterInfo]:
    """Update cluster event_count, mean_velocity, representative_time after dedup."""
    # Build stats from remaining events
    event_by_cluster: dict[int, list[DrumEvent]] = {}
    for e in events:
        event_by_cluster.setdefault(e.cluster_id, []).append(e)

    for c in clusters:
        cevents = event_by_cluster.get(c.id, [])
        c.event_count = len(cevents)
        if cevents:
            c.mean_velocity = round(
                sum(e.velocity for e in cevents) / len(cevents), 1
            )
            # Representative time: median event time
            times = sorted(e.time for e in cevents)
            c.representative_time = round(times[len(times) // 2], 3)
        else:
            c.mean_velocity = 0
            c.representative_time = 0.0

    return clusters
