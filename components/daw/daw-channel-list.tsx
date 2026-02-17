"use client";

import type { RefObject } from "react";
import { DawChannelStrip } from "@/components/daw/daw-channel-strip";
import { TIME_RULER_HEIGHT } from "@/components/daw/daw-constants";
import type { DawChannelState } from "@/hooks/use-daw-channels";

interface DawChannelListProps {
  channels: DawChannelState[];
  onVolumeChange: (id: string, db: number) => void;
  onToggleMute: (id: string) => void;
  onToggleSolo: (id: string) => void;
  scrollRef: RefObject<HTMLDivElement | null>;
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
}

export function DawChannelList({
  channels,
  onVolumeChange,
  onToggleMute,
  onToggleSolo,
  scrollRef,
  onScroll,
}: DawChannelListProps) {
  return (
    <div className="w-[200px] bg-zinc-900 border-r border-zinc-800 flex flex-col flex-shrink-0">
      {/* Spacer matching the time ruler height */}
      <div
        className="shrink-0 border-b border-zinc-800 bg-zinc-900"
        style={{ height: TIME_RULER_HEIGHT }}
      />
      <div ref={scrollRef} className="flex-1 overflow-y-auto" onScroll={onScroll}>
        {channels.map((ch) => (
          <DawChannelStrip
            key={ch.id}
            channel={ch}
            onVolumeChange={onVolumeChange}
            onToggleMute={onToggleMute}
            onToggleSolo={onToggleSolo}
          />
        ))}
      </div>
    </div>
  );
}
