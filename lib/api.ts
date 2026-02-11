import { ClustersResponse, DrumEvent, JobResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadFile(
  file: File,
  bpm: number,
  separator: string = "demucs",
): Promise<JobResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("bpm", bpm.toString());
  form.append("separator", separator);

  const res = await fetch(`${API_BASE}/api/jobs/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function submitYouTube(
  url: string,
  bpm: number,
  separator: string = "demucs",
): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/youtube`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, bpm, separator }),
  });
  if (!res.ok) throw new Error(`YouTube submit failed: ${res.statusText}`);
  return res.json();
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get job: ${res.statusText}`);
  return res.json();
}

export async function getEvents(jobId: string): Promise<DrumEvent[]> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/events`);
  if (!res.ok) throw new Error(`Failed to get events: ${res.statusText}`);
  return res.json();
}

export function getMidiUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/midi`;
}

export function getOtherTrackUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/other-track`;
}

export function getDrumTrackUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/drum-track`;
}

export async function getClusters(jobId: string): Promise<ClustersResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/clusters`);
  if (!res.ok) throw new Error(`Failed to get clusters: ${res.statusText}`);
  return res.json();
}

export async function updateClusters(
  jobId: string,
  clusterLabels: Record<string, string>,
): Promise<ClustersResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/clusters`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cluster_labels: clusterLabels }),
  });
  if (!res.ok) throw new Error(`Failed to update clusters: ${res.statusText}`);
  return res.json();
}

export async function fetchJobs(): Promise<JobResponse[]> {
  const res = await fetch(`${API_BASE}/api/jobs/`);
  if (!res.ok) throw new Error(`Failed to fetch jobs: ${res.statusText}`);
  return res.json();
}

export function getDrumStemUrl(jobId: string, stemName: string): string {
  return `${API_BASE}/api/jobs/${jobId}/stems/${stemName}`;
}

export async function getDrumTrackArrayBuffer(jobId: string): Promise<ArrayBuffer> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/drum-track`);
  if (!res.ok) throw new Error(`Failed to get drum track: ${res.statusText}`);
  return res.arrayBuffer();
}
