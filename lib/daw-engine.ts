import * as Tone from "tone";
import { STEM_MIDI_NOTES, STEM_NAMES } from "@/lib/channel-colors";
import type { MidiPlaybackEngine } from "@/lib/midi-playback";
import { buildDrumSampleUrls } from "@/lib/midi-playback";
import type { DrumEvent } from "@/types";

export interface DawChannel {
  id: string;
  name: string;
  type: "drum-stem" | "backing";
  volumeNode: Tone.Volume;
  midiNotes: number[];
  volume: number;
  muted: boolean;
  solo: boolean;
}

/**
 * Per-stem set of Tone.Players, each pre-connected to the stem's volume node.
 * This avoids disconnect/reconnect per trigger which corrupts player state.
 */
interface StemPlayers {
  /** URL → Tone.Player, all connected to this stem's volumeNode */
  players: Map<string, Tone.Player>;
}

export class DawMixerEngine {
  private baseEngine: MidiPlaybackEngine;
  private channels: Map<string, DawChannel> = new Map();
  private stemPlayers: Map<string, StemPlayers> = new Map();
  private metronomesynth: Tone.Synth | null = null;
  private metronomeVolume: Tone.Volume | null = null;
  private metronomePart: Tone.Loop | null = null;
  private _metronomeEnabled = false;
  private scheduledEvents: number[] = [];
  private _active = false;

  constructor(baseEngine: MidiPlaybackEngine) {
    this.baseEngine = baseEngine;
  }

  get isActive(): boolean {
    return this._active;
  }

  get metronomeEnabled(): boolean {
    return this._metronomeEnabled;
  }

  async activate(events: DrumEvent[], _backingUrl: string): Promise<void> {
    if (this._active) return;
    this._active = true;

    // Mute the base engine's 2-bus routing
    this.baseEngine.mute();

    // Create per-stem volume nodes
    for (const stem of STEM_NAMES) {
      const volumeNode = new Tone.Volume(0).toDestination();
      this.channels.set(stem, {
        id: stem,
        name: stem,
        type: "drum-stem",
        volumeNode,
        midiNotes: STEM_MIDI_NOTES[stem],
        volume: 0,
        muted: false,
        solo: false,
      });
    }

    // Create backing channel
    const backingVolumeNode = new Tone.Volume(0).toDestination();
    this.channels.set("backing", {
      id: "backing",
      name: "backing",
      type: "backing",
      volumeNode: backingVolumeNode,
      midiNotes: [],
      volume: 0,
      muted: false,
      solo: false,
    });

    // Connect backing player to its DAW channel
    const bp = this.baseEngine.backingPlayer;
    if (bp) {
      bp.disconnect();
      bp.connect(backingVolumeNode);
    }

    // Create per-stem player clones from base engine's loaded buffers
    this.buildStemPlayers();

    // Schedule drum events through per-stem players
    this.scheduleDawEvents(events);

    // Set up metronome
    this.metronomeVolume = new Tone.Volume(-6).toDestination();
    this.metronomesynth = new Tone.Synth({
      oscillator: { type: "triangle" },
      envelope: { attack: 0.001, decay: 0.1, sustain: 0, release: 0.05 },
    }).connect(this.metronomeVolume);

    this.metronomeVolume.mute = !this._metronomeEnabled;
  }

  /**
   * Create dedicated Tone.Player clones per stem, each pre-connected
   * to the stem's volume node. Uses the same loaded buffers from the
   * base engine but as independent player instances.
   */
  private buildStemPlayers(): void {
    // Dispose any existing stem players
    for (const sp of this.stemPlayers.values()) {
      for (const p of sp.players.values()) p.dispose();
    }
    this.stemPlayers.clear();

    const noteUrls = this.baseEngine.noteUrls;
    const basePlayers = this.baseEngine.players;

    for (const stem of STEM_NAMES) {
      const channel = this.channels.get(stem);
      if (!channel) continue;

      const players = new Map<string, Tone.Player>();
      const notes = STEM_MIDI_NOTES[stem];

      for (const note of notes) {
        const urls = noteUrls[note];
        if (!urls) continue;
        for (const url of urls) {
          if (players.has(url)) continue;
          const basePlayer = basePlayers.get(url);
          if (!basePlayer?.loaded) continue;

          // Create a new player sharing the same buffer, connected to stem volume
          const clone = new Tone.Player(basePlayer.buffer).connect(channel.volumeNode);
          players.set(url, clone);
        }
      }

      this.stemPlayers.set(stem, { players });
    }
  }

