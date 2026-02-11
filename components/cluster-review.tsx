"use client";

import { Play, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { DRUM_COLORS, EventTimeline } from "@/components/event-timeline";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAudioSnippets } from "@/hooks/use-audio-snippets";
import { getClusters, getDrumTrackArrayBuffer, updateClusters } from "@/lib/api";
import { ClusterInfo, DrumEvent } from "@/types";

const DRUM_TYPES = [
  { value: "kick", label: "Kick" },
  { value: "snare", label: "Snare" },
  { value: "closed_hihat", label: "Closed Hi-Hat" },
  { value: "open_hihat", label: "Open Hi-Hat" },
  { value: "crash", label: "Crash" },
  { value: "ride", label: "Ride" },
  { value: "tom_high", label: "Tom High" },
  { value: "tom_mid", label: "Tom Mid" },
  { value: "tom_low", label: "Tom Low" },
];

interface ClusterReviewProps {
  jobId: string;
  onRegenerate?: () => void;
}

export function ClusterReview({ jobId, onRegenerate }: ClusterReviewProps) {
  const [clusters, setClusters] = useState<ClusterInfo[]>([]);
  const [events, setEvents] = useState<DrumEvent[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const fetchAudio = useCallback(() => getDrumTrackArrayBuffer(jobId), [jobId]);
  const { playSnippet, isLoaded: audioLoaded } = useAudioSnippets(fetchAudio);

  useEffect(() => {
    async function load() {
      try {
        const data = await getClusters(jobId);
        setClusters(data.clusters);
        setEvents(data.events as DrumEvent[]);
        const initialLabels: Record<string, string> = {};
        for (const c of data.clusters) {
          initialLabels[String(c.id)] = c.label;
        }
        setLabels(initialLabels);
      } catch (err) {
        console.error("Failed to load clusters:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [jobId]);

  const handleLabelChange = (clusterId: number, newLabel: string) => {
    setLabels((prev) => {
      const next = { ...prev, [String(clusterId)]: newLabel };
      setHasChanges(true);
      return next;
    });
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const data = await updateClusters(jobId, labels);
      setClusters(data.clusters);
      setEvents(data.events as DrumEvent[]);
      setHasChanges(false);
      onRegenerate?.();
    } catch (err) {
      console.error("Failed to regenerate:", err);
    } finally {
      setRegenerating(false);
    }
  };

  const totalDuration = events.length > 0 ? Math.max(...events.map((e) => e.time)) + 1 : 0;

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent>
          <p className="text-muted-foreground py-4">Loading clusters...</p>
        </CardContent>
      </Card>
    );
  }

  if (clusters.length === 0) return null;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Drum Classification Review</CardTitle>
        <CardDescription>
          {clusters.length} sound groups detected. Adjust labels if needed, then regenerate.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {clusters.map((cluster) => {
          const clusterEvents = events.filter((e) => e.cluster_id === cluster.id);
          const currentLabel = labels[String(cluster.id)] || cluster.label;
          const color = DRUM_COLORS[currentLabel] || "#888";

          return (
            <div key={cluster.id} className="flex items-center gap-3 rounded border p-2">
              {/* Color dot */}
              <div className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: color }} />

              {/* Label select */}
              <Select
                value={currentLabel}
                onValueChange={(val) => val && handleLabelChange(cluster.id, val)}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DRUM_TYPES.map((dt) => (
                    <SelectItem key={dt.value} value={dt.value}>
                      {dt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Event count */}
              <span className="text-muted-foreground shrink-0 text-xs">
                {cluster.event_count} hits
              </span>

              {/* Confidence */}
              <span className="text-muted-foreground shrink-0 text-xs">
                {Math.round(cluster.suggestion_confidence * 100)}%
              </span>

              {/* Play snippet button */}
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 shrink-0 p-0"
                disabled={!audioLoaded}
                onClick={() => playSnippet(cluster.representative_time)}
              >
                <Play className="h-3 w-3" />
              </Button>

              {/* Mini timeline */}
              <div className="min-w-0 flex-1">
                <EventTimeline events={clusterEvents} totalDuration={totalDuration} color={color} />
              </div>
            </div>
          );
        })}
      </CardContent>
      <CardFooter>
        <Button
          onClick={handleRegenerate}
          disabled={regenerating || !hasChanges}
          className="w-full"
        >
          {regenerating ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Regenerating...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Regenerate MIDI
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}
