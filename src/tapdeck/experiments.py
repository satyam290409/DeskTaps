"""Acoustic feasibility experiment runner, sample replay harness, and metrics evaluator.

Measures spatial zone classification accuracy, confusion matrices, latency distributions,
and false-positive rates under controlled acoustic test sets or replayed WAV recordings.
"""

from __future__ import annotations

import argparse
import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tapdeck.audio.feature_extractor import FeatureConfig, FeatureExtractor
from tapdeck.audio.gcc_phat import gcc_phat
from tapdeck.audio.preprocessing import BandpassFilter, FilterConfig
from tapdeck.audio.transient_detector import DetectorConfig, TransientDetector
from tapdeck.audio.zone_classifier import (
    ClassifierConfig,
    Zone,
    ZoneClassifier,
)

logger = logging.getLogger(__name__)


@dataclass
class TrialResult:
    """Detailed result of a single acoustic trial evaluation."""

    trial_id: int
    true_zone: str
    predicted_zone: str
    is_correct: bool
    delay_ms: float
    hfr: float
    confidence: float
    peak_amplitude: float
    latency_ms: float
    rejection_reason: str | None


@dataclass
class FeasibilityMetrics:
    """Aggregated classification and latency metrics for an experiment run."""

    total_trials: int
    candidate_detected: int
    detection_recall: float
    accepted_trials: int
    rejection_rate: float
    macro_f1: float
    overall_accuracy: float
    per_zone_precision: dict[str, float]
    per_zone_recall: dict[str, float]
    per_zone_f1: dict[str, float]
    confusion_matrix: dict[str, dict[str, int]]
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    false_triggers_per_hour: float


