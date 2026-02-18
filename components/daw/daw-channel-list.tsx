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
    <div className="w-[200px] bg-muted/50 border-r border-border flex flex-col flex-shrink-0">
      {/* Spacer matching the time ruler height */}
      <div className="shrink-0 border-b border-border" style={{ height: TIME_RULER_HEIGHT }} />
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
