"""Synthetic drum dataset generator.

Renders MIDI drum patterns into synthetic audio stems using a sample kit,
producing a ground-truth-annotated dataset for evaluating drum transcription.
"""

import json
from pathlib import Path

import librosa
import mido
import numpy as np
import soundfile as sf

from app.ml.drum_map import DRUM_MAP

SAMPLE_RATE = 44100

# GM note number → kit.json key
GM_TO_KIT_KEY: dict[int, str] = {
    36: "kick",
    38: "snare",
    42: "hihat-closed",
    46: "hihat-open",
    50: "tom-high",
    47: "tom-mid",
    45: "tom-low",
    49: "crash",
    51: "ride",
}

# kit.json key → drum_type (matches DRUM_MAP keys)
KIT_KEY_TO_DRUM_TYPE: dict[str, str] = {
    "kick": "kick",
    "snare": "snare",
    "hihat-closed": "closed_hihat",
    "hihat-open": "open_hihat",
    "tom-high": "tom_high",
    "tom-mid": "tom_mid",
    "tom-low": "tom_low",
    "crash": "crash",
    "ride": "ride",
}

# kit.json key → stem group (matches DrumSep 5-stem layout)
KIT_KEY_TO_STEM_GROUP: dict[str, str] = {
    "kick": "kick",
    "snare": "snare",
    "hihat-closed": "hh",
    "hihat-open": "hh",
    "tom-high": "toms",
    "tom-mid": "toms",
    "tom-low": "toms",
    "crash": "cymbals",
    "ride": "cymbals",
}

# Which kit keys compose each DrumSep stem
STEM_COMPOSITION: dict[str, list[str]] = {
    "kick": ["kick"],
    "snare": ["snare"],
    "toms": ["tom-high", "tom-mid", "tom-low"],
    "hh": ["hihat-closed", "hihat-open"],
    "cymbals": ["crash", "ride"],
}


def _parse_midi(midi_path: Path) -> tuple[float, list[tuple[float, int, int]]]:
    """Parse MIDI file into (bpm, events).

    Returns:
        bpm: Detected tempo
        events: List of (time_s, gm_note, velocity) sorted by time
    """
    mid = mido.MidiFile(str(midi_path))
    tempo = 500000  # default 120 BPM
    bpm = 120.0
    events: list[tuple[float, int, int]] = []

    for track in mid.tracks:
        current_time_s = 0.0
        for msg in track:
            current_time_s += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
                bpm = mido.tempo2bpm(tempo)
            elif msg.type == "note_on" and msg.velocity > 0 and msg.channel == 9:
                events.append((current_time_s, msg.note, msg.velocity))

    events.sort(key=lambda x: x[0])
    return bpm, events


def _load_kit_samples(kit_json_path: Path) -> dict[str, list[np.ndarray]]:
    """Load all WAV samples from a kit.json into memory.

    Returns:
        Dict mapping kit_key → list of mono float32 arrays at SAMPLE_RATE
    """
    kit_dir = kit_json_path.parent
    with open(kit_json_path) as f:
        kit: dict[str, list[str]] = json.load(f)

    samples: dict[str, list[np.ndarray]] = {}
    for kit_key, filenames in kit.items():
        loaded: list[np.ndarray] = []
        for filename in filenames:
            wav_path = kit_dir / filename
            if wav_path.exists():
                audio = librosa.load(str(wav_path), sr=SAMPLE_RATE, mono=True)[0].astype(np.float32)
                loaded.append(audio)
        if loaded:
            samples[kit_key] = loaded

    return samples


