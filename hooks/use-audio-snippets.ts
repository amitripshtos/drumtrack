"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useAudioSnippets(fetchAudioBuffer: () => Promise<ArrayBuffer>) {
  const [isLoaded, setIsLoaded] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const bufferRef = useRef<AudioBuffer | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const ctx = new AudioContext();
        audioCtxRef.current = ctx;

        const arrayBuffer = await fetchAudioBuffer();
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

        if (!cancelled) {
          bufferRef.current = audioBuffer;
          setIsLoaded(true);
        }
      } catch (err) {
        console.error("Failed to load audio for snippets:", err);
      }
    }

    load();

    return () => {
      cancelled = true;
      sourceRef.current?.stop();
      audioCtxRef.current?.close();
    };
  }, [fetchAudioBuffer]);

  const playSnippet = useCallback(
    (startTime: number, duration: number = 0.3) => {
      const ctx = audioCtxRef.current;
      const buffer = bufferRef.current;
      if (!ctx || !buffer) return;

      // Stop any currently playing snippet
      sourceRef.current?.stop();

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      const clampedStart = Math.max(0, Math.min(startTime, buffer.duration));
      const clampedDuration = Math.min(duration, buffer.duration - clampedStart);

      source.start(0, clampedStart, clampedDuration);
      sourceRef.current = source;
    },
    []
  );

  return { playSnippet, isLoaded };
}
