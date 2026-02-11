"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JobResponse, STATUS_LABELS } from "@/types";

interface JobProgressProps {
  job: JobResponse;
}

export function JobProgress({ job }: JobProgressProps) {
  const isComplete = job.status === "complete";
  const isFailed = job.status === "failed";
  const isProcessing = !isComplete && !isFailed;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isProcessing && <Loader2 className="h-5 w-5 animate-spin" />}
          {isComplete && <CheckCircle2 className="h-5 w-5 text-green-500" />}
          {isFailed && <XCircle className="h-5 w-5 text-red-500" />}
          {STATUS_LABELS[job.status]}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Progress</span>
            <span>{Math.round(job.progress)}%</span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isFailed ? "bg-red-500" : isComplete ? "bg-green-500" : "bg-primary"
              }`}
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>

        {/* Error message */}
        {isFailed && job.error && <p className="text-sm text-red-500">{job.error}</p>}

        {/* Job info */}
        <div className="text-xs text-muted-foreground space-y-1">
          <p>Job ID: {job.id}</p>
          <p>BPM: {job.bpm}</p>
          <p>Source: {job.source}</p>
        </div>
      </CardContent>
    </Card>
  );
}
