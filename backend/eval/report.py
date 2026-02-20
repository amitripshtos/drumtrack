"""Terminal table formatting and JSON report writer for evaluation results."""

import json
import statistics
from pathlib import Path

from eval.metrics import ALL_GROUPS


def _fmt(val: float, decimals: int = 3) -> str:
    return f"{val:.{decimals}f}"


def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def print_sample_table(sample_name: str, fm_result: dict, onset_mae: float, vel_rmse: float) -> None:
    """Print per-sample metrics table to terminal."""
    col_w = 10
    headers = ["Group", "P", "R", "F1", "TP", "FP", "FN"]
    widths = [10, 8, 8, 8, 6, 6, 6]

    sep = "+" + "+".join("-" * w for w in widths) + "+"
    header_row = "|" + "|".join(h.center(w) for h, w in zip(headers, widths)) + "|"

    print(f"\n{'=' * 56}")
    print(f"  Sample: {sample_name}")
    print(f"  Onset MAE: {_fmt(onset_mae)} ms   Velocity RMSE: {_fmt(vel_rmse)}")
    print(sep)
    print(header_row)
    print(sep)

    for group in ALL_GROUPS + ["overall"]:
        s = fm_result.get(group, {})
        row = (
            f"|{group.center(widths[0])}"
            f"|{_pct(s.get('precision', 0)).center(widths[1])}"
            f"|{_pct(s.get('recall', 0)).center(widths[2])}"
            f"|{_pct(s.get('f1', 0)).center(widths[3])}"
            f"|{str(s.get('tp', 0)).center(widths[4])}"
            f"|{str(s.get('fp', 0)).center(widths[5])}"
            f"|{str(s.get('fn', 0)).center(widths[6])}"
            f"|"
        )
        if group == "overall":
            print(sep)
        print(row)
    print(sep)


def print_aggregate_table(all_results: list[dict]) -> None:
    """Print aggregate mean±std table across all samples."""
    if not all_results:
        return

    print(f"\n{'=' * 56}")
    print("  AGGREGATE (mean ± std across all samples)")

    col_w = 10
    headers = ["Group", "F1 mean", "F1 std", "P mean", "R mean"]
    widths = [10, 10, 10, 10, 10]
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    header_row = "|" + "|".join(h.center(w) for h, w in zip(headers, widths)) + "|"

    print(sep)
    print(header_row)
    print(sep)

    for group in ALL_GROUPS + ["overall"]:
        f1s = [r["fm"].get(group, {}).get("f1", 0.0) for r in all_results]
        ps = [r["fm"].get(group, {}).get("precision", 0.0) for r in all_results]
        rs = [r["fm"].get(group, {}).get("recall", 0.0) for r in all_results]

        mean_f1 = statistics.mean(f1s) if f1s else 0.0
        std_f1 = statistics.stdev(f1s) if len(f1s) > 1 else 0.0
        mean_p = statistics.mean(ps) if ps else 0.0
        mean_r = statistics.mean(rs) if rs else 0.0

        row = (
            f"|{group.center(widths[0])}"
            f"|{_pct(mean_f1).center(widths[1])}"
            f"|{('±' + _pct(std_f1)).center(widths[2])}"
            f"|{_pct(mean_p).center(widths[3])}"
            f"|{_pct(mean_r).center(widths[4])}"
            f"|"
        )
        if group == "overall":
            print(sep)
        print(row)
    print(sep)

    # Summary line
    maes = [r["onset_mae"] for r in all_results]
    rmses = [r["vel_rmse"] for r in all_results]
    print(f"  Onset MAE: {statistics.mean(maes):.2f} ± {statistics.stdev(maes) if len(maes) > 1 else 0:.2f} ms")
    print(f"  Velocity RMSE: {statistics.mean(rmses):.2f} ± {statistics.stdev(rmses) if len(rmses) > 1 else 0:.2f}")
    print()


def print_confusion_matrix(matrix, groups: list[str]) -> None:
    """Print 5×5 confusion matrix to terminal."""
    print(f"\n{'=' * 56}")
    print("  CONFUSION MATRIX (rows=GT, cols=predicted)")
    col_w = 9
    header = " " * 10 + "".join(g[:col_w].center(col_w) for g in groups)
    print(header)
    for i, row_label in enumerate(groups):
        row_str = row_label.ljust(10) + "".join(str(matrix[i, j]).center(col_w) for j in range(len(groups)))
        print(row_str)
    print()


def write_json_report(output_path: Path, all_results: list[dict]) -> None:
    """Write results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=lambda x: x.tolist() if hasattr(x, "tolist") else x)
    print(f"Results written to {output_path}")
