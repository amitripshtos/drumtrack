"use client";

import { use, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JobProgress } from "@/components/job-progress";
import { MidiPlayer } from "@/components/midi-player";
import { DownloadButton } from "@/components/download-button";
import { ClusterReview } from "@/components/cluster-review";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getMidiUrl, getOtherTrackUrl, getDrumTrackUrl, getDrumStemUrl } from "@/lib/api";

export default function JobPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const { job, error } = useJobPolling(jobId);
  const [midiVersion, setMidiVersion] = useState(0);

  if (error) {
    return (
      <main className="flex flex-col items-center justify-center p-8">
        <p className="text-red-500">Error: {error}</p>
        <Link href="/" className="mt-4">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        </Link>
      </main>
    );
  }

  if (!job) {
    return (
      <main className="flex flex-col items-center justify-center p-8">
        <p className="text-muted-foreground">Loading...</p>
      </main>
    );
  }

  const isComplete = job.status === "complete";

  return (
    <main className="flex flex-col items-center p-8 pt-16">
      <div className="w-full max-w-lg space-y-6">
        <Link href="/">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            New Job
          </Button>
        </Link>

        <JobProgress job={job} />

        {isComplete && (
          <>
            <ClusterReview
              jobId={jobId}
              onRegenerate={() => setMidiVersion((v) => v + 1)}
            />

            <MidiPlayer
              key={midiVersion}
              jobId={jobId}
              bpm={job.bpm}
            />

            <div className="flex flex-wrap gap-2">
              <DownloadButton
                url={getMidiUrl(jobId)}
                label="MIDI File"
                filename={`drums_${jobId.slice(0, 8)}.mid`}
              />
              <DownloadButton
                url={getDrumTrackUrl(jobId)}
                label="Drum Track"
                filename={`drums_${jobId.slice(0, 8)}.mp3`}
              />
              <DownloadButton
                url={getOtherTrackUrl(jobId)}
                label="Backing Track"
                filename={`backing_${jobId.slice(0, 8)}.mp3`}
              />
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">
                Individual Drum Stems
              </h3>
              <div className="flex flex-wrap gap-2">
                <DownloadButton
                  url={getDrumStemUrl(jobId, "kick")}
                  label="Kick"
                  filename={`kick_${jobId.slice(0, 8)}.wav`}
                />
                <DownloadButton
                  url={getDrumStemUrl(jobId, "snare")}
                  label="Snare"
                  filename={`snare_${jobId.slice(0, 8)}.wav`}
                />
                <DownloadButton
                  url={getDrumStemUrl(jobId, "toms")}
                  label="Toms"
                  filename={`toms_${jobId.slice(0, 8)}.wav`}
                />
                <DownloadButton
                  url={getDrumStemUrl(jobId, "hh")}
                  label="Hi-hat"
                  filename={`hh_${jobId.slice(0, 8)}.wav`}
                />
                <DownloadButton
                  url={getDrumStemUrl(jobId, "cymbals")}
                  label="Cymbals"
                  filename={`cymbals_${jobId.slice(0, 8)}.wav`}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
