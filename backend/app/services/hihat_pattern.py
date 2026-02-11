"""Hi-hat pattern inference via majority voting.

Hi-hats are rhythmically predictable — typically straight 8ths, 16ths,
or shuffle patterns. Instead of trusting every raw onset from an imperfect
stem separation, we find the dominant per-bar pattern and use it to fill
gaps and remove noise.
"""

import logging

import numpy as np

from app.models.drum_event import DrumEvent

logger = logging.getLogger(__name__)

# Minimum number of bars required for pattern inference
MIN_BARS_FOR_INFERENCE = 4

# A grid slot is "dominant" if it has a hit in this fraction of bars
DOMINANCE_THRESHOLD = 0.50

# Velocity multiplier threshold for keeping non-dominant detections
NON_DOMINANT_VELOCITY_MULT = 1.3

# Confidence values for pattern-corrected events
CONFIDENCE_DETECTED = 0.95
CONFIDENCE_FILLED = 0.70

# 16 slots per bar (4 beats × 4 sixteenths)
SLOTS_PER_BAR = 16


def _classify_pattern(dominant_slots: set[int]) -> str:
    """Classify the dominant hi-hat pattern type."""
    if len(dominant_slots) <= 4:
        return "sparse"

    even_slots = {0, 2, 4, 6, 8, 10, 12, 14}
    shuffle_slots = {0, 3, 4, 7, 8, 11, 12, 15}

    # Check how well the dominant slots match known patterns
    even_match = len(dominant_slots & even_slots) / max(len(dominant_slots), 1)
    shuffle_match = len(dominant_slots & shuffle_slots) / max(len(dominant_slots), 1)

    if len(dominant_slots) >= 14:
        return "16ths"
    if shuffle_match > 0.8 and even_match < 0.7:
        return "shuffle"
    if even_match > 0.7:
        return "8ths"
    return "mixed"


def infer_hihat_pattern(
    hh_events: list[DrumEvent],
    kick_events: list[DrumEvent],
    snare_events: list[DrumEvent],
    bpm: float,
    duration: float,
) -> list[DrumEvent]:
    """Apply pattern-based correction to raw hi-hat events.

    Algorithm:
    1. Divide song into bars, map onsets to 16th-note grid slots
    2. Majority vote to find dominant pattern
    3. Per bar: keep detected dominant hits, fill missing dominant slots,
       discard non-dominant hits unless they're unusually loud

    Args:
        hh_events: Raw hi-hat DrumEvents from peak detection
        kick_events: Kick events (for anchoring)
        snare_events: Snare events (for anchoring)
        bpm: Song tempo
        duration: Total audio duration in seconds

    Returns:
        Corrected list of hi-hat DrumEvents
    """
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4
    sixteenth_dur = beat_dur / 4
    num_bars = int(duration / bar_dur)

    if num_bars < MIN_BARS_FOR_INFERENCE:
        logger.info(f"Hi-hat: only {num_bars} bars, skipping pattern inference")
        return hh_events

    if not hh_events:
        return hh_events

    # Build a grid: for each bar, which 16th-note slots have hits?
    # Also track velocity per (bar, slot)
    bar_slot_hits: dict[int, dict[int, list[int]]] = {}  # bar -> slot -> [velocities]
    for e in hh_events:
        bar_idx = int(e.time / bar_dur)
        if bar_idx >= num_bars:
            bar_idx = num_bars - 1
        time_in_bar = e.time - bar_idx * bar_dur
        slot = round(time_in_bar / sixteenth_dur) % SLOTS_PER_BAR

        bar_slot_hits.setdefault(bar_idx, {}).setdefault(slot, []).append(e.velocity)

    # Majority vote: count how many bars each slot is active
    slot_bar_count: dict[int, int] = {}
    for bar_idx in range(num_bars):
        bar_data = bar_slot_hits.get(bar_idx, {})
        for slot in bar_data:
            slot_bar_count[slot] = slot_bar_count.get(slot, 0) + 1

    dominant_slots = {
        slot for slot, count in slot_bar_count.items() if count / num_bars >= DOMINANCE_THRESHOLD
    }

    pattern_type = _classify_pattern(dominant_slots)
    logger.info(
        f"Hi-hat pattern: {pattern_type}, {len(dominant_slots)} dominant slots "
        f"out of {SLOTS_PER_BAR}, {num_bars} bars"
    )

    if pattern_type == "sparse":
        logger.info("Hi-hat: sparse pattern, returning raw detections")
        return hh_events

    # Compute median velocity across all hits for gap-filling
    all_velocities = [e.velocity for e in hh_events]
    median_velocity = int(np.median(all_velocities))

    # Build kick/snare time sets for anchoring (quantized to nearest ms)
    kick_times_ms = {int(e.time * 1000) for e in kick_events}
    snare_times_ms = {int(e.time * 1000) for e in snare_events}

    # Template DrumEvent properties from first hh event
    template = hh_events[0]

    corrected: list[DrumEvent] = []

    for bar_idx in range(num_bars):
        bar_start = bar_idx * bar_dur
        bar_data = bar_slot_hits.get(bar_idx, {})

        for slot in range(SLOTS_PER_BAR):
            slot_time = bar_start + slot * sixteenth_dur
            if slot_time > duration:
                break

            is_dominant = slot in dominant_slots
            has_detection = slot in bar_data

            if is_dominant and has_detection:
                # Dominant + detected → keep with high confidence
                vel = int(np.mean(bar_data[slot]))
                corrected.append(
                    DrumEvent(
                        time=round(slot_time, 4),
                        quantized_time=round(slot_time, 4),
                        drum_type=template.drum_type,
                        midi_note=template.midi_note,
                        velocity=vel,
                        confidence=CONFIDENCE_DETECTED,
                        cluster_id=template.cluster_id,
                    )
                )
            elif is_dominant and not has_detection:
                # Dominant + missing → fill gap
                # Boost confidence if kick/snare also hits here
                slot_time_ms = int(slot_time * 1000)
                has_anchor = any(
                    abs(slot_time_ms - t) <= 30 for t in kick_times_ms | snare_times_ms
                )
                conf = CONFIDENCE_FILLED + (0.1 if has_anchor else 0.0)
                corrected.append(
                    DrumEvent(
                        time=round(slot_time, 4),
                        quantized_time=round(slot_time, 4),
                        drum_type=template.drum_type,
                        midi_note=template.midi_note,
                        velocity=median_velocity,
                        confidence=round(min(conf, 1.0), 2),
                        cluster_id=template.cluster_id,
                    )
                )
            elif not is_dominant and has_detection:
                # Non-dominant + detected → keep only if loud enough
                vel = int(np.mean(bar_data[slot]))
                if vel > NON_DOMINANT_VELOCITY_MULT * median_velocity:
                    corrected.append(
                        DrumEvent(
                            time=round(slot_time, 4),
                            quantized_time=round(slot_time, 4),
                            drum_type=template.drum_type,
                            midi_note=template.midi_note,
                            velocity=vel,
                            confidence=0.75,
                            cluster_id=template.cluster_id,
                        )
                    )
            # else: non-dominant + no detection → skip

    logger.info(f"Hi-hat pattern correction: {len(hh_events)} raw → {len(corrected)} corrected")
    return corrected
