"use client";

import { useEffect, useRef, useState } from "react";
import { getJob } from "@/lib/api";
import { JobResponse } from "@/types";

export function useJobPolling(jobId: string | null) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const data = await getJob(jobId);
        setJob(data);
        if (data.status === "complete" || data.status === "failed") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Polling failed");
      }
    };

    // Initial fetch
    poll();

    // Poll every 2 seconds
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [jobId]);

  return { job, error };
}
