"use client";

import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { rerunJob } from "@/lib/api";

const CHECKPOINTS = [
  {
    value: "onset_detection",
    label: "Onset Detection",
    description: "Re-detect hits & regenerate MIDI (fastest)",
  },
  {
    value: "drumsep",
    label: "Drum Separation",
    description: "Re-separate drum instruments, then re-detect",
  },
  {
    value: "stem_separation",
    label: "Stem Separation",
    description: "Re-run Demucs and everything after",
  },
] as const;

export function RerunControls({ jobId }: { jobId: string }) {
  const [loading, setLoading] = useState(false);

  async function handleRerun(checkpoint: string) {
    setLoading(true);
    try {
      await rerunJob(jobId, checkpoint);
    } catch {
      setLoading(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={loading}
        render={<Button variant="outline" size="sm" disabled={loading} />}
      >
        <RotateCcw className="mr-2 h-4 w-4" />
        {loading ? "Re-running..." : "Re-run from..."}
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuGroup>
          <DropdownMenuLabel>Re-run pipeline from</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {CHECKPOINTS.map((cp) => (
            <DropdownMenuItem key={cp.value} onClick={() => handleRerun(cp.value)}>
              <div>
                <div className="font-medium">{cp.label}</div>
                <div className="text-muted-foreground text-[10px]">{cp.description}</div>
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