def render_midi_to_dataset(
    midi_path: Path,
    kit_json_path: Path,
    output_dir: Path,
    snr_db: float | None = None,
) -> dict:
    """Render a MIDI file into a synthetic DrumSep-compatible dataset directory.

    Output layout:
        <output_dir>/
            mix.wav              # full mix
            stems/
                kick.wav         # DrumSep-format 5 stems
                snare.wav
                toms.wav
                hh.wav
                cymbals.wav
            ground_truth.json    # list of DrumEvent dicts with stem_group field
            meta.json            # {bpm, duration_s, midi_file, kit_json, snr_db, event_count}

    Args:
        midi_path: Path to source .mid file
        kit_json_path: Path to kit.json
        output_dir: Where to write the dataset
        snr_db: If set, add white noise at this SNR (dB) to each stem

    Returns:
        meta dict written to meta.json
    """
    bpm, midi_events = _parse_midi(midi_path)
    if not midi_events:
        print(f"  Warning: no drum events found in {midi_path.name}")
        return {}

    samples = _load_kit_samples(kit_json_path)

    # Determine buffer length: last event + 2s padding
    total_duration_s = midi_events[-1][0] + 2.0
    total_samples = int(total_duration_s * SAMPLE_RATE)

    # Per-kit-key audio buffers
    kit_buffers: dict[str, np.ndarray] = {
        key: np.zeros(total_samples, dtype=np.float32)
        for key in samples
    }
    rr_counters: dict[str, int] = {key: 0 for key in samples}

    # Ground truth events
    gt_events: list[dict] = []

    for time_s, gm_note, velocity in midi_events:
        kit_key = GM_TO_KIT_KEY.get(gm_note)
        if kit_key is None or kit_key not in samples:
            continue

        # Round-robin sample selection
        sample_list = samples[kit_key]
        idx = rr_counters[kit_key] % len(sample_list)
        sample = sample_list[idx]
        rr_counters[kit_key] += 1

        # Mix with quadratic velocity scaling
        amplitude = (velocity / 127.0) ** 2
        onset = int(round(time_s * SAMPLE_RATE))
        end = min(total_samples, onset + len(sample))
        chunk_len = end - onset
        if chunk_len > 0:
            kit_buffers[kit_key][onset:end] += amplitude * sample[:chunk_len]

        # Ground truth event
        drum_type = KIT_KEY_TO_DRUM_TYPE[kit_key]
        gt_events.append(
            {
                "time": round(time_s, 4),
                "quantized_time": round(time_s, 4),  # MIDI is grid-quantized
                "drum_type": drum_type,
                "midi_note": DRUM_MAP.get(drum_type, gm_note),
                "velocity": velocity,
                "confidence": 1.0,
                "stem_group": KIT_KEY_TO_STEM_GROUP[kit_key],
            }
        )

    # Build 5 DrumSep stems by summing per-kit-key buffers
    stem_buffers: dict[str, np.ndarray] = {}
    for stem_name, kit_keys in STEM_COMPOSITION.items():
        stem = np.zeros(total_samples, dtype=np.float32)
        for key in kit_keys:
            if key in kit_buffers:
                stem += kit_buffers[key]
        stem_buffers[stem_name] = stem

    # Full mix
    mix = np.zeros(total_samples, dtype=np.float32)
    for stem in stem_buffers.values():
        mix += stem

    # Add white noise to stems if SNR requested
    if snr_db is not None:
        signal_rms = float(np.sqrt(np.mean(mix**2)))
        if signal_rms > 0:
            noise_rms = signal_rms / (10.0 ** (snr_db / 20.0))
            rng = np.random.default_rng()
            for stem_name in stem_buffers:
                noise = (noise_rms * rng.standard_normal(total_samples)).astype(np.float32)
                stem_buffers[stem_name] = stem_buffers[stem_name] + noise
            # Recompute mix after adding noise
            mix = np.zeros(total_samples, dtype=np.float32)
            for stem in stem_buffers.values():
                mix += stem

    # Peak-normalize mix to 0.95
    max_val = float(np.max(np.abs(mix)))
    if max_val > 0:
        scale = 0.95 / max_val
        mix = mix * scale
        for stem_name in stem_buffers:
            stem_buffers[stem_name] = stem_buffers[stem_name] * scale

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    stems_dir = output_dir / "stems"
    stems_dir.mkdir(exist_ok=True)

    sf.write(str(output_dir / "mix.wav"), mix, SAMPLE_RATE)
    for stem_name, buf in stem_buffers.items():
        sf.write(str(stems_dir / f"{stem_name}.wav"), buf, SAMPLE_RATE)

    gt_events.sort(key=lambda e: e["time"])
    with open(output_dir / "ground_truth.json", "w") as f:
        json.dump(gt_events, f, indent=2)

    meta = {
        "bpm": round(bpm, 2),
        "duration_s": round(total_duration_s, 3),
        "midi_file": str(midi_path),
        "kit_json": str(kit_json_path),
        "snr_db": snr_db,
        "event_count": len(gt_events),
    }
    with open(output_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return meta
