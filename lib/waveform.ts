/**
 * Compute peak amplitudes from an AudioBuffer, downsampled to `numBins` bins.
 */
export function computePeaks(audioBuffer: AudioBuffer, numBins: number): Float32Array {
  const peaks = new Float32Array(numBins);
  const channelData = audioBuffer.getChannelData(0);
  const samplesPerBin = channelData.length / numBins;

  for (let i = 0; i < numBins; i++) {
    const start = Math.floor(i * samplesPerBin);
    const end = Math.floor((i + 1) * samplesPerBin);
    let max = 0;
    for (let j = start; j < end; j++) {
      const abs = Math.abs(channelData[j]);
      if (abs > max) max = abs;
    }
    peaks[i] = max;
  }

  return peaks;
}

/**
 * Draw a waveform on a canvas 2D context from pre-computed peaks.
 */
export function drawWaveform(
  ctx: CanvasRenderingContext2D,
  peaks: Float32Array,
  width: number,
  height: number,
  color: string,
): void {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = color;

  const barWidth = width / peaks.length;
  const centerY = height / 2;

  for (let i = 0; i < peaks.length; i++) {
    const amp = peaks[i];
    const barHeight = amp * height * 0.9;
    const x = i * barWidth;
    ctx.globalAlpha = 0.6 + amp * 0.4;
    ctx.fillRect(x, centerY - barHeight / 2, Math.max(barWidth - 0.5, 1), barHeight || 1);
  }

  ctx.globalAlpha = 1;
}
