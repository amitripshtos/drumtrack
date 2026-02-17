"use client";

import { Download, Maximize2, Music, Pause, Play, Square, Volume2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePlayerContext } from "@/contexts/player-context";
import { getOtherTrackUrl } from "@/lib/api";
import { exportMix } from "@/lib/audio-export";

/** Convert a 0–100 linear slider value to decibels (-Infinity to 0 dB). */
function sliderToDb(value: number): number {
  if (value <= 0) return -Infinity;
  // Quadratic taper for more natural volume feel
  const normalized = (value / 100) ** 2;
  // Map to -40 dB .. 0 dB range
  return 20 * Math.log10(normalized);
}

function dbToLinear(db: number): number {
  if (db === -Infinity) return 0;
  return 10 ** (db / 20);
}

export function MidiPlayer() {
  const {
    isReady,
    isPlaying,
    currentTime,
    duration,
    events,
    jobId,
    bpm,
    play,
    pause,
    stop,
    seek,
    initialize,
    isLoading,
    sampleSets,
    currentSampleSet,
    changeSamples,
    setMidiVolume,
    setBackingVolume,
    openDaw,
  } = usePlayerContext();

  const [midiVol, setMidiVol] = useState(80);
  const [backingVol, setBackingVol] = useState(80);
  const [exporting, setExporting] = useState(false);
  const [changingSamples, setChangingSamples] = useState(false);

  const handleInit = async () => {
    await initialize();
  };

  const handleSampleSetChange = async (newSet: string | null) => {
    if (!newSet) return;
    setChangingSamples(true);
    try {
      await changeSamples(newSet);
    } catch (e) {
      console.error("Failed to change samples:", e);
    } finally {
      setChangingSamples(false);
    }
  };

  const handleExport = async () => {
    if (isPlaying) pause();
    setExporting(true);
    try {
      const blob = await exportMix(
        getOtherTrackUrl(jobId),
        events,
        dbToLinear(sliderToDb(midiVol)),
        dbToLinear(sliderToDb(backingVol)),
        currentSampleSet,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "drumtrack-mix.wav";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          MIDI Player
          {isReady && (
            <Button variant="ghost" size="sm" onClick={openDaw} title="Open DAW view">
              <Maximize2 className="h-4 w-4" />
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!isReady ? (
          <Button onClick={handleInit} disabled={isLoading} className="w-full">
            {isLoading ? "Loading samples..." : "Load Player"}
          </Button>
        ) : (
          <>
            {/* Transport controls */}
            <div className="flex items-center gap-2">
              {isPlaying ? (
                <Button onClick={pause} size="sm">
                  <Pause className="h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={play} size="sm">
                  <Play className="h-4 w-4" />
                </Button>
              )}
              <Button onClick={stop} variant="outline" size="sm">
                <Square className="h-4 w-4" />
              </Button>
              <Button onClick={handleExport} variant="outline" size="sm" disabled={exporting}>
                <Download className="h-4 w-4" />
                {exporting ? "Exporting..." : "Export WAV"}
              </Button>
              <span className="text-sm font-mono ml-2">{formatTime(currentTime)}</span>
              {duration > 0 && (
                <span className="text-xs text-muted-foreground font-mono">
                  / {formatTime(duration)}
                </span>
              )}
            </div>

            {/* Sample set selector */}
            {sampleSets.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground shrink-0">Sample Kit</span>
                <Select
                  value={currentSampleSet}
                  onValueChange={handleSampleSetChange}
                  disabled={changingSamples}
                >
                  <SelectTrigger className="w-40 text-sm h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {sampleSets.map((set) => (
                      <SelectItem key={set} value={set}>
                        {set}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {changingSamples && (
                  <span className="text-xs text-muted-foreground">Loading...</span>
                )}
              </div>
            )}

            {/* Seek slider */}
            {duration > 0 && (
              <input
                type="range"
                min={0}
                max={duration}
                step={0.1}
                value={currentTime}
                onChange={(e) => seek(Number(e.target.value))}
                className="h-1.5 w-full accent-foreground"
              />
            )}

            {/* Volume controls */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Music className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="text-xs text-muted-foreground w-16 shrink-0">MIDI</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={midiVol}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setMidiVol(v);
                    setMidiVolume(sliderToDb(v));
                  }}
                  className="h-1.5 w-full accent-foreground"
                />
              </div>
              <div className="flex items-center gap-2">
                <Volume2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="text-xs text-muted-foreground w-16 shrink-0">Backing</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={backingVol}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setBackingVol(v);
                    setBackingVolume(sliderToDb(v));
                  }}
                  className="h-1.5 w-full accent-foreground"
                />
              </div>
            </div>

            {/* Event summary */}
            <div className="text-xs text-muted-foreground">
              <p>{events.length} drum hits detected</p>
              <p>BPM: {bpm}</p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
