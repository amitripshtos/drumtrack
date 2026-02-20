"""Core metric computation for drum transcription evaluation.

Implements F-measure, onset MAE, velocity RMSE, and confusion matrix
over the 5 DrumSep stem groups.
"""

import math

import numpy as np

from app.models.drum_event import DrumEvent

# drum_type → stem group (5 groups matching DrumSep stems)
STEM_GROUPS: dict[str, str] = {
    "kick": "kick",
    "snare": "snare",
    "tom_high": "toms",
    "tom_mid": "toms",
    "tom_low": "toms",
    "closed_hihat": "hh",
    "open_hihat": "hh",
    "crash": "cymbals",
    "ride": "cymbals",
}

ALL_GROUPS = ["kick", "snare", "toms", "hh", "cymbals"]


def _pred_group(event: DrumEvent) -> str:
    return STEM_GROUPS.get(event.drum_type, "unknown")


def _gt_group(gt: dict) -> str:
    return gt.get("stem_group") or STEM_GROUPS.get(gt.get("drum_type", ""), "unknown")


def match_events(
    predicted: list[DrumEvent],
    ground_truth: list[dict],
    tolerance_s: float = 0.05,
) -> tuple[list[tuple[DrumEvent, dict]], list[DrumEvent], list[dict]]:
    """Greedy nearest-neighbor matching within each stem group.

    Matches predicted events to ground truth events using quantized_time,
    within the MIREX standard tolerance window (default 50ms).

    Args:
        predicted: DrumEvent objects from detect_onsets_from_stems
        ground_truth: List of GT event dicts (with stem_group field)
        tolerance_s: Maximum time difference to consider a match

    Returns:
        matched: List of (pred, gt) pairs
        unmatched_pred: Predicted events with no GT match (false positives)
        unmatched_gt: GT events with no predicted match (false negatives)
    """
    # Group by stem group
    pred_by_group: dict[str, list[DrumEvent]] = {}
    for pred in predicted:
        pred_by_group.setdefault(_pred_group(pred), []).append(pred)

    gt_by_group: dict[str, list[dict]] = {}
    for gt in ground_truth:
        gt_by_group.setdefault(_gt_group(gt), []).append(gt)

    matched: list[tuple[DrumEvent, dict]] = []
    matched_pred_ids: set[int] = set()
    matched_gt_ids: set[int] = set()

    for group in ALL_GROUPS:
        preds = pred_by_group.get(group, [])
        gts = gt_by_group.get(group, [])

        # Build candidate pairs sorted by |time_diff| (greedy nearest-first)
        candidates: list[tuple[float, DrumEvent, dict]] = []
        for pred in preds:
            for gt in gts:
                diff = abs(pred.quantized_time - gt["quantized_time"])
                if diff <= tolerance_s:
                    candidates.append((diff, pred, gt))
        candidates.sort(key=lambda x: x[0])

        for diff, pred, gt in candidates:
            pid = id(pred)
            gid = id(gt)
            if pid not in matched_pred_ids and gid not in matched_gt_ids:
                matched.append((pred, gt))
                matched_pred_ids.add(pid)
                matched_gt_ids.add(gid)

    unmatched_pred = [p for p in predicted if id(p) not in matched_pred_ids]
    unmatched_gt = [g for g in ground_truth if id(g) not in matched_gt_ids]

    return matched, unmatched_pred, unmatched_gt


def compute_f_measure(
    predicted: list[DrumEvent],
    ground_truth: list[dict],
    tolerance_s: float = 0.05,
) -> tuple[dict[str, dict], list[tuple[DrumEvent, dict]], list[DrumEvent], list[dict]]:
    """Compute precision, recall, F1 per stem group and overall.

    Returns:
        result: Dict {group: {precision, recall, f1, tp, fp, fn}} plus "overall" key
        matched: Matched (pred, gt) pairs
        unmatched_pred: False positives
        unmatched_gt: False negatives
    """
    matched, unmatched_pred, unmatched_gt = match_events(predicted, ground_truth, tolerance_s)

    stats: dict[str, dict[str, int]] = {g: {"tp": 0, "fp": 0, "fn": 0} for g in ALL_GROUPS}

    for pred, gt in matched:
        group = _pred_group(pred)
        if group in stats:
            stats[group]["tp"] += 1

    for pred in unmatched_pred:
        group = _pred_group(pred)
        if group in stats:
            stats[group]["fp"] += 1

    for gt in unmatched_gt:
        group = _gt_group(gt)
        if group in stats:
            stats[group]["fn"] += 1

    result: dict[str, dict] = {}
    total_tp = total_fp = total_fn = 0

    for group, s in stats.items():
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        result[group] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    # Overall (micro-averaged)
    p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    result["overall"] = {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f, 4),
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
    }

    return result, matched, unmatched_pred, unmatched_gt


def compute_onset_mae(matched: list[tuple[DrumEvent, dict]]) -> float:
    """Mean absolute error between predicted raw onset and GT time (ms).

    Uses pred.time (pre-quantization) vs gt["time"] to measure onset detector accuracy.
    Returns 0.0 if no matched pairs.
    """
    if not matched:
        return 0.0
    errors = [abs(pred.time - gt["time"]) * 1000.0 for pred, gt in matched]
    return round(sum(errors) / len(errors), 3)


def compute_velocity_rmse(matched: list[tuple[DrumEvent, dict]]) -> float:
    """RMSE of predicted velocity vs ground truth velocity (MIDI units 0-127).

    Returns 0.0 if no matched pairs.
    """
    if not matched:
        return 0.0
    sq_errors = [(pred.velocity - gt["velocity"]) ** 2 for pred, gt in matched]
    return round(math.sqrt(sum(sq_errors) / len(sq_errors)), 3)


def compute_confusion_matrix(
    predicted: list[DrumEvent],
    ground_truth: list[dict],
    tolerance_s: float = 0.05,
) -> tuple[np.ndarray, list[str]]:
    """5×5 confusion matrix using time-only (instrument-agnostic) matching.

    Matches each predicted event to the nearest GT event regardless of stem group,
    then records (gt_group, pred_group) to measure instrument confusion.

    Returns:
        matrix: 5×5 int array, rows=GT groups, cols=predicted groups
        groups: Ordered list of group names (row/col labels)
    """
    group_to_idx = {g: i for i, g in enumerate(ALL_GROUPS)}
    matrix = np.zeros((5, 5), dtype=int)

    # Build all candidate (pred, gt) pairs with time-only matching
    candidates: list[tuple[float, DrumEvent, dict]] = []
    for pred in predicted:
        for gt in ground_truth:
            diff = abs(pred.quantized_time - gt["quantized_time"])
            if diff <= tolerance_s:
                candidates.append((diff, pred, gt))
    candidates.sort(key=lambda x: x[0])

    matched_pred_ids: set[int] = set()
    matched_gt_ids: set[int] = set()

    for diff, pred, gt in candidates:
        pid = id(pred)
        gid = id(gt)
        if pid in matched_pred_ids or gid in matched_gt_ids:
            continue
        matched_pred_ids.add(pid)
        matched_gt_ids.add(gid)

        row = group_to_idx.get(_gt_group(gt), -1)
        col = group_to_idx.get(_pred_group(pred), -1)
        if row >= 0 and col >= 0:
            matrix[row, col] += 1

    return matrix, ALL_GROUPS
