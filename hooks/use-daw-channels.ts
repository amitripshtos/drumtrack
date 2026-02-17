"use client";

import { useCallback, useEffect, useState } from "react";
import type { DawChannel, DawMixerEngine } from "@/lib/daw-engine";

export interface DawChannelState {
  id: string;
  name: string;
  type: "drum-stem" | "backing";
  volume: number;
  muted: boolean;
  solo: boolean;
  midiNotes: number[];
}

export function useDawChannels(dawEngine: DawMixerEngine | null) {
  const [channels, setChannels] = useState<DawChannelState[]>([]);

  // Sync channel state from engine
  const syncChannels = useCallback(() => {
    if (!dawEngine?.isActive) {
      setChannels([]);
      return;
    }
    const engineChannels = dawEngine.getChannels();
    setChannels(
      engineChannels.map((ch: DawChannel) => ({
        id: ch.id,
        name: ch.name,
        type: ch.type,
        volume: ch.volume,
        muted: ch.muted,
        solo: ch.solo,
        midiNotes: ch.midiNotes,
      })),
    );
  }, [dawEngine]);

  useEffect(() => {
    syncChannels();
  }, [syncChannels]);

  const setChannelVolume = useCallback(
    (id: string, db: number) => {
      dawEngine?.setChannelVolume(id, db);
      syncChannels();
    },
    [dawEngine, syncChannels],
  );

  const toggleMute = useCallback(
    (id: string) => {
      dawEngine?.toggleMute(id);
      syncChannels();
    },
    [dawEngine, syncChannels],
  );

  const toggleSolo = useCallback(
    (id: string) => {
      dawEngine?.toggleSolo(id);
      syncChannels();
    },
    [dawEngine, syncChannels],
  );

  return {
    channels,
    setChannelVolume,
    toggleMute,
    toggleSolo,
    syncChannels,
  };
}
