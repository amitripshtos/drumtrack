"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MidiPlaybackEngine } from "@/lib/midi-playback";
import { DrumEvent } from "@/types";

export function useMidiPlayer() {
  const engineRef = useRef<MidiPlaybackEngine | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      engineRef.current?.dispose();
    };
  }, []);

  const init = useCallback(async (sampleSet: string = "default") => {
    if (engineRef.current) return;
    const engine = new MidiPlaybackEngine();
    await engine.init(sampleSet);
    engineRef.current = engine;
    setIsReady(true);
  }, []);

  const loadBackingTrack = useCallback(async (url: string) => {
    if (!engineRef.current) return;
    await engineRef.current.loadBackingTrack(url);
    setDuration(engineRef.current.duration);
  }, []);

  const scheduleEvents = useCallback((events: DrumEvent[], bpm: number) => {
    if (!engineRef.current) return;
    engineRef.current.scheduleEvents(events, bpm);
  }, []);

  const updateTime = useCallback(() => {
    if (engineRef.current) {
      setCurrentTime(engineRef.current.currentTime);
    }
    animFrameRef.current = requestAnimationFrame(updateTime);
  }, []);

  const play = useCallback(() => {
    engineRef.current?.play();
    setIsPlaying(true);
    animFrameRef.current = requestAnimationFrame(updateTime);
  }, [updateTime]);

  const pause = useCallback(() => {
    engineRef.current?.pause();
    setIsPlaying(false);
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    engineRef.current?.stop();
    setIsPlaying(false);
    setCurrentTime(0);
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  }, []);

  const seek = useCallback((seconds: number) => {
    engineRef.current?.seek(seconds);
    setCurrentTime(seconds);
  }, []);

  const setMidiVolume = useCallback((db: number) => {
    engineRef.current?.setMidiVolume(db);
  }, []);

  const setBackingVolume = useCallback((db: number) => {
    engineRef.current?.setBackingVolume(db);
  }, []);

  const changeSamples = useCallback(async (sampleSet: string) => {
    if (!engineRef.current) return;
    await engineRef.current.changeSamples(sampleSet);
  }, []);

  return {
    isReady,
    isPlaying,
    currentTime,
    duration,
    init,
    loadBackingTrack,
    scheduleEvents,
    play,
    pause,
    stop,
    seek,
    setMidiVolume,
    setBackingVolume,
    changeSamples,
  };
}
