export type JobStatus =
  | "pending"
  | "downloading_youtube"
  | "uploading_to_lalal"
  | "separating_stems"
  | "detecting_onsets"
  | "classifying_drums"
  | "generating_midi"
  | "complete"
  | "failed";

export interface JobResponse {
  id: string;
  status: JobStatus;
  bpm: number;
  source: string;
  separator: string;
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

export const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pending",
  downloading_youtube: "Downloading from YouTube",
  uploading_to_lalal: "Uploading to LALAL.AI",
  separating_stems: "Separating stems",
  detecting_onsets: "Detecting drum hits",
  classifying_drums: "Classifying drums",
  generating_midi: "Generating MIDI",
  complete: "Complete",
  failed: "Failed",
};
