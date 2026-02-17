"use client";

import type { RefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { LANE_HEIGHT } from "@/components/daw/daw-constants";
import { DawPlayhead } from "@/components/daw/daw-playhead";
import { DawTimeRuler } from "@/components/daw/daw-time-ruler";
import { DawTrackLane } from "@/components/daw/daw-track-lane";
import { usePlayerContext } from "@/contexts/player-context";
import type { DawChannelState } from "@/hooks/use-daw-channels";
import { computePeaks } from "@/lib/waveform";

interface DawTimelineProps {
  channels: DawChannelState[];
  scrollRef: RefObject<HTMLDivElement | null>;
  onVerticalScroll: (e: React.UIEvent<HTMLDivElement>) => void;
}

const DEFAULT_PPS = 80; // pixels per second

export function DawTimeline({ channels, scrollRef, onVerticalScroll }: DawTimelineProps) {
  const { currentTime, duration, engine, isPlaying } = usePlayerContext();
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [containerWidth, setContainerWidth] = useState(800);
  const [waveformPeaks, setWaveformPeaks] = useState<Float32Array | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(DEFAULT_PPS);
  const { events } = usePlayerContext();

  // Observe container width
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const obs = new ResizeObserver(([entry]) => {
      setContainerWidth(entry.contentRect.width);
    });
    obs.observe(container);
    return () => obs.disconnect();
  }, []);

  // Compute waveform peaks from backing track
  useEffect(() => {
    const bp = engine?.backingPlayer;
    if (!bp?.loaded || !bp.buffer) return;
    const buffer = bp.buffer.get();
    if (!buffer) return;
    const numBins = Math.max(Math.floor(duration * pixelsPerSecond), 200);
    const peaks = computePeaks(buffer, numBins);
    setWaveformPeaks(peaks);
  }, [engine, duration, pixelsPerSecond]);

  // Auto-scroll to follow playhead during playback
  useEffect(() => {
    if (!isPlaying) return;
    const playheadX = currentTime * pixelsPerSecond;
    const viewEnd = scrollLeft + containerWidth;
    const margin = containerWidth * 0.2;

    if (playheadX > viewEnd - margin) {
      setScrollLeft(playheadX - containerWidth * 0.3);
    } else if (playheadX < scrollLeft + margin && scrollLeft > 0) {
      setScrollLeft(Math.max(0, playheadX - containerWidth * 0.7));
    }
  }, [currentTime, isPlaying, pixelsPerSecond, containerWidth, scrollLeft]);

  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      setScrollLeft(e.currentTarget.scrollLeft);
      onVerticalScroll(e);
    },
    [onVerticalScroll],
  );

  // Zoom with ctrl+wheel
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
      setPixelsPerSecond((prev) => Math.min(500, Math.max(20, prev * zoomFactor)));
    }
  }, []);

  const totalWidth = Math.max(duration * pixelsPerSecond, containerWidth);

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden" onWheel={handleWheel}>
      {/* Time ruler */}
      <DawTimeRuler
        width={containerWidth}
        duration={duration}
        scrollLeft={scrollLeft}
        pixelsPerSecond={pixelsPerSecond}
      />

      {/* Track lanes */}
      <div
        ref={(node) => {
          (containerRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
          if (scrollRef)
            (scrollRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
        }}
        className="flex-1 overflow-x-auto overflow-y-auto relative"
        onScroll={handleScroll}
      >
        <div style={{ width: totalWidth, position: "relative" }}>
          {/* Playhead */}
          <DawPlayhead
            currentTime={currentTime}
            pixelsPerSecond={pixelsPerSecond}
            scrollLeft={0}
            height={channels.length * LANE_HEIGHT}
          />

          {channels.map((ch) => (
            <div
              key={ch.id}
              className="border-b border-zinc-800/50"
              style={{ height: LANE_HEIGHT }}
            >
              <DawTrackLane
                channel={ch}
                events={events}
                duration={duration}
                width={totalWidth}
                height={LANE_HEIGHT}
                scrollLeft={0}
                pixelsPerSecond={pixelsPerSecond}
                waveformPeaks={ch.type === "backing" ? waveformPeaks : null}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