  private scheduleDawEvents(events: DrumEvent[]): void {
    for (const id of this.scheduledEvents) {
      Tone.getTransport().clear(id);
    }
    this.scheduledEvents = [];

    const roundRobinIndex: Record<number, number> = {};

    // Build midi_note → stem mapping
    const noteToStem: Record<number, string> = {};
    for (const [stem, notes] of Object.entries(STEM_MIDI_NOTES)) {
      for (const note of notes) {
        noteToStem[note] = stem;
      }
    }

    for (const event of events) {
      const id = Tone.getTransport().schedule((time) => {
        const stemId = noteToStem[event.midi_note];
        if (!stemId) return;

        // Look up URLs from base engine at trigger time (handles sample kit changes)
        const urls = this.baseEngine.noteUrls[event.midi_note];
        if (!urls || urls.length === 0) return;

        const idx = roundRobinIndex[event.midi_note] ?? 0;
        const url = urls[idx % urls.length];
        roundRobinIndex[event.midi_note] = idx + 1;

        // Use the stem's dedicated player (not the shared base engine player)
        const sp = this.stemPlayers.get(stemId);
        const player = sp?.players.get(url);
        if (!player) return;

        player.volume.value = Tone.gainToDb(event.velocity / 127);
        player.start(time);
      }, event.quantized_time);
      this.scheduledEvents.push(id);
    }
  }

  /** Re-schedule events after a sample kit change */
  reschedule(events: DrumEvent[]): void {
    if (!this._active) return;
    this.buildStemPlayers();
    this.scheduleDawEvents(events);
  }

  deactivate(): void {
    if (!this._active) return;
    this._active = false;

    // Clear DAW scheduled events
    for (const id of this.scheduledEvents) {
      Tone.getTransport().clear(id);
    }
    this.scheduledEvents = [];

    // Dispose per-stem player clones
    for (const sp of this.stemPlayers.values()) {
      for (const p of sp.players.values()) p.dispose();
    }
    this.stemPlayers.clear();

    // Reconnect backing player to base engine volume
    const bp = this.baseEngine.backingPlayer;
    const backingVol = this.baseEngine.backingVolumeNode;
    if (bp && backingVol) {
      bp.disconnect();
      bp.connect(backingVol);
    }

    // Dispose per-stem volume nodes
    for (const channel of this.channels.values()) {
      channel.volumeNode.dispose();
    }
    this.channels.clear();

    // Dispose metronome
    this.metronomePart?.dispose();
    this.metronomesynth?.dispose();
    this.metronomeVolume?.dispose();
    this.metronomePart = null;
    this.metronomesynth = null;
    this.metronomeVolume = null;

    // Unmute the base engine
    this.baseEngine.unmute();
  }

  setChannelVolume(id: string, db: number): void {
    const channel = this.channels.get(id);
    if (!channel) return;
    channel.volume = db;
    channel.volumeNode.volume.value = db;
  }

  toggleMute(id: string): void {
    const channel = this.channels.get(id);
    if (!channel) return;
    channel.muted = !channel.muted;
    this.recalcMuteStates();
  }

  toggleSolo(id: string): void {
    const channel = this.channels.get(id);
    if (!channel) return;
    channel.solo = !channel.solo;
    this.recalcMuteStates();
  }

  private recalcMuteStates(): void {
    const anySolo = [...this.channels.values()].some((c) => c.solo);
    for (const channel of this.channels.values()) {
      if (anySolo) {
        channel.volumeNode.mute = !channel.solo || channel.muted;
      } else {
        channel.volumeNode.mute = channel.muted;
      }
    }
  }

  getChannels(): DawChannel[] {
    return [...this.channels.values()];
  }

  getChannel(id: string): DawChannel | undefined {
    return this.channels.get(id);
  }

