# GM Drum Map (Channel 10)
DRUM_MAP = {
    "kick": 36,
    "snare": 38,
    "closed_hihat": 42,
    "open_hihat": 46,
    "tom_high": 50,
    "tom_mid": 47,
    "tom_low": 45,
    "crash": 49,
    "ride": 51,
}

DRUM_NAMES = {v: k for k, v in DRUM_MAP.items()}

# Minimum inter-onset gap per drum type (milliseconds).
# Used by cluster-based deduplication to remove spurious double-triggers.
DRUM_TYPE_MIN_GAP_MS = {
    "kick": 35,
    "snare": 40,
    "closed_hihat": 25,
    "open_hihat": 80,
    "crash": 150,
    "ride": 60,
    "tom_high": 40,
    "tom_mid": 40,
    "tom_low": 50,
}
