"use client";

import { Download, FileAudio, FileMusic, Volume2, VolumeX } from "lucide-react";
import { useCallback, useState } from "react";
import { LANE_HEIGHT } from "@/components/daw/daw-constants";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePlayerContext } from "@/contexts/player-context";
import type { DawChannelState } from "@/hooks/use-daw-channels";
import { CHANNEL_COLORS, CHANNEL_LABELS } from "@/lib/channel-colors";

interface DawChannelStripProps {
  channel: DawChannelState;
  onVolumeChange: (id: string, db: number) => void;
  onToggleMute: (id: string) => void;
  onToggleSolo: (id: string) => void;
}

export function DawChannelStrip({
  channel,
  onVolumeChange,
  onToggleMute,
  onToggleSolo,
}: DawChannelStripProps) {
  const { dawEngine, events, bpm, currentSampleSet, jobId } = usePlayerContext();
  const [exporting, setExporting] = useState(false);
  const color = CHANNEL_COLORS[channel.id] || "#6b7280";
  const label = CHANNEL_LABELS[channel.id] || channel.name;

  const handleExportMidi = useCallback(async () => {
    if (!dawEngine || channel.type !== "drum-stem") return;
    setExporting(true);
    try {
      const blob = await dawEngine.exportChannelMidi(channel.id, events, bpm);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${channel.id}.mid`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export MIDI failed:", e);
    } finally {
      setExporting(false);
    }
  }, [dawEngine, channel, events, bpm]);

  const handleExportAudio = useCallback(async () => {
    if (!dawEngine) return;
    setExporting(true);
    try {
      const { getOtherTrackUrl } = await import("@/lib/api");
      const blob = await dawEngine.exportChannelAudio(
        channel.id,
        events,
        getOtherTrackUrl(jobId),
        currentSampleSet,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${channel.id}.wav`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export audio failed:", e);
    } finally {
      setExporting(false);
    }
  }, [dawEngine, channel, events, jobId, currentSampleSet]);

  const dbToSlider = (db: number) => ((db + 20) / 26) * 100;
  const sliderToDb = (val: number) => (val / 100) * 26 - 20;

  return (
    <div
      className="flex flex-col justify-center gap-1.5 px-3 border-b border-border box-border"
      style={{ height: LANE_HEIGHT }}
    >
      {/* Row 1: color dot + name */}
      <div className="flex items-center gap-1.5">
        <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
        <span className="text-[10px] font-medium text-foreground truncate">{label}</span>
      </div>

      {/* Row 2: volume fader */}
      <div className="flex items-center gap-1.5">
        {channel.muted ? (
          <VolumeX className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
        ) : (
          <Volume2 className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
        )}
        <input
          type="range"
          min={0}
          max={100}
          value={dbToSlider(channel.volume)}
          onChange={(e) => onVolumeChange(channel.id, sliderToDb(Number(e.target.value)))}
          className="h-1 w-full accent-foreground"
        />
        <span className="text-[9px] text-muted-foreground font-mono w-8 text-right shrink-0">
          {channel.volume > 0 ? "+" : ""}
          {channel.volume.toFixed(0)}
        </span>
      </div>

      {/* Row 3: M/S left, export right */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className={`h-4 px-1 text-[9px] font-bold min-w-0 ${
            channel.muted
              ? "bg-yellow-500 text-black hover:bg-yellow-400"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => onToggleMute(channel.id)}
        >
          M
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={`h-4 px-1 text-[9px] font-bold min-w-0 ${
            channel.solo
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => onToggleSolo(channel.id)}
        >
          S
        </Button>

        <div className="flex-1" />

        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                className="h-4 px-1 text-muted-foreground hover:text-foreground min-w-0"
                disabled={exporting}
              />
            }
          >
            <Download className="h-2.5 w-2.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent side="bottom" align="end">
            <DropdownMenuItem onClick={handleExportAudio}>
              <FileAudio className="h-3.5 w-3.5" />
              Export WAV
            </DropdownMenuItem>
            {channel.type === "drum-stem" && (
              <DropdownMenuItem onClick={handleExportMidi}>
                <FileMusic className="h-3.5 w-3.5" />
                Export MIDI
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