  setMetronome(enabled: boolean, bpm: number): void {
    this._metronomeEnabled = enabled;

    if (this.metronomeVolume) {
      this.metronomeVolume.mute = !enabled;
    }

    if (enabled && !this.metronomePart && this.metronomesynth) {
      const secondsPerBeat = 60 / bpm;
      this.metronomePart = new Tone.Loop((time) => {
        this.metronomesynth?.triggerAttackRelease("C5", "32n", time, 0.3);
      }, secondsPerBeat).start(0);
    } else if (!enabled && this.metronomePart) {
      this.metronomePart.dispose();
      this.metronomePart = null;
    }
  }

  async exportMaster(
    events: DrumEvent[],
    backingUrl: string,
    _bpm: number,
    sampleSet: string,
  ): Promise<Blob> {
    const { exportMix } = await import("@/lib/audio-export");
    return exportMix(backingUrl, events, 1, 1, sampleSet);
  }

  async exportChannelMidi(channelId: string, events: DrumEvent[], bpm: number): Promise<Blob> {
    const { exportEventsAsMidi } = await import("@/lib/midi-export");
    const channel = this.channels.get(channelId);
    if (!channel || channel.type !== "drum-stem") {
      throw new Error(`Channel ${channelId} is not a drum stem`);
    }
    const filtered = events.filter((e) => channel.midiNotes.includes(e.midi_note));
    return exportEventsAsMidi(filtered, bpm);
  }

  async exportChannelAudio(
    channelId: string,
    events: DrumEvent[],
    backingUrl: string,
    sampleSet: string,
  ): Promise<Blob> {
    const channel = this.channels.get(channelId);
    if (!channel) throw new Error(`Channel ${channelId} not found`);

    if (channel.type === "backing") {
      const response = await fetch(backingUrl);
      return response.blob();
    }

    const { noteUrls } = await buildDrumSampleUrls(sampleSet);
    const filtered = events.filter((e) => channel.midiNotes.includes(e.midi_note));

    const tempCtx = new AudioContext();

    const sampleBuffers = new Map<string, AudioBuffer>();
    const urlsToFetch = new Set<string>();
    for (const note of channel.midiNotes) {
      const urls = noteUrls[note];
      if (urls) for (const u of urls) urlsToFetch.add(u);
    }
    await Promise.all(
      [...urlsToFetch].map(async (url) => {
        const res = await fetch(url);
        const arr = await res.arrayBuffer();
        const decoded = await tempCtx.decodeAudioData(arr);
        sampleBuffers.set(url, decoded);
      }),
    );

    const duration = this.baseEngine.duration || 30;
    const sampleRate = tempCtx.sampleRate;
    tempCtx.close();

    const offlineCtx = new OfflineAudioContext(2, Math.ceil(sampleRate * duration), sampleRate);
    const roundRobinIndex: Record<number, number> = {};

    for (const event of filtered) {
      const urls = noteUrls[event.midi_note];
      if (!urls || urls.length === 0) continue;
      const idx = roundRobinIndex[event.midi_note] ?? 0;
      const url = urls[idx % urls.length];
      roundRobinIndex[event.midi_note] = idx + 1;

      const sampleBuffer = sampleBuffers.get(url);
      if (!sampleBuffer) continue;

      const source = offlineCtx.createBufferSource();
      source.buffer = sampleBuffer;
      const gainNode = offlineCtx.createGain();
      gainNode.gain.value = event.velocity / 127;
      source.connect(gainNode);
      gainNode.connect(offlineCtx.destination);
      source.start(event.quantized_time);
    }

    const renderedBuffer = await offlineCtx.startRendering();
    return encodeWav(renderedBuffer);
  }

  dispose(): void {
    this.deactivate();
  }
}

function encodeWav(audioBuffer: AudioBuffer): Blob {
  const numChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const numFrames = audioBuffer.length;
  const bytesPerSample = 2;
  const dataSize = numFrames * numChannels * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true);
  view.setUint16(32, numChannels * bytesPerSample, true);
  view.setUint16(34, bytesPerSample * 8, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  const channels: Float32Array[] = [];
  for (let ch = 0; ch < numChannels; ch++) channels.push(audioBuffer.getChannelData(ch));

  let offset = 44;
  for (let i = 0; i < numFrames; i++) {
    for (let ch = 0; ch < numChannels; ch++) {
      const sample = Math.max(-1, Math.min(1, channels[ch][i]));
      view.setInt16(offset, sample * 0x7fff, true);
      offset += 2;
    }
  }

  return new Blob([buffer], { type: "audio/wav" });
}