class AcousticExperimentHarness:
    """Evaluates acoustic tap localization against benchmark test signals or recordings."""

    def __init__(
        self,
        sample_rate: int = 48000,
        filter_config: FilterConfig | None = None,
        detector_config: DetectorConfig | None = None,
        classifier_config: ClassifierConfig | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.filter = BandpassFilter(filter_config or FilterConfig(sample_rate=sample_rate))
        self.detector = TransientDetector(
            detector_config
            or DetectorConfig(sample_rate=sample_rate, energy_threshold=0.0005, peak_threshold=0.02)
        )
        self.extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
        self.classifier = ZoneClassifier(
            classifier_config
            or ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0, confidence_threshold=0.5)
        )

    def evaluate_synthetic_dataset(
        self,
        trials_per_zone: int = 100,
        noise_snr_db: float = 20.0,
        seed: int = 42,
    ) -> tuple[FeasibilityMetrics, list[TrialResult]]:
        """Run controlled benchmark trials across all 4 zones with acoustic simulation.

        Zone simulation parameters:
            LT: delay < 0 (left), HFR < 1.0 (desk resonance / top)
            LB: delay < 0 (left), HFR > 1.0 (chassis impact / bottom)
            RT: delay > 0 (right), HFR < 1.0 (desk resonance / top)
            RB: delay > 0 (right), HFR > 1.0 (chassis impact / bottom)
        """
        rng = np.random.default_rng(seed)
        zones = [Zone.LT, Zone.LB, Zone.RT, Zone.RB]
        zone_names = [z.value for z in zones]

        results: list[TrialResult] = []
        latencies: list[float] = []

        trial_counter = 0

        for zone in zones:
            # Acoustic parameters based on zone physics
            # Microphone separation ~0.2m -> max delay ~0.58ms (~28 samples at 48kHz)
            is_left = zone in (Zone.LT, Zone.LB)
            is_top = zone in (Zone.LT, Zone.RT)

            base_delay_samples = -8 if is_left else 8

            for _ in range(trials_per_zone):
                trial_counter += 1
                self.detector.reset()
                t_start = time.perf_counter()

                # Add physical jitter to delay (±2 samples) and HFR (±0.2)
                delay_jitter = rng.normal(0, 1.2)
                effective_delay = base_delay_samples + delay_jitter

                # Generate synthetic transient with target HFR
                block_len = 1024
                ch1 = np.zeros(block_len, dtype=np.float32)
                ch2 = np.zeros(block_len, dtype=np.float32)

                # Transient pulse
                center = 300
                width = 8.0 if is_top else 3.0  # Top = wider envelope, Bottom = sharper click
                t_idx = np.arange(block_len)
                pulse = np.exp(-((t_idx - center) ** 2) / (2 * width**2)) * 0.4

                # High frequency component tailored for HFR
                if not is_top:
                    high_click = (
                        np.sin(2 * np.pi * 1800.0 * t_idx / self.sample_rate)
                        * 0.2
                        * np.exp(-t_idx / 100.0)
                    )
                    pulse += high_click

                ch1 = pulse.copy()

                # Shift ch2 for inter-channel delay
                shift_int = int(round(effective_delay))
                if shift_int > 0:
                    ch2[shift_int:] = pulse[:-shift_int]
                elif shift_int < 0:
                    ch2[:shift_int] = pulse[-shift_int:]
                else:
                    ch2 = pulse.copy()

                # Add noise floor based on SNR
                sig_pwr = np.mean(ch1**2)
                noise_pwr = sig_pwr / (10 ** (noise_snr_db / 10.0))
                noise = rng.normal(0, np.sqrt(noise_pwr), size=(block_len, 2)).astype(np.float32)

                stereo_tap = np.column_stack([ch1, ch2]) + noise

                # Run DSP Pipeline
                filtered = self.filter.process(stereo_tap)
                detected = self.detector.process(filtered, timestamp=trial_counter * 0.05)

                if detected is None:
                    # Missed detection
                    t_end = time.perf_counter()
                    lat_ms = (t_end - t_start) * 1000.0
                    latencies.append(lat_ms)
                    results.append(
                        TrialResult(
                            trial_id=trial_counter,
                            true_zone=zone.value,
                            predicted_zone="UNKNOWN",
                            is_correct=False,
                            delay_ms=0.0,
                            hfr=0.0,
                            confidence=0.0,
                            peak_amplitude=float(np.max(np.abs(stereo_tap))),
                            latency_ms=lat_ms,
                            rejection_reason="transient_missed",
                        )
                    )
                    continue

                gcc_res = gcc_phat(filtered[:, 0], filtered[:, 1], sample_rate=self.sample_rate)
                features = self.extractor.extract(filtered[:, 0], sample_rate=self.sample_rate)
                classification = self.classifier.classify(
                    delay_ms=gcc_res.delay_ms,
                    hfr=features.hfr,
                    confidence=gcc_res.confidence,
                )

                t_end = time.perf_counter()
                lat_ms = (t_end - t_start) * 1000.0
                latencies.append(lat_ms)

                pred_val = classification.zone.value
                is_match = pred_val == zone.value

                results.append(
                    TrialResult(
                        trial_id=trial_counter,
                        true_zone=zone.value,
                        predicted_zone=pred_val,
                        is_correct=is_match,
                        delay_ms=gcc_res.delay_ms,
                        hfr=features.hfr,
                        confidence=classification.confidence,
                        peak_amplitude=float(np.max(np.abs(stereo_tap))),
                        latency_ms=lat_ms,
                        rejection_reason=classification.rejection_reason,
                    )
                )

        # Compute Confusion Matrix and Per-Zone Metrics
        matrix: dict[str, dict[str, int]] = {
            tz: {pz: 0 for pz in zone_names + ["UNKNOWN"]} for tz in zone_names
        }

        for r in results:
            matrix[r.true_zone][r.predicted_zone] = matrix[r.true_zone].get(r.predicted_zone, 0) + 1

        precisions: dict[str, float] = {}
        recalls: dict[str, float] = {}
        f1s: dict[str, float] = {}

        for z in zone_names:
            tp = matrix[z].get(z, 0)
            fn = sum(matrix[z].values()) - tp
            fp = sum(matrix[other_z].get(z, 0) for other_z in zone_names if other_z != z)

            prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
            f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

            precisions[z] = prec
            recalls[z] = rec
            f1s[z] = f1

        macro_f1 = float(np.mean(list(f1s.values())))
        total_trials = len(results)
        total_correct = sum(1 for r in results if r.is_correct)
        overall_acc = total_correct / total_trials if total_trials > 0 else 0.0

        candidates = sum(1 for r in results if r.rejection_reason != "transient_missed")
        accepted = sum(1 for r in results if r.predicted_zone != "UNKNOWN")

        lat_arr = np.array(latencies) if latencies else np.array([0.0])

        metrics = FeasibilityMetrics(
            total_trials=total_trials,
            candidate_detected=candidates,
            detection_recall=candidates / total_trials if total_trials > 0 else 0.0,
            accepted_trials=accepted,
            rejection_rate=(total_trials - accepted) / total_trials if total_trials > 0 else 0.0,
            macro_f1=macro_f1,
            overall_accuracy=overall_acc,
            per_zone_precision=precisions,
            per_zone_recall=recalls,
            per_zone_f1=f1s,
            confusion_matrix=matrix,
            median_latency_ms=float(np.median(lat_arr)),
            p95_latency_ms=float(np.percentile(lat_arr, 95.0)),
            p99_latency_ms=float(np.percentile(lat_arr, 99.0)),
            false_triggers_per_hour=0.0,  # Measured in idle test
        )

        return metrics, results

    def run_idle_false_trigger_test(self, duration_seconds: float = 10.0) -> float:
        """Run idle stream capture test to measure false transient triggers per hour."""
        self.detector.reset()
        block_samples = 512
        num_blocks = int(duration_seconds * self.sample_rate / block_samples)
        false_triggers = 0

        # Simulate low level background white noise
        rng = np.random.default_rng(1234)
        for i in range(num_blocks):
            noise_block = rng.normal(0, 0.0005, size=(block_samples, 2)).astype(np.float32)
            filtered = self.filter.process(noise_block)
            t_sec = i * (block_samples / self.sample_rate)
            event = self.detector.process(filtered, timestamp=t_sec)
            if event is not None and not event.is_duplicate:
                false_triggers += 1

        hours = duration_seconds / 3600.0
        return float(false_triggers / hours) if hours > 0 else 0.0

    @staticmethod
    def export_csv(results: list[TrialResult], output_path: Path) -> None:
        """Export raw trial results to CSV for external analysis."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "trial_id",
                    "true_zone",
                    "predicted_zone",
                    "is_correct",
                    "delay_ms",
                    "hfr",
                    "confidence",
                    "peak_amplitude",
                    "latency_ms",
                    "rejection_reason",
                ]
            )
            for r in results:
                writer.writerow(
                    [
                        r.trial_id,
                        r.true_zone,
                        r.predicted_zone,
                        r.is_correct,
                        f"{r.delay_ms:.4f}",
                        f"{r.hfr:.4f}",
                        f"{r.confidence:.4f}",
                        f"{r.peak_amplitude:.4f}",
                        f"{r.latency_ms:.2f}",
                        r.rejection_reason or "",
                    ]
                )
        logger.info("Exported %d trial results to %s", len(results), output_path)


def run_experiment_cli() -> None:
    """CLI entry point for running Phase 1 feasibility experiments."""
    parser = argparse.ArgumentParser(description="TapDeck 2.0 Acoustic Feasibility Experiments")
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of trials per zone (default: 100)"
    )
    parser.add_argument(
        "--snr", type=float, default=20.0, help="Signal-to-noise ratio in dB (default: 20.0)"
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default="recordings/feasibility_results.csv",
        help="CSV export path",
    )
    args = parser.parse_args()

    harness = AcousticExperimentHarness()
    print("=" * 60)
    print("TAPDECK 2.0 — PHASE 1 ACOUSTIC FEASIBILITY EXPERIMENT")
    print("=" * 60)
    print(f"Target: {args.trials} trials per zone across 4 zones (total: {args.trials * 4} trials)")
    print(f"Acoustic noise condition: {args.snr} dB SNR")
    print("Running trials...")

    metrics, results = harness.evaluate_synthetic_dataset(
        trials_per_zone=args.trials, noise_snr_db=args.snr
    )
    idle_fpr = harness.run_idle_false_trigger_test(duration_seconds=10.0)
    metrics.false_triggers_per_hour = idle_fpr

    print("\n--- RESULTS SUMMARY ---")
    print(f"Macro-F1 Score:        {metrics.macro_f1 * 100:.2f}%  (Target: >= 90.0%)")
    print(f"Overall Accuracy:      {metrics.overall_accuracy * 100:.2f}%  (Target: >= 90.0%)")
    print(f"Detection Recall:      {metrics.detection_recall * 100:.2f}%  (Target: >= 95.0%)")
    print(f"Median DSP Latency:    {metrics.median_latency_ms:.2f} ms   (Target: < 200 ms)")
    print(f"P95 DSP Latency:       {metrics.p95_latency_ms:.2f} ms   (Target: < 200 ms)")
    print(
        f"Idle False Triggers:   {metrics.false_triggers_per_hour:.1f} / hour (Target: < 1.0 / hr)"
    )

    print("\n--- PER-ZONE METRICS ---")
    for z in ("left_top", "left_bottom", "right_top", "right_bottom"):
        p = metrics.per_zone_precision.get(z, 0.0) * 100
        r = metrics.per_zone_recall.get(z, 0.0) * 100
        f = metrics.per_zone_f1.get(z, 0.0) * 100
        print(f"  {z.upper():14s} -> Precision: {p:5.1f}% | Recall: {r:5.1f}% | F1: {f:5.1f}%")

    print("\n--- CONFUSION MATRIX ---")
    header = (
        "True \\ Pred".ljust(15)
        + "".join(
            f"{z.upper()[:4]:>8}" for z in ("left_top", "left_bottom", "right_top", "right_bottom")
        )
        + "   UNKNOWN"
    )
    print(header)
    for tz in ("left_top", "left_bottom", "right_top", "right_bottom"):
        row = f"{tz.upper()[:12]:15}"
        for pz in ("left_top", "left_bottom", "right_top", "right_bottom"):
            row += f"{metrics.confusion_matrix[tz].get(pz, 0):8d}"
        row += f"{metrics.confusion_matrix[tz].get('UNKNOWN', 0):10d}"
        print(row)

    csv_path = Path(args.export_csv)
    harness.export_csv(results, csv_path)
    print(f"\nDetailed CSV exported to: {csv_path.resolve()}")


if __name__ == "__main__":
    run_experiment_cli()
