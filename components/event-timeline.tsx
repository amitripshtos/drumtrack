"use client";

import { DrumEvent } from "@/types";

const DRUM_COLORS: Record<string, string> = {
  kick: "#ef4444",
  snare: "#f59e0b",
  closed_hihat: "#22c55e",
  open_hihat: "#10b981",
  crash: "#3b82f6",
  ride: "#6366f1",
  tom_high: "#ec4899",
  tom_mid: "#d946ef",
  tom_low: "#a855f7",
};

interface EventTimelineProps {
  events: DrumEvent[];
  totalDuration: number;
  color?: string;
}

export function EventTimeline({
  events,
  totalDuration,
  color,
}: EventTimelineProps) {
  if (totalDuration <= 0 || events.length === 0) return null;

  return (
    <svg
      className="w-full rounded"
      height="8"
      viewBox={`0 0 ${totalDuration} 8`}
      preserveAspectRatio="none"
    >
      <rect width={totalDuration} height="8" fill="currentColor" className="text-muted/30" />
      {events.map((event, i) => (
        <rect
          key={i}
          x={event.time}
          y="0"
          width={Math.max(totalDuration * 0.002, 0.02)}
          height="8"
          fill={color || DRUM_COLORS[event.drum_type] || "#888"}
        />
      ))}
    </svg>
  );
}

export { DRUM_COLORS };
