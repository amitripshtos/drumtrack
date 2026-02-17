"use client";

interface DawPlayheadProps {
  currentTime: number;
  pixelsPerSecond: number;
  scrollLeft: number;
  height: number;
}

export function DawPlayhead({
  currentTime,
  pixelsPerSecond,
  scrollLeft,
  height,
}: DawPlayheadProps) {
  const x = currentTime * pixelsPerSecond - scrollLeft;

  if (x < -2) return null;

  return (
    <div
      className="absolute top-0 w-px bg-red-500 pointer-events-none z-10"
      style={{
        left: x,
        height,
      }}
    />
  );
}
