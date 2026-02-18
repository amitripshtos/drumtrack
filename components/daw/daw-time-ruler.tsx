"use client";

import { useCallback, useEffect, useRef } from "react";
import { usePlayerContext } from "@/contexts/player-context";

interface DawTimeRulerProps {
  width: number;
  duration: number;
  scrollLeft: number;
  pixelsPerSecond: number;
}

export function DawTimeRuler({ width, duration, scrollLeft, pixelsPerSecond }: DawTimeRulerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { seek, bpm } = usePlayerContext();

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = 28 * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, 28);

    const style = getComputedStyle(document.documentElement);
    const bgColor = style.getPropertyValue("--card").trim();
    const borderColor = style.getPropertyValue("--border").trim();
    const textColor = style.getPropertyValue("--muted-foreground").trim();

    // Background
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, width, 28);

    // Draw second markers
    const startSec = Math.floor(scrollLeft / pixelsPerSecond);
    const endSec = Math.ceil((scrollLeft + width) / pixelsPerSecond);

    ctx.strokeStyle = borderColor;
    ctx.fillStyle = textColor;
    ctx.font = "10px monospace";
    ctx.textAlign = "center";

    for (let s = startSec; s <= endSec; s++) {
      const x = s * pixelsPerSecond - scrollLeft;
      if (x < -20 || x > width + 20) continue;

      // Tick mark
      ctx.beginPath();
      ctx.moveTo(x, 20);
      ctx.lineTo(x, 28);
      ctx.stroke();

      // Label every 5 seconds
      if (s % 5 === 0) {
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        ctx.fillText(`${mins}:${secs.toString().padStart(2, "0")}`, x, 16);
      }
    }

    // Draw beat grid markers (lighter)
    if (bpm > 0) {
      const secondsPerBeat = 60 / bpm;
      const startBeat = Math.floor(scrollLeft / pixelsPerSecond / secondsPerBeat);
      const endBeat = Math.ceil((scrollLeft + width) / pixelsPerSecond / secondsPerBeat);

      ctx.strokeStyle = borderColor;
      for (let b = startBeat; b <= endBeat; b++) {
        const x = b * secondsPerBeat * pixelsPerSecond - scrollLeft;
        if (x < 0 || x > width) continue;
        ctx.beginPath();
        ctx.moveTo(x, 24);
        ctx.lineTo(x, 28);
        ctx.stroke();
      }
    }
  }, [width, scrollLeft, pixelsPerSecond, bpm]);

  useEffect(() => {
    draw();
  }, [draw]);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left + scrollLeft;
      const seconds = x / pixelsPerSecond;
      seek(Math.max(0, Math.min(seconds, duration)));
    },
    [scrollLeft, pixelsPerSecond, seek, duration],
  );

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height: 28 }}
      className="cursor-pointer block border-b border-border"
      onClick={handleClick}
    />
  );
}
