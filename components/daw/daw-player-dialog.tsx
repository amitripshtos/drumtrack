"use client";

import { Dialog } from "@base-ui/react/dialog";
import { useCallback, useEffect, useRef } from "react";
import { DawChannelList } from "@/components/daw/daw-channel-list";
import { DawTimeline } from "@/components/daw/daw-timeline";
import { DawTopBar } from "@/components/daw/daw-top-bar";
import { usePlayerContext } from "@/contexts/player-context";
import { useDawChannels } from "@/hooks/use-daw-channels";

export function DawPlayerDialog() {
  const { isDawOpen, closeDaw, dawEngine, isPlaying, play, pause } = usePlayerContext();
  const { channels, setChannelVolume, toggleMute, toggleSolo, syncChannels } =
    useDawChannels(dawEngine);

  const channelScrollRef = useRef<HTMLDivElement>(null);
  const timelineScrollRef = useRef<HTMLDivElement>(null);
  const isSyncing = useRef(false);

  // Sync channels when DAW opens
  useEffect(() => {
    if (isDawOpen) syncChannels();
  }, [isDawOpen, syncChannels]);

  // Spacebar play/pause when DAW is open
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isDawOpen) return;
      if (e.code === "Space") {
        e.preventDefault();
        if (isPlaying) {
          pause();
        } else {
          play();
        }
      }
    },
    [isDawOpen, isPlaying, play, pause],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Sync vertical scroll between channel list and timeline
  const handleChannelScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    if (isSyncing.current) return;
    isSyncing.current = true;
    const target = e.currentTarget;
    if (timelineScrollRef.current) {
      timelineScrollRef.current.scrollTop = target.scrollTop;
    }
    requestAnimationFrame(() => {
      isSyncing.current = false;
    });
  }, []);

  const handleTimelineScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    if (isSyncing.current) return;
    isSyncing.current = true;
    const target = e.currentTarget;
    if (channelScrollRef.current) {
      channelScrollRef.current.scrollTop = target.scrollTop;
    }
    requestAnimationFrame(() => {
      isSyncing.current = false;
    });
  }, []);

  return (
    <Dialog.Root
      open={isDawOpen}
      onOpenChange={(open) => {
        if (!open) closeDaw();
      }}
    >
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/80" />
        <Dialog.Popup className="fixed inset-0 z-50 flex flex-col bg-zinc-950 text-zinc-100">
          {/* Title (hidden visually for a11y) */}
          <Dialog.Title className="sr-only">DAW Player</Dialog.Title>

          {/* Top bar with transport + close button */}
          <DawTopBar />

          {/* Main content: channel strips + timeline */}
          <div className="flex flex-1 min-h-0">
            <DawChannelList
              channels={channels}
              onVolumeChange={setChannelVolume}
              onToggleMute={toggleMute}
              onToggleSolo={toggleSolo}
              scrollRef={channelScrollRef}
              onScroll={handleChannelScroll}
            />
            <DawTimeline
              channels={channels}
              scrollRef={timelineScrollRef}
              onVerticalScroll={handleTimelineScroll}
            />
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
