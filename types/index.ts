export type JobStatus =
  | "pending"
  | "downloading_youtube"
  | "separating_stems"
  | "separating_drum_instruments"
  | "detecting_onsets"
  | "generating_midi"
  | "complete"
  | "failed";

export interface JobResponse {
  id: string;
  status: JobStatus;
  bpm: number;
  source: string;
  title: string | null;
  created_at: string | null;
  error: string | null;
  progress: number;
}

export interface DrumEvent {
  time: number;
  quantized_time: number;
  drum_type: string;
  midi_note: number;
  velocity: number;
  confidence: number;
  cluster_id: number;
}

export interface ClusterInfo {
  id: number;
  suggested_label: string;
  label: string;
  suggestion_confidence: number;
  event_count: number;
  mean_velocity: number;
  representative_time: number;
}

export interface ClustersResponse {
  clusters: ClusterInfo[];
  events: DrumEvent[];
}

/** Maps instrument name → array of WAV filenames (for round-robin). */
export type SampleKit = Record<string, string[]>;

export const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pending",
  downloading_youtube: "Downloading from YouTube",
  separating_stems: "Separating stems",
  separating_drum_instruments: "Separating drum instruments",
  detecting_onsets: "Detecting drum hits",
  generating_midi: "Generating MIDI",
  complete: "Complete",
  failed: "Failed",
};
