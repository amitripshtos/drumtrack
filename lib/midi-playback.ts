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
  private _players: Map<string, Tone.Player> = new Map();
  private _noteUrls: Record<number, string[]> = {};
  private roundRobinIndex: Record<number, number> = {};
  private _backingPlayer: Tone.Player | null = null;
  private _midiVolume: Tone.Volume | null = null;
  private _backingVolume: Tone.Volume | null = null;
  private scheduledEvents: number[] = [];
  private _isLoaded = false;
  private _sampleSet = "default";
  private _muted = false;

  get isLoaded(): boolean {
    return this._isLoaded;
  }

  get sampleSet(): string {
    return this._sampleSet;
  }

  /** Expose players map for DAW engine to reuse loaded samples */
  get players(): Map<string, Tone.Player> {
    return this._players;
  }

  /** Expose note URL mapping for DAW engine */
  get noteUrls(): Record<number, string[]> {
    return this._noteUrls;
  }

  /** Expose volume nodes for DAW engine to reroute */
  get midiVolumeNode(): Tone.Volume | null {
    return this._midiVolume;
  }

  get backingVolumeNode(): Tone.Volume | null {
    return this._backingVolume;
  }

  get backingPlayer(): Tone.Player | null {
    return this._backingPlayer;
  }

  /** Mute all output without stopping transport */
  mute(): void {
    this._muted = true;
    if (this._midiVolume) this._midiVolume.mute = true;
    if (this._backingVolume) this._backingVolume.mute = true;
  }

  /** Unmute output */
  unmute(): void {
    this._muted = false;
    if (this._midiVolume) this._midiVolume.mute = false;
    if (this._backingVolume) this._backingVolume.mute = false;
  }

  get isMuted(): boolean {
    return this._muted;
  }

  async init(sampleSet: string = "default"): Promise<void> {
    await Tone.start();
    this._sampleSet = sampleSet;

    // Create independent volume nodes
    this._midiVolume = new Tone.Volume(0).toDestination();
    this._backingVolume = new Tone.Volume(0).toDestination();

    await this.loadSamples(sampleSet);
  }

  private async loadSamples(sampleSet: string): Promise<void> {
    this._isLoaded = false;
    const { noteUrls, allUrls } = await buildDrumSampleUrls(sampleSet);
    this._noteUrls = noteUrls;
    this.roundRobinIndex = {};

    // Dispose old players
    for (const player of this._players.values()) {
      player.dispose();
    }
    this._players.clear();

    // Create a Tone.Player per unique URL
    const loadPromises: Promise<void>[] = [];
    for (const url of allUrls) {
      if (this._players.has(url)) continue;
      const player = new Tone.Player(url).connect(this._midiVolume!);
      this._players.set(url, player);
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
    if (this._backingPlayer) {
      this._backingPlayer.dispose();
    }

    this._backingPlayer = new Tone.Player({
      url,
      onload: () => {},
    }).connect(this._backingVolume!);

    // Wait for the backing track to load
    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (this._backingPlayer?.loaded) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });

    // Sync to transport
    this._backingPlayer.sync().start(0);
  }

  private triggerSample(midiNote: number, time: number, velocity: number): void {
    const urls = this._noteUrls[midiNote];
    if (!urls || urls.length === 0) return;

    // Round-robin through variants
    const idx = this.roundRobinIndex[midiNote] ?? 0;
    const url = urls[idx % urls.length];
    this.roundRobinIndex[midiNote] = idx + 1;

    const player = this._players.get(url);
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
    return this._backingPlayer?.buffer?.duration ?? 0;
  }

  /** Set MIDI drum volume. 0 = unity, -Infinity = mute. Value in dB. */
  setMidiVolume(db: number): void {
    if (this._midiVolume) {
      this._midiVolume.volume.value = db;
    }
  }

  /** Set backing track volume. 0 = unity, -Infinity = mute. Value in dB. */
  setBackingVolume(db: number): void {
    if (this._backingVolume) {
      this._backingVolume.volume.value = db;
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
    for (const player of this._players.values()) {
      player.dispose();
    }
    this._players.clear();
    this._backingPlayer?.dispose();
    this._midiVolume?.dispose();
    this._backingVolume?.dispose();
    this._backingPlayer = null;
    this._midiVolume = null;
    this._backingVolume = null;
    this._isLoaded = false;
  }
}
