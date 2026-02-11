"""DrumSep + peak detection drum classification pipeline.

Uses DrumSep MDX23C to separate drums into 5 stems (kick, snare, toms, hh, cymbals),
then runs simple peak detection on each isolated stem to find onset times and velocities.
"""

import logging
from pathlib import Path

from app.ml.drum_map import DRUM_MAP, DRUM_TYPE_MIN_GAP_MS
from app.models.cluster import ClusterInfo
from app.models.drum_event import DrumEvent
from app.services.drumsep import separate_drums
from app.services.peak_detection import detect_peaks

logger = logging.getLogger(__name__)

# Stem -> (drum_type, midi_note, cluster_id)
STEM_MAPPING = {
    "kick": ("kick", 36, 0),
    "snare": ("snare", 38, 1),
    "toms": ("tom_mid", 47, 2),
    "hh": ("closed_hihat", 42, 3),
    "cymbals": ("crash", 49, 4),
}


def quantize_time(time_sec: float, bpm: float) -> float:
    """Snap time to nearest 16th note grid position."""
    sixteenth_duration = 60.0 / bpm / 4.0
    grid_position = round(time_sec / sixteenth_duration)
    return grid_position * sixteenth_duration


def detect_cluster_and_label(
    drum_audio_path: Path, bpm: float
) -> tuple[list[DrumEvent], list[ClusterInfo]]:
    """Full pipeline: separate drums into stems, detect peaks, build events.

    Returns (events, clusters).
    """
    # Step 1: Separate drum track into 5 stems
    output_dir = drum_audio_path.parent / "stems"
    logger.info(f"Separating drum track into stems -> {output_dir}")
    stem_paths = separate_drums(drum_audio_path, output_dir)

    # Step 2: Detect peaks per stem and build events
    all_events: list[DrumEvent] = []
    clusters: list[ClusterInfo] = []

    for stem_name, (drum_type, midi_note, cluster_id) in STEM_MAPPING.items():
        stem_path = stem_paths.get(stem_name)
        if stem_path is None or not stem_path.exists():
            logger.warning(f"Stem '{stem_name}' not found, skipping")
            continue

        # Detect peaks in this stem
        peaks = detect_peaks(stem_path, bpm, stem_name=stem_name)
        logger.info(f"Stem '{stem_name}': {len(peaks)} peaks detected")

        if not peaks:
            continue

        # Build DrumEvents
        stem_events: list[DrumEvent] = []
        for peak in peaks:
            event = DrumEvent(
                time=peak["time"],
                quantized_time=peak["quantized_time"],
                drum_type=drum_type,
                midi_note=midi_note,
                velocity=peak["velocity"],
                confidence=0.9,  # high confidence since stems are isolated
                cluster_id=cluster_id,
            )
            stem_events.append(event)

        all_events.extend(stem_events)

        # Build ClusterInfo for this stem
        mean_vel = sum(e.velocity for e in stem_events) / len(stem_events)
        times = sorted(e.time for e in stem_events)
        representative_time = times[len(times) // 2]

        clusters.append(
            ClusterInfo(
                id=cluster_id,
                suggested_label=drum_type,
                label=drum_type,
                suggestion_confidence=0.9,
                event_count=len(stem_events),
                mean_velocity=round(mean_vel, 1),
                representative_time=round(representative_time, 3),
            )
        )

    # Deduplicate and sort
    all_events = deduplicate_events(all_events)
    all_events.sort(key=lambda e: e.time)

    # Update cluster stats after dedup
    _recompute_cluster_stats(all_events, clusters)

    clusters.sort(key=lambda c: c.id)
    logger.info(f"Final: {len(all_events)} events in {len(clusters)} clusters")
    return all_events, clusters


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
    for _cid, cluster_events in by_cluster.items():
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


def _recompute_cluster_stats(events: list[DrumEvent], clusters: list[ClusterInfo]) -> None:
    """Update cluster event_count, mean_velocity, representative_time after dedup."""
    event_by_cluster: dict[int, list[DrumEvent]] = {}
    for e in events:
        event_by_cluster.setdefault(e.cluster_id, []).append(e)

    for c in clusters:
        cevents = event_by_cluster.get(c.id, [])
        c.event_count = len(cevents)
        if cevents:
            c.mean_velocity = round(sum(e.velocity for e in cevents) / len(cevents), 1)
            times = sorted(e.time for e in cevents)
            c.representative_time = round(times[len(times) // 2], 3)
        else:
            c.mean_velocity = 0
            c.representative_time = 0.0
