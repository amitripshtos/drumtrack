"""Crash cymbal analysis: accent detection and ride classification.

Classifies cymbal behavior as either "accent crashes" (sparse, on strong
beats with kick) or "riding" (regular pattern, re-labeled as ride cymbal).
"""

import logging

import numpy as np

from app.ml.drum_map import DRUM_MAP
from app.models.drum_event import DrumEvent

logger = logging.getLogger(__name__)

# Inter-onset interval coefficient of variation threshold for riding detection
RIDING_CV_THRESHOLD = 0.35

# Minimum density (events per bar) to consider riding
RIDING_MIN_DENSITY = 4.0

# Accent scoring weights
ACCENT_WEIGHT_VELOCITY = 0.40
ACCENT_WEIGHT_KICK = 0.35
ACCENT_WEIGHT_STRONG_BEAT = 0.25

# Minimum accent score to keep a crash event
ACCENT_MIN_SCORE = 0.60

# After a kept crash, suppress detections for this many beats
SUSTAIN_SUPPRESS_BEATS = 2

# A new crash during suppression must be this much louder to override
SUSTAIN_OVERRIDE_MULT = 1.2

# Velocity threshold for accent scoring (out of 127)
ACCENT_VELOCITY_THRESHOLD = 60

# Kick coincidence window in seconds
KICK_COINCIDENCE_WINDOW = 0.050

# Strong beat tolerance as fraction of beat duration
STRONG_BEAT_TOLERANCE = 0.15


def analyze_crash_events(
    crash_events: list[DrumEvent],
    kick_events: list[DrumEvent],
    bpm: float,
    duration: float,
) -> tuple[list[DrumEvent], bool]:
    """Analyze and filter crash cymbal events.

    Returns:
        Tuple of (filtered_events, is_riding).
        If is_riding=True, events have been re-labeled as ride cymbal.
    """
    if len(crash_events) < 2:
        return crash_events, False

    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4
    num_bars = max(1, int(duration / bar_dur))

    # Compute inter-onset intervals
    times = sorted(e.time for e in crash_events)
    iois = np.diff(times)

    if len(iois) == 0:
        return crash_events, False

    # Classify behavior based on IOI regularity and density
    ioi_cv = np.std(iois) / np.mean(iois) if np.mean(iois) > 0 else float("inf")
    density = len(crash_events) / num_bars

    logger.info(
        f"Crash analysis: {len(crash_events)} events, "
        f"IOI CV={ioi_cv:.3f}, density={density:.1f}/bar"
    )

    if ioi_cv < RIDING_CV_THRESHOLD and density >= RIDING_MIN_DENSITY:
        # Riding pattern detected
        return _process_riding_crash(crash_events, bpm, duration), True
    else:
        # Accent mode
        return _process_accent_crash(crash_events, kick_events, bpm), False


