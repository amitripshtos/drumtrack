"""Built-in MIDI drum pattern generator.

Generates 7 standard 4/4 patterns as .mid files using mido.
No external data needed — all patterns are defined inline.
"""

from pathlib import Path

import mido

# Ticks per beat (quarter note)
TICKS_PER_BEAT = 480

# Tick durations
QUARTER = TICKS_PER_BEAT          # 480 ticks
EIGHTH = TICKS_PER_BEAT // 2      # 240 ticks
SIXTEENTH = TICKS_PER_BEAT // 4   # 120 ticks
BAR = TICKS_PER_BEAT * 4          # 1920 ticks

# GM drum note numbers (channel 10 = channel index 9)
KICK = 36
SNARE = 38
CLOSED_HH = 42
OPEN_HH = 46
TOM_HIGH = 50
TOM_MID = 47
TOM_LOW = 45
CRASH = 49
RIDE = 51


def _build_midi(events_per_bar: list[tuple[int, int, int]], bpm: float, bars: int = 8) -> mido.MidiFile:
    """Build a type-0 MIDI file from per-bar events.

    Args:
        events_per_bar: List of (tick_in_bar, note, velocity) tuples (one bar pattern)
        bpm: Tempo in beats per minute
        bars: Number of bars to repeat

    Returns:
        mido.MidiFile ready to save
    """
    mid = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    tempo = mido.bpm2tempo(bpm)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    # Build flat list of (abs_tick, sort_key, type, note, velocity)
    # type 0 = note_on, type 1 = note_off  (sorted so note_on comes first at equal ticks)
    messages: list[tuple[int, int, int, int, int]] = []
    for bar in range(bars):
        bar_start = bar * BAR
        for tick_in_bar, note, velocity in events_per_bar:
            abs_tick = bar_start + tick_in_bar
            messages.append((abs_tick, 0, note, velocity, 0))        # note_on
            messages.append((abs_tick + 10, 1, note, 0, 1))           # note_off

    messages.sort(key=lambda x: (x[0], x[4]))  # sort by abs_tick, then type

    current_tick = 0
    for abs_tick, _type, note, velocity, msg_type in messages:
        delta = abs_tick - current_tick
        if msg_type == 0:
            track.append(mido.Message("note_on", channel=9, note=note, velocity=velocity, time=delta))
        else:
            track.append(mido.Message("note_off", channel=9, note=note, velocity=0, time=delta))
        current_tick = abs_tick

    track.append(mido.MetaMessage("end_of_track", time=1))
    return mid


def generate_simple_patterns(output_dir: Path, bpm: float = 120.0) -> list[Path]:
    """Generate 7 standard 4/4 drum patterns as MIDI files.

    Args:
        output_dir: Directory to write .mid files to
        bpm: Tempo for all patterns

    Returns:
        List of created .mid file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    patterns: dict[str, list[tuple[int, int, int]]] = {
        # Rock beat: kick 1&3, snare 2&4, 8th-note HH
        "rock_beat": [
            (0, CLOSED_HH, 80), (EIGHTH, CLOSED_HH, 70),
            (QUARTER, CLOSED_HH, 80), (QUARTER + EIGHTH, CLOSED_HH, 70),
            (QUARTER * 2, CLOSED_HH, 80), (QUARTER * 2 + EIGHTH, CLOSED_HH, 70),
            (QUARTER * 3, CLOSED_HH, 80), (QUARTER * 3 + EIGHTH, CLOSED_HH, 70),
            (0, KICK, 100), (QUARTER * 2, KICK, 95),
            (QUARTER, SNARE, 90), (QUARTER * 3, SNARE, 85),
        ],

        # Rock beat with 16th-note HH
        "rock_beat_16ths": (
            [(SIXTEENTH * i, CLOSED_HH, 75 if i % 2 == 0 else 55) for i in range(16)]
            + [
                (0, KICK, 100), (QUARTER * 2, KICK, 95),
                (QUARTER, SNARE, 90), (QUARTER * 3, SNARE, 85),
            ]
        ),

        # Four-on-the-floor kick with crash on beat 1
        "kick_heavy": [
            (0, KICK, 110), (QUARTER, KICK, 100),
            (QUARTER * 2, KICK, 105), (QUARTER * 3, KICK, 100),
            (0, CRASH, 100),
            (EIGHTH, CLOSED_HH, 70), (QUARTER + EIGHTH, CLOSED_HH, 70),
            (QUARTER * 2 + EIGHTH, CLOSED_HH, 70), (QUARTER * 3 + EIGHTH, CLOSED_HH, 70),
        ],

        # Half-time feel: snare only on beat 3
        "half_time": [
            (0, CLOSED_HH, 80), (QUARTER, CLOSED_HH, 70),
            (QUARTER * 2, CLOSED_HH, 80), (QUARTER * 3, CLOSED_HH, 70),
            (0, KICK, 100),
            (QUARTER * 2, SNARE, 95),
        ],

        # Descending tom fill across one bar
        "tom_fill": [
            (0, TOM_HIGH, 90), (SIXTEENTH, TOM_HIGH, 80),
            (QUARTER, TOM_HIGH, 85), (QUARTER + SIXTEENTH, TOM_HIGH, 75),
            (QUARTER * 2, TOM_MID, 90), (QUARTER * 2 + SIXTEENTH, TOM_MID, 80),
            (QUARTER * 3, TOM_LOW, 95), (QUARTER * 3 + SIXTEENTH, TOM_LOW, 85),
            (QUARTER * 3 + EIGHTH + SIXTEENTH, SNARE, 100),
        ],

        # Open HH on the "and" of beat 2
        "open_hihat": [
            (0, CLOSED_HH, 80), (QUARTER, CLOSED_HH, 75),
            (QUARTER + EIGHTH, OPEN_HH, 85),
            (QUARTER * 2, CLOSED_HH, 80), (QUARTER * 3, CLOSED_HH, 75),
            (0, KICK, 100), (QUARTER * 2, KICK, 95),
            (QUARTER, SNARE, 90), (QUARTER * 3, SNARE, 85),
        ],

        # Ride cymbal groove instead of HH
        "ride_groove": [
            (0, RIDE, 75), (EIGHTH, RIDE, 65),
            (QUARTER, RIDE, 75), (QUARTER + EIGHTH, RIDE, 65),
            (QUARTER * 2, RIDE, 75), (QUARTER * 2 + EIGHTH, RIDE, 65),
            (QUARTER * 3, RIDE, 75), (QUARTER * 3 + EIGHTH, RIDE, 65),
            (0, KICK, 100), (QUARTER * 2, KICK, 95),
            (QUARTER, SNARE, 90), (QUARTER * 3, SNARE, 85),
        ],
    }

    created: list[Path] = []
    for name, events in patterns.items():
        mid = _build_midi(events, bpm=bpm, bars=8)
        out_path = output_dir / f"{name}.mid"
        mid.save(str(out_path))
        created.append(out_path)
        print(f"  Created {out_path.name} ({len(events)} events/bar × 8 bars)")

    return created
