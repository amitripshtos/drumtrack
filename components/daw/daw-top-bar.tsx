"use client";

import { Dialog } from "@base-ui/react/dialog";
import { Download, Pause, Play, Square, X } from "lucide-react";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePlayerContext } from "@/contexts/player-context";

export function DawTopBar() {
  const {
    isPlaying,
    play,
    pause,
    stop,
    currentTime,
    duration,
    bpm,
    dawEngine,
    events,
    jobId,
    currentSampleSet,
    sampleSets,
    changeSamples,
  } = usePlayerContext();
  const [metronome, setMetronome] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [changingSamples, setChangingSamples] = useState(false);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
  };

  const toggleMetronome = useCallback(() => {
    const next = !metronome;
    setMetronome(next);
    dawEngine?.setMetronome(next, bpm);
  }, [metronome, dawEngine, bpm]);

  const handleExportMaster = useCallback(async () => {
    if (!dawEngine) return;
    setExporting(true);
    try {
      const { getOtherTrackUrl } = await import("@/lib/api");
      const blob = await dawEngine.exportMaster(
        events,
        getOtherTrackUrl(jobId),
        bpm,
        currentSampleSet,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "drumtrack-master.wav";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Master export failed:", e);
    } finally {
      setExporting(false);
    }
  }, [dawEngine, events, jobId, bpm, currentSampleSet]);

  const handleSampleSetChange = useCallback(
    async (newSet: string | null) => {
      if (!newSet) return;
      setChangingSamples(true);
      try {
        await changeSamples(newSet);
      } catch (e) {
        console.error("Failed to change samples:", e);
      } finally {
        setChangingSamples(false);
      }
    },
    [changeSamples],
  );

  return (
    <div className="h-12 bg-card border-b border-border flex items-center px-4 gap-3 shrink-0">
      {/* Transport */}
      <div className="flex items-center gap-1">
        {isPlaying ? (
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={pause}>
            <Pause className="h-4 w-4" />
          </Button>
        ) : (
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={play}>
            <Play className="h-4 w-4" />
          </Button>
        )}
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={stop}>
          <Square className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Time display */}
      <div className="font-mono text-sm text-foreground min-w-[100px]">
        {formatTime(currentTime)}
        {duration > 0 && (
          <span className="text-muted-foreground text-xs ml-1">/ {formatTime(duration)}</span>
        )}
      </div>

      {/* BPM */}
      <div className="text-xs text-muted-foreground font-mono">{bpm} BPM</div>

      {/* Metronome */}
      <Button
        variant="ghost"
        size="sm"
        className={`h-7 px-2 text-xs ${metronome ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
        onClick={toggleMetronome}
      >
        Click
      </Button>

      {/* Sample kit selector */}
      {sampleSets.length > 1 && (
        <Select
          value={currentSampleSet}
          onValueChange={handleSampleSetChange}
          disabled={changingSamples}
        >
          <SelectTrigger className="w-32 text-xs h-7">
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
      )}

      <div className="flex-1" />

      {/* Export */}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 text-xs text-muted-foreground hover:text-foreground"
        onClick={handleExportMaster}
        disabled={exporting}
      >
        <Download className="h-3.5 w-3.5 mr-1" />
        {exporting ? "Exporting..." : "Export Master"}
      </Button>

      {/* Close */}
      <Dialog.Close
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
          />
        }
      >
        <X className="h-4 w-4" />
      </Dialog.Close>
    </div>
  );
}