def _process_riding_crash(
    crash_events: list[DrumEvent],
    bpm: float,
    duration: float,
) -> list[DrumEvent]:
    """Re-label regular crash pattern as ride cymbal.

    Applies 8th-note pattern inference similar to hi-hat processing.
    """
    beat_dur = 60.0 / bpm
    eighth_dur = beat_dur / 2
    bar_dur = beat_dur * 4
    num_bars = int(duration / bar_dur)
    slots_per_bar = 8  # 8th-note resolution

    ride_note = DRUM_MAP["ride"]

    logger.info(f"Crash riding detected, re-labeling {len(crash_events)} events as ride")

    if num_bars < 4:
        # Too few bars for pattern inference, just re-label
        return [
            DrumEvent(
                time=e.time,
                quantized_time=e.quantized_time,
                drum_type="ride",
                midi_note=ride_note,
                velocity=e.velocity,
                confidence=e.confidence,
                cluster_id=e.cluster_id,
            )
            for e in crash_events
        ]

    # Build 8th-note grid per bar
    bar_slot_hits: dict[int, dict[int, list[int]]] = {}
    for e in crash_events:
        bar_idx = min(int(e.time / bar_dur), num_bars - 1)
        time_in_bar = e.time - bar_idx * bar_dur
        slot = round(time_in_bar / eighth_dur) % slots_per_bar
        bar_slot_hits.setdefault(bar_idx, {}).setdefault(slot, []).append(e.velocity)

    # Majority vote
    slot_bar_count: dict[int, int] = {}
    for bar_idx in range(num_bars):
        for slot in bar_slot_hits.get(bar_idx, {}):
            slot_bar_count[slot] = slot_bar_count.get(slot, 0) + 1

    dominant_slots = {slot for slot, count in slot_bar_count.items() if count / num_bars >= 0.50}

    all_velocities = [e.velocity for e in crash_events]
    median_velocity = int(np.median(all_velocities))

    corrected: list[DrumEvent] = []
    for bar_idx in range(num_bars):
        bar_start = bar_idx * bar_dur
        bar_data = bar_slot_hits.get(bar_idx, {})

        for slot in range(slots_per_bar):
            slot_time = bar_start + slot * eighth_dur
            if slot_time > duration:
                break

            is_dominant = slot in dominant_slots
            has_detection = slot in bar_data

            if is_dominant:
                vel = int(np.mean(bar_data[slot])) if has_detection else median_velocity
                conf = 0.90 if has_detection else 0.65
                corrected.append(
                    DrumEvent(
                        time=round(slot_time, 4),
                        quantized_time=round(slot_time, 4),
                        drum_type="ride",
                        midi_note=ride_note,
                        velocity=vel,
                        confidence=conf,
                        cluster_id=crash_events[0].cluster_id,
                    )
                )
            elif has_detection:
                vel = int(np.mean(bar_data[slot]))
                if vel > 1.3 * median_velocity:
                    corrected.append(
                        DrumEvent(
                            time=round(slot_time, 4),
                            quantized_time=round(slot_time, 4),
                            drum_type="ride",
                            midi_note=ride_note,
                            velocity=vel,
                            confidence=0.70,
                            cluster_id=crash_events[0].cluster_id,
                        )
                    )

    logger.info(f"Ride pattern: {len(crash_events)} raw → {len(corrected)} corrected")
    return corrected


def _process_accent_crash(
    crash_events: list[DrumEvent],
    kick_events: list[DrumEvent],
    bpm: float,
) -> list[DrumEvent]:
    """Filter crash events to keep only genuine accents.

    Scores each event on velocity, kick coincidence, and strong beat position.
    Applies sustain suppression after kept crashes.
    """
    beat_dur = 60.0 / bpm
    kick_times = sorted(e.time for e in kick_events)

    # Sort crash events by time
    sorted_crashes = sorted(crash_events, key=lambda e: e.time)

    kept: list[DrumEvent] = []
    suppress_until = -1.0

    for e in sorted_crashes:
        # Check if we're in sustain suppression window
        if e.time < suppress_until:
            # Only override if much louder than the crash that started suppression
            if kept and e.velocity > SUSTAIN_OVERRIDE_MULT * kept[-1].velocity:
                pass  # Allow through
            else:
                continue

        # Score this event
        score = 0.0

        # a. Strong attack velocity
        if e.velocity >= ACCENT_VELOCITY_THRESHOLD:
            score += ACCENT_WEIGHT_VELOCITY

        # b. Kick coincidence
        has_kick = _has_nearby_event(e.time, kick_times, KICK_COINCIDENCE_WINDOW)
        if has_kick:
            score += ACCENT_WEIGHT_KICK

        # c. Strong beat position (beat 1 or 3)
        beat_position = (e.time % (beat_dur * 4)) / beat_dur
        tolerance = STRONG_BEAT_TOLERANCE
        on_strong_beat = (
            beat_position < tolerance
            or abs(beat_position - 2) < tolerance
            or abs(beat_position - 4) < tolerance
        )
        if on_strong_beat:
            score += ACCENT_WEIGHT_STRONG_BEAT

        if score >= ACCENT_MIN_SCORE:
            kept.append(
                DrumEvent(
                    time=e.time,
                    quantized_time=e.quantized_time,
                    drum_type=e.drum_type,
                    midi_note=e.midi_note,
                    velocity=e.velocity,
                    confidence=round(min(score, 1.0), 2),
                    cluster_id=e.cluster_id,
                )
            )
            # Start sustain suppression
            suppress_until = e.time + SUSTAIN_SUPPRESS_BEATS * beat_dur

    logger.info(f"Crash accent filter: {len(crash_events)} raw → {len(kept)} kept")
    return kept


def _has_nearby_event(time: float, sorted_times: list[float], window: float) -> bool:
    """Check if any event in sorted_times is within ±window of time."""
    # Binary search for efficiency
    lo, hi = 0, len(sorted_times) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if abs(sorted_times[mid] - time) <= window:
            return True
        if sorted_times[mid] < time:
            lo = mid + 1
        else:
            hi = mid - 1
    return False
