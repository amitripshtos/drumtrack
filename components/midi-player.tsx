"use client";

import { Download, Music, Pause, Play, Square, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMidiPlayer } from "@/hooks/use-midi-player";
import { getEvents, getOtherTrackUrl } from "@/lib/api";
import { exportMix } from "@/lib/audio-export";
import { DrumEvent } from "@/types";

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
  return Math.pow(10, db / 20);
}

interface MidiPlayerProps {
  jobId: string;
  bpm: number;
}

export function MidiPlayer({ jobId, bpm }: MidiPlayerProps) {
  const player = useMidiPlayer();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<DrumEvent[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [midiVol, setMidiVol] = useState(80);
  const [backingVol, setBackingVol] = useState(80);
  const [exporting, setExporting] = useState(false);

  const handleInit = async () => {
    setLoading(true);
    try {
      await player.init();

      // Load backing track and events in parallel
      const [eventsData] = await Promise.all([
        getEvents(jobId),
        player.loadBackingTrack(getOtherTrackUrl(jobId)),
      ]);

      setEvents(eventsData);
      player.scheduleEvents(eventsData, bpm);
      setInitialized(true);
    } catch (e) {
      console.error("Failed to initialize player:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (player.isPlaying) player.pause();
    setExporting(true);
    try {
      const blob = await exportMix(
        getOtherTrackUrl(jobId),
        events,
        dbToLinear(sliderToDb(midiVol)),
        dbToLinear(sliderToDb(backingVol)),
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

  // Cleanup on unmount
  // biome-ignore lint/correctness/useExhaustiveDependencies: only run on unmount
  useEffect(() => {
    return () => {
      player.stop();
    };
  }, []);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>MIDI Player</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!initialized ? (
          <Button onClick={handleInit} disabled={loading} className="w-full">
            {loading ? "Loading samples..." : "Load Player"}
          </Button>
        ) : (
          <>
            {/* Transport controls */}
            <div className="flex items-center gap-2">
              {player.isPlaying ? (
                <Button onClick={player.pause} size="sm">
                  <Pause className="h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={player.play} size="sm">
                  <Play className="h-4 w-4" />
                </Button>
              )}
              <Button onClick={player.stop} variant="outline" size="sm">
                <Square className="h-4 w-4" />
              </Button>
              <Button onClick={handleExport} variant="outline" size="sm" disabled={exporting}>
                <Download className="h-4 w-4" />
                {exporting ? "Exporting..." : "Export WAV"}
              </Button>
              <span className="text-sm font-mono ml-2">{formatTime(player.currentTime)}</span>
              {player.duration > 0 && (
                <span className="text-xs text-muted-foreground font-mono">
                  / {formatTime(player.duration)}
                </span>
              )}
            </div>

            {/* Seek slider */}
            {player.duration > 0 && (
              <input
                type="range"
                min={0}
                max={player.duration}
                step={0.1}
                value={player.currentTime}
                onChange={(e) => player.seek(Number(e.target.value))}
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
                    player.setMidiVolume(sliderToDb(v));
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
                    player.setBackingVolume(sliderToDb(v));
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
