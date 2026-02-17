export const CHANNEL_COLORS: Record<string, string> = {
  kick: "#ef4444",
  snare: "#f59e0b",
  toms: "#a855f7",
  hh: "#22c55e",
  cymbals: "#3b82f6",
  backing: "#6b7280",
};

export const STEM_MIDI_NOTES: Record<string, number[]> = {
  kick: [36],
  snare: [38],
  toms: [45, 47, 50],
  hh: [42, 46],
  cymbals: [49, 51],
};

export const STEM_NAMES = ["kick", "snare", "toms", "hh", "cymbals"] as const;

export const CHANNEL_LABELS: Record<string, string> = {
  kick: "Kick",
  snare: "Snare",
  toms: "Toms",
  hh: "Hi-Hat",
  cymbals: "Cymbals",
  backing: "Backing",
};
