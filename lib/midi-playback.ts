import * as Tone from "tone";
import { getSampleKit, getSampleUrl } from "@/lib/api";
import { DrumEvent, SampleKit } from "@/types";

// GM drum note → instrument name mapping
const GM_NOTE_TO_INSTRUMENT: Record<number, string> = {
  36: "kick",
  38: "snare",
  42: "hihat-closed",
  46: "hihat-open",
  45: "tom-low",
  47: "tom-mid",
  50: "tom-high",
  49: "crash",
  51: "ride",
};

/**
 * Build a mapping of MIDI note → array of sample URLs using the kit manifest.
 * Returns both the URL map and a flat list of all URLs (for preloading).
 */
export async function buildDrumSampleUrls(
  sampleSet: string,
): Promise<{ noteUrls: Record<number, string[]>; allUrls: string[] }> {
  const kit: SampleKit = await getSampleKit(sampleSet);
  const noteUrls: Record<number, string[]> = {};
  const allUrls: string[] = [];

  for (const [note, instrument] of Object.entries(GM_NOTE_TO_INSTRUMENT)) {
    const files = kit[instrument];
    if (!files) continue;
    const urls = files.map((f) => getSampleUrl(sampleSet, f));
    noteUrls[Number(note)] = urls;
    allUrls.push(...urls);
  }

  return { noteUrls, allUrls };
}

export class MidiPlaybackEngine {
  private players: Map<string, Tone.Player> = new Map();
  private noteUrls: Record<number, string[]> = {};
  private roundRobinIndex: Record<number, number> = {};
  private backingPlayer: Tone.Player | null = null;
  private midiVolume: Tone.Volume | null = null;
  private backingVolume: Tone.Volume | null = null;
  private scheduledEvents: number[] = [];
  private _isLoaded = false;
  private _sampleSet = "default";

  get isLoaded(): boolean {
    return this._isLoaded;
  }

  get sampleSet(): string {
    return this._sampleSet;
  }

  async init(sampleSet: string = "default"): Promise<void> {
    await Tone.start();
    this._sampleSet = sampleSet;

    // Create independent volume nodes
    this.midiVolume = new Tone.Volume(0).toDestination();
    this.backingVolume = new Tone.Volume(0).toDestination();

    await this.loadSamples(sampleSet);
  }

  private async loadSamples(sampleSet: string): Promise<void> {
    this._isLoaded = false;
    const { noteUrls, allUrls } = await buildDrumSampleUrls(sampleSet);
    this.noteUrls = noteUrls;
    this.roundRobinIndex = {};

    // Dispose old players
    for (const player of this.players.values()) {
      player.dispose();
    }
    this.players.clear();

    // Create a Tone.Player per unique URL
    const loadPromises: Promise<void>[] = [];
    for (const url of allUrls) {
      if (this.players.has(url)) continue;
      const player = new Tone.Player(url).connect(this.midiVolume!);
      this.players.set(url, player);
      loadPromises.push(
        new Promise<void>((resolve) => {
          const check = setInterval(() => {
            if (player.loaded) {
              clearInterval(check);
              resolve();
            }
          }, 100);
        }),
      );
    }

    await Promise.all(loadPromises);
    this._isLoaded = true;
  }

  async changeSamples(sampleSet: string): Promise<void> {
    this._sampleSet = sampleSet;
    await this.loadSamples(sampleSet);
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

  private triggerSample(midiNote: number, time: number, velocity: number): void {
    const urls = this.noteUrls[midiNote];
    if (!urls || urls.length === 0) return;

    // Round-robin through variants
    const idx = this.roundRobinIndex[midiNote] ?? 0;
    const url = urls[idx % urls.length];
    this.roundRobinIndex[midiNote] = idx + 1;

    const player = this.players.get(url);
    if (!player) return;

    // Start from beginning with given volume
    player.volume.value = Tone.gainToDb(velocity);
    player.start(time);
  }

  scheduleEvents(events: DrumEvent[], bpm: number): void {
    this.clearScheduled();
    Tone.getTransport().bpm.value = bpm;

    for (const event of events) {
      const id = Tone.getTransport().schedule((time) => {
        this.triggerSample(event.midi_note, time, event.velocity / 127);
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
    for (const player of this.players.values()) {
      player.dispose();
    }
    this.players.clear();
    this.backingPlayer?.dispose();
    this.midiVolume?.dispose();
    this.backingVolume?.dispose();
    this.backingPlayer = null;
    this.midiVolume = null;
    this.backingVolume = null;
    this._isLoaded = false;
  }
}
