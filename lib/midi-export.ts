import { Midi } from "@tonejs/midi";
import type { DrumEvent } from "@/types";

/**
 * Export a subset of DrumEvents as a Standard MIDI File (type 0).
 * All events are written to channel 10 (GM drums).
 */
export function exportEventsAsMidi(events: DrumEvent[], bpm: number): Blob {
  const midi = new Midi();
  midi.header.setTempo(bpm);

  const track = midi.addTrack();
  track.channel = 9; // GM drum channel (0-indexed)

  for (const event of events) {
    track.addNote({
      midi: event.midi_note,
      time: event.quantized_time,
      velocity: event.velocity / 127,
      duration: 0.05,
    });
  }

  const arr = midi.toArray();
  return new Blob([arr.buffer as ArrayBuffer], { type: "audio/midi" });
}
