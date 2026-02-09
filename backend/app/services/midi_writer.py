import logging
from pathlib import Path

import pretty_midi

from app.models.drum_event import DrumEvent

logger = logging.getLogger(__name__)


def write_midi(events: list[DrumEvent], bpm: float, output_path: Path) -> Path:
    """Generate a MIDI file from classified drum events."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)

    # Channel 10 (0-indexed: 9) for drums — program is ignored for drum instruments
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    note_duration = 0.05  # Short duration for percussion hits

    for event in events:
        note = pretty_midi.Note(
            velocity=event.velocity,
            pitch=event.midi_note,
            start=event.quantized_time,
            end=event.quantized_time + note_duration,
        )
        drum_inst.notes.append(note)

    midi.instruments.append(drum_inst)
    midi.write(str(output_path))
    logger.info(f"MIDI written to {output_path} ({len(events)} notes, {bpm} BPM)")
    return output_path
