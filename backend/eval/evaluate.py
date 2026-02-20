"""CLI entry point for the drum transcription evaluation framework.

Subcommands:
  generate-patterns  — Write built-in MIDI patterns to disk
  generate-dataset   — Render MIDI → synthetic audio stems + ground truth
  evaluate           — Run evaluation on a synthetic dataset (fast, no DrumSep)

Usage (from backend/ directory):
  uv run python -m eval.evaluate generate-patterns --output-dir ./eval/midis --bpm 120
  uv run python -m eval.evaluate generate-dataset \\
      --midi-dir ./eval/midis \\
      --sample-kit ./storage/samples/test/kit.json \\
      --output-dir ./eval/dataset
  uv run python -m eval.evaluate evaluate \\
      --dataset ./eval/dataset --tolerance 50 --output-json ./eval/results.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def _cmd_generate_patterns(args: argparse.Namespace) -> None:
    from eval.patterns import generate_simple_patterns

    output_dir = Path(args.output_dir)
    print(f"Generating MIDI patterns → {output_dir}")
    created = generate_simple_patterns(output_dir, bpm=args.bpm)
    print(f"Done. Created {len(created)} pattern files.")


def _cmd_generate_dataset(args: argparse.Namespace) -> None:
    from eval.generate_dataset import render_midi_to_dataset

    midi_dir = Path(args.midi_dir)
    kit_json = Path(args.sample_kit)
    output_dir = Path(args.output_dir)
    snr_db = args.snr

    midi_files = sorted(midi_dir.glob("*.mid"))
    if not midi_files:
        print(f"Error: no .mid files found in {midi_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Rendering {len(midi_files)} MIDI files → {output_dir}")
    if snr_db is not None:
        print(f"  Adding white noise at SNR={snr_db} dB")

    for midi_path in midi_files:
        sample_dir = output_dir / midi_path.stem
        print(f"  {midi_path.name} → {sample_dir.name}/")
        meta = render_midi_to_dataset(
            midi_path=midi_path,
            kit_json_path=kit_json,
            output_dir=sample_dir,
            snr_db=snr_db,
        )
        if meta:
            print(f"    BPM={meta['bpm']}, events={meta['event_count']}, dur={meta['duration_s']:.1f}s")

    print("Done.")


def _cmd_evaluate(args: argparse.Namespace) -> None:
    from app.services.drum_clusterer import detect_onsets_from_stems
    from eval.metrics import (
        compute_confusion_matrix,
        compute_f_measure,
        compute_onset_mae,
        compute_velocity_rmse,
    )
    from eval.report import (
        print_aggregate_table,
        print_confusion_matrix,
        print_sample_table,
        write_json_report,
    )

    dataset_dir = Path(args.dataset)
    tolerance_s = args.tolerance / 1000.0  # ms → s
    output_json = Path(args.output_json) if args.output_json else None

    # Find all sample directories (each must have mix.wav + ground_truth.json + meta.json)
    sample_dirs = sorted(
        d for d in dataset_dir.iterdir()
        if d.is_dir() and (d / "mix.wav").exists() and (d / "ground_truth.json").exists()
    )

    if not sample_dirs:
        print(f"Error: no valid sample directories found in {dataset_dir}", file=sys.stderr)
        print("  Expected: <dataset>/<sample>/mix.wav + ground_truth.json + meta.json")
        sys.exit(1)

    print(f"Evaluating {len(sample_dirs)} samples in {dataset_dir}")
    print(f"Tolerance: {args.tolerance} ms\n")

    all_results: list[dict] = []
    aggregate_confusion = np.zeros((5, 5), dtype=int)

    for sample_dir in sample_dirs:
        # Load ground truth and meta
        with open(sample_dir / "ground_truth.json") as f:
            ground_truth = json.load(f)

        with open(sample_dir / "meta.json") as f:
            meta = json.load(f)

        bpm = meta["bpm"]
        mix_wav = sample_dir / "mix.wav"

        # Run onset detection (fast path — stems already on disk)
        try:
            predicted, _ = detect_onsets_from_stems(mix_wav, bpm)
        except Exception as e:
            print(f"  Warning: {sample_dir.name} failed: {e}")
            continue

        # Compute metrics
        fm_result, matched, fp_events, fn_events = compute_f_measure(
            predicted, ground_truth, tolerance_s
        )
        onset_mae = compute_onset_mae(matched)
        vel_rmse = compute_velocity_rmse(matched)
        confusion, groups = compute_confusion_matrix(predicted, ground_truth, tolerance_s)

        aggregate_confusion += confusion

        result = {
            "sample": sample_dir.name,
            "bpm": bpm,
            "gt_events": len(ground_truth),
            "pred_events": len(predicted),
            "fm": fm_result,
            "onset_mae_ms": onset_mae,
            "vel_rmse": vel_rmse,
        }
        all_results.append(result)

        print_sample_table(sample_dir.name, fm_result, onset_mae, vel_rmse)

    if all_results:
        # Reformat for aggregate table (uses 'fm' key internally)
        agg_input = [{"fm": r["fm"], "onset_mae": r["onset_mae_ms"], "vel_rmse": r["vel_rmse"]} for r in all_results]
        print_aggregate_table(agg_input)
        print_confusion_matrix(aggregate_confusion, groups)

    if output_json:
        write_json_report(output_json, all_results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DrumTrack evaluation framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- generate-patterns ---
    p_patterns = subparsers.add_parser(
        "generate-patterns",
        help="Generate built-in MIDI drum patterns",
    )
    p_patterns.add_argument("--output-dir", required=True, help="Directory to write .mid files")
    p_patterns.add_argument("--bpm", type=float, default=120.0, help="Tempo (default: 120)")

    # --- generate-dataset ---
    p_dataset = subparsers.add_parser(
        "generate-dataset",
        help="Render MIDI files into synthetic dataset",
    )
    p_dataset.add_argument("--midi-dir", required=True, help="Directory containing .mid files")
    p_dataset.add_argument("--sample-kit", required=True, help="Path to kit.json")
    p_dataset.add_argument("--output-dir", required=True, help="Output dataset directory")
    p_dataset.add_argument("--snr", type=float, default=None, help="Add white noise at this SNR (dB)")

    # --- evaluate ---
    p_eval = subparsers.add_parser(
        "evaluate",
        help="Evaluate algorithm on synthetic dataset",
    )
    p_eval.add_argument("--dataset", required=True, help="Dataset directory (from generate-dataset)")
    p_eval.add_argument("--tolerance", type=float, default=50.0, help="Matching tolerance in ms (default: 50)")
    p_eval.add_argument("--output-json", default=None, help="Write results to this JSON file")

    args = parser.parse_args()

    if args.command == "generate-patterns":
        _cmd_generate_patterns(args)
    elif args.command == "generate-dataset":
        _cmd_generate_dataset(args)
    elif args.command == "evaluate":
        _cmd_evaluate(args)


if __name__ == "__main__":
    main()
