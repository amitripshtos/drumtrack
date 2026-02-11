import { DrumEvent } from "@/types";
import { DRUM_SAMPLES } from "@/lib/midi-playback";

function encodeWav(audioBuffer: AudioBuffer): Blob {
  const numChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const numFrames = audioBuffer.length;
  const bytesPerSample = 2; // 16-bit PCM
  const dataSize = numFrames * numChannels * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // Write RIFF header
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(view, 8, "WAVE");

  // Write fmt chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true);
  view.setUint16(32, numChannels * bytesPerSample, true);
  view.setUint16(34, bytesPerSample * 8, true);

  // Write data chunk
  writeString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  // Interleave channel data as 16-bit PCM
  const channels: Float32Array[] = [];
  for (let ch = 0; ch < numChannels; ch++) {
    channels.push(audioBuffer.getChannelData(ch));
  }

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

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

export async function exportMix(
  backingTrackUrl: string,
  events: DrumEvent[],
  midiGain: number,
  backingGain: number,
): Promise<Blob> {
  // Use a temporary online AudioContext for decoding
  const tempCtx = new AudioContext();

  // Fetch and decode the backing track
  const backingResponse = await fetch(backingTrackUrl);
  const backingArrayBuffer = await backingResponse.arrayBuffer();
  const backingBuffer = await tempCtx.decodeAudioData(backingArrayBuffer);

  // Collect unique MIDI notes used in events
  const usedNotes = new Set(events.map((e) => e.midi_note));

  // Fetch and decode all needed drum samples in parallel
  const sampleBuffers = new Map<number, AudioBuffer>();
  await Promise.all(
    [...usedNotes].map(async (note) => {
      const samplePath = DRUM_SAMPLES[note];
      if (!samplePath) return;
      const res = await fetch(samplePath);
      const arr = await res.arrayBuffer();
      const decoded = await tempCtx.decodeAudioData(arr);
      sampleBuffers.set(note, decoded);
    }),
  );

  tempCtx.close();

  // Create offline context matching the backing track
  const sampleRate = backingBuffer.sampleRate;
  const duration = backingBuffer.duration;
  const offlineCtx = new OfflineAudioContext(2, Math.ceil(sampleRate * duration), sampleRate);

  // Wire backing track
  const backingSource = offlineCtx.createBufferSource();
  backingSource.buffer = backingBuffer;
  const backingGainNode = offlineCtx.createGain();
  backingGainNode.gain.value = backingGain;
  backingSource.connect(backingGainNode);
  backingGainNode.connect(offlineCtx.destination);
  backingSource.start(0);

  // Wire each drum event
  for (const event of events) {
    const sampleBuffer = sampleBuffers.get(event.midi_note);
    if (!sampleBuffer) continue;

    const source = offlineCtx.createBufferSource();
    source.buffer = sampleBuffer;
    const gainNode = offlineCtx.createGain();
    gainNode.gain.value = (event.velocity / 127) * midiGain;
    source.connect(gainNode);
    gainNode.connect(offlineCtx.destination);
    source.start(event.quantized_time);
  }

  // Render and encode
  const renderedBuffer = await offlineCtx.startRendering();
  return encodeWav(renderedBuffer);
}
