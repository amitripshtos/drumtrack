import type { DrumEvent } from "@/types";

/**
 * Draw MIDI event rectangles on a canvas lane.
 * Each event is drawn as a rectangle at its quantized_time position,
 * with opacity based on velocity.
 */
export function drawMidiLane(
  ctx: CanvasRenderingContext2D,
  events: DrumEvent[],
  duration: number,
  width: number,
  height: number,
  color: string,
): void {
  ctx.clearRect(0, 0, width, height);
  if (duration <= 0 || events.length === 0) return;

  const pixelsPerSecond = width / duration;
  const noteWidth = Math.max(pixelsPerSecond * 0.05, 3);
  const noteHeight = height * 0.6;
  const yOffset = (height - noteHeight) / 2;

  for (const event of events) {
    const x = (event.quantized_time / duration) * width;
    const velocity = event.velocity / 127;

    ctx.globalAlpha = 0.3 + velocity * 0.7;
    ctx.fillStyle = color;
    ctx.fillRect(x, yOffset, noteWidth, noteHeight);
  }

  ctx.globalAlpha = 1;
}
