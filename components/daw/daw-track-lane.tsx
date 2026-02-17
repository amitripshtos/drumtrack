"use client";

import { useEffect, useRef } from "react";
import type { DawChannelState } from "@/hooks/use-daw-channels";
import { CHANNEL_COLORS } from "@/lib/channel-colors";
import { drawMidiLane } from "@/lib/midi-canvas";
import { drawWaveform } from "@/lib/waveform";
import type { DrumEvent } from "@/types";

interface DawTrackLaneProps {
  channel: DawChannelState;
  events: DrumEvent[];
  duration: number;
  width: number;
  height: number;
  scrollLeft: number;
  pixelsPerSecond: number;
  waveformPeaks?: Float32Array | null;
}

export function DawTrackLane({
  channel,
  events,
  duration,
  width,
  height,
  scrollLeft,
  pixelsPerSecond,
  waveformPeaks,
}: DawTrackLaneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const color = CHANNEL_COLORS[channel.id] || "#6b7280";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = "#0a0a0b";
    ctx.fillRect(0, 0, width, height);

    // Total content width based on duration
    const totalWidth = duration * pixelsPerSecond;

    // Save context and translate for scrolling
    ctx.save();
    ctx.translate(-scrollLeft, 0);

    if (channel.type === "backing" && waveformPeaks) {
      drawWaveform(ctx, waveformPeaks, totalWidth, height, color);
    } else if (channel.type === "drum-stem") {
      const channelEvents = events.filter((e) => channel.midiNotes.includes(e.midi_note));
      drawMidiLane(ctx, channelEvents, duration, totalWidth, height, color);
    }

    ctx.restore();
  }, [channel, events, duration, width, height, scrollLeft, pixelsPerSecond, color, waveformPeaks]);

  return <canvas ref={canvasRef} style={{ width, height }} className="block" />;
}
