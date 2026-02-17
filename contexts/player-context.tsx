"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getEvents, getOtherTrackUrl, getSampleSets } from "@/lib/api";
import { DawMixerEngine } from "@/lib/daw-engine";
import { MidiPlaybackEngine } from "@/lib/midi-playback";
import type { DrumEvent } from "@/types";

interface PlayerContextValue {
  // Engine refs
  engine: MidiPlaybackEngine | null;
  dawEngine: DawMixerEngine | null;
  // Transport state
  isReady: boolean;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  bpm: number;
  events: DrumEvent[];
  jobId: string;
  // Transport controls
  play(): void;
  pause(): void;
  stop(): void;
  seek(s: number): void;
  // Initialization
  initialize(): Promise<void>;
  isLoading: boolean;
  // Sample kit
  sampleSets: string[];
  currentSampleSet: string;
  changeSamples(set: string): Promise<void>;
  // DAW lifecycle
  isDawOpen: boolean;
  openDaw(): void;
  closeDaw(): void;
  // Volume (mini player mode)
  setMidiVolume(db: number): void;
  setBackingVolume(db: number): void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

export function usePlayerContext(): PlayerContextValue {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayerContext must be used within PlayerProvider");
  return ctx;
}

interface PlayerProviderProps {
  jobId: string;
  bpm: number;
  children: ReactNode;
}

export function PlayerProvider({ jobId, bpm, children }: PlayerProviderProps) {
  const engineRef = useRef<MidiPlaybackEngine | null>(null);
  const dawEngineRef = useRef<DawMixerEngine | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [events, setEvents] = useState<DrumEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sampleSets, setSampleSets] = useState<string[]>([]);
  const [currentSampleSet, setCurrentSampleSet] = useState("default");
  const [isDawOpen, setIsDawOpen] = useState(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      dawEngineRef.current?.dispose();
      engineRef.current?.dispose();
    };
  }, []);

  const updateTime = useCallback(() => {
    if (engineRef.current) {
      setCurrentTime(engineRef.current.currentTime);
    }
    animFrameRef.current = requestAnimationFrame(updateTime);
  }, []);

  const initialize = useCallback(async () => {
    if (engineRef.current) return;
    setIsLoading(true);
    try {
      const engine = new MidiPlaybackEngine();
      const [sets] = await Promise.all([getSampleSets(), engine.init(currentSampleSet)]);
      setSampleSets(sets);

      const [eventsData] = await Promise.all([
        getEvents(jobId),
        engine.loadBackingTrack(getOtherTrackUrl(jobId)),
      ]);

      setEvents(eventsData);
      engine.scheduleEvents(eventsData, bpm);
      engineRef.current = engine;
      dawEngineRef.current = new DawMixerEngine(engine);
      setDuration(engine.duration);
      setIsReady(true);
    } catch (e) {
      console.error("Failed to initialize player:", e);
    } finally {
      setIsLoading(false);
    }
  }, [jobId, bpm, currentSampleSet]);

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

  const changeSamples = useCallback(
    async (set: string) => {
      if (!engineRef.current) return;
      setCurrentSampleSet(set);
      await engineRef.current.changeSamples(set);
      // Re-schedule DAW events so new players get routed through per-stem volumes
      dawEngineRef.current?.reschedule(events);
    },
    [events],
  );

  const openDaw = useCallback(async () => {
    if (!dawEngineRef.current || !engineRef.current) return;
    await dawEngineRef.current.activate(events, getOtherTrackUrl(jobId));
    setIsDawOpen(true);
  }, [events, jobId]);

  const closeDaw = useCallback(() => {
    if (!dawEngineRef.current) return;
    dawEngineRef.current.deactivate();
    setIsDawOpen(false);

    // Re-schedule events through the base engine
    if (engineRef.current) {
      engineRef.current.scheduleEvents(events, bpm);
    }
  }, [events, bpm]);

  const value: PlayerContextValue = {
    engine: engineRef.current,
    dawEngine: dawEngineRef.current,
    isReady,
    isPlaying,
    currentTime,
    duration,
    bpm,
    events,
    jobId,
    play,
    pause,
    stop,
    seek,
    initialize,
    isLoading,
    sampleSets,
    currentSampleSet,
    changeSamples,
    isDawOpen,
    openDaw,
    closeDaw,
    setMidiVolume,
    setBackingVolume,
  };

  return <PlayerContext value={value}>{children}</PlayerContext>;
}
