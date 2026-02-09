import * as Tone from "tone";
import { DrumEvent } from "@/types";

// GM drum note to sample file mapping
const DRUM_SAMPLES: Record<number, string> = {
  36: "/samples/kick.wav",
  38: "/samples/snare.wav",
  42: "/samples/hihat-closed.wav",
  46: "/samples/hihat-open.wav",
  45: "/samples/tom-low.wav",
  47: "/samples/tom-mid.wav",
  50: "/samples/tom-high.wav",
  49: "/samples/crash.wav",
  51: "/samples/ride.wav",
};

export class MidiPlaybackEngine {
  private sampler: Tone.Sampler | null = null;
  private backingPlayer: Tone.Player | null = null;
  private midiVolume: Tone.Volume | null = null;
  private backingVolume: Tone.Volume | null = null;
  private scheduledEvents: number[] = [];
  private _isLoaded = false;

  get isLoaded(): boolean {
    return this._isLoaded;
  }

  async init(): Promise<void> {
    await Tone.start();

    // Create independent volume nodes
    this.midiVolume = new Tone.Volume(0).toDestination();
    this.backingVolume = new Tone.Volume(0).toDestination();

    // Build note-to-url map for Sampler
    const urls: Record<string, string> = {};
    for (const [note, url] of Object.entries(DRUM_SAMPLES)) {
      // Tone.Sampler wants note names, we'll use MIDI note numbers via fromMidi
      const noteName = Tone.Frequency(Number(note), "midi").toNote();
      urls[noteName] = url;
    }

    this.sampler = new Tone.Sampler({
      urls,
      baseUrl: "",
      onload: () => {
        this._isLoaded = true;
      },
    }).connect(this.midiVolume);

    // Wait for samples to load
    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (this._isLoaded) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });
  }

  async loadBackingTrack(url: string): Promise<void> {
    if (this.backingPlayer) {
      this.backingPlayer.dispose();
    }

    this.backingPlayer = new Tone.Player({
      url,
      onload: () => {},
    }).connect(this.backingVolume!);

    // Wait for the backing track to load
    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (this.backingPlayer?.loaded) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });

    // Sync to transport
    this.backingPlayer.sync().start(0);
  }

  scheduleEvents(events: DrumEvent[], bpm: number): void {
    this.clearScheduled();
    Tone.getTransport().bpm.value = bpm;

    for (const event of events) {
      const id = Tone.getTransport().schedule((time) => {
        if (this.sampler) {
          const noteName = Tone.Frequency(event.midi_note, "midi").toNote();
          const velocity = event.velocity / 127;
          this.sampler.triggerAttackRelease(noteName, "4n", time, velocity);
        }
      }, event.quantized_time);
      this.scheduledEvents.push(id);
    }
  }

  play(): void {
    Tone.getTransport().start();
  }

  pause(): void {
    Tone.getTransport().pause();
  }

  stop(): void {
    Tone.getTransport().stop();
  }

  seek(seconds: number): void {
    Tone.getTransport().seconds = seconds;
  }

  get currentTime(): number {
    return Tone.getTransport().seconds;
  }

  get isPlaying(): boolean {
    return Tone.getTransport().state === "started";
  }

  get duration(): number {
    return this.backingPlayer?.buffer?.duration ?? 0;
  }

  /** Set MIDI drum volume. 0 = unity, -Infinity = mute. Value in dB. */
  setMidiVolume(db: number): void {
    if (this.midiVolume) {
      this.midiVolume.volume.value = db;
    }
  }

  /** Set backing track volume. 0 = unity, -Infinity = mute. Value in dB. */
  setBackingVolume(db: number): void {
    if (this.backingVolume) {
      this.backingVolume.volume.value = db;
    }
  }

  private clearScheduled(): void {
    for (const id of this.scheduledEvents) {
      Tone.getTransport().clear(id);
    }
    this.scheduledEvents = [];
  }

  dispose(): void {
    this.clearScheduled();
    Tone.getTransport().stop();
    Tone.getTransport().cancel();
    this.sampler?.dispose();
    this.backingPlayer?.dispose();
    this.midiVolume?.dispose();
    this.backingVolume?.dispose();
    this.sampler = null;
    this.backingPlayer = null;
    this.midiVolume = null;
    this.backingVolume = null;
    this._isLoaded = false;
  }
}
