"use client";

import { CheckCircle, Loader2, Music, Plus, XCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { fetchJobs } from "@/lib/api";
import type { JobResponse } from "@/types";

function StatusIcon({ status }: { status: string }) {
  if (status === "complete") {
    return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />;
  }
  if (status === "failed") {
    return <XCircle className="h-4 w-4 text-red-500 shrink-0" />;
  }
  return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />;
}

function jobDisplayTitle(job: JobResponse): string {
  if (job.title) {
    return job.title.length > 40 ? `${job.title.slice(0, 37)}...` : job.title;
  }
  return `Job ${job.id.slice(0, 8)}`;
}

export function AppSidebar() {
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const pathname = usePathname();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchJobs();
        if (!cancelled) setJobs(data);
      } catch {
        // silently ignore fetch errors
      }
    }

    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <Sidebar>
      <SidebarHeader className="flex flex-row items-center gap-2 px-4 py-3">
        <Music className="h-5 w-5" />
        <span className="font-semibold text-lg">DrumTrack</span>
        {/* <SidebarTrigger className="ml-auto" /> */}
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton render={<Link href="/" />} isActive={pathname === "/"}>
                <Plus className="h-4 w-4" />
                <span>New Job</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>History</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {jobs.map((job) => {
                const jobPath = `/job/${job.id}`;
                const isActive = pathname === jobPath;
                return (
                  <SidebarMenuItem key={job.id}>
                    <SidebarMenuButton render={<Link href={jobPath} />} isActive={isActive}>
                      <StatusIcon status={job.status} />
                      <span className="truncate">{jobDisplayTitle(job)}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
              {jobs.length === 0 && (
                <p className="px-3 py-2 text-sm text-muted-foreground">No jobs yet</p>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="px-4 py-2">
        <p className="text-xs text-muted-foreground">Isolate drums &amp; generate MIDI</p>
      </SidebarFooter>
    </Sidebar>
  );
}
