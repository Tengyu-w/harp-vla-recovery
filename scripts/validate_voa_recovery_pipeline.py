from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voa_recovery.pipeline import run_pipeline


REQUIRED_OUTPUTS = [
    "outputs/recovery_route_classifier/metrics.json",
    "outputs/recovery_route_classifier/confusion_matrix.png",
    "outputs/recovery_route_classifier/feature_importance.csv",
    "outputs/recovery_route_classifier/route_predictions.csv",
    "outputs/recovery_route_classifier/route_explanations.csv",
    "outputs/recovery_timing_ablation/summary.csv",
    "outputs/recovery_timing_ablation/summary_by_route.csv",
    "reports/representation_guided_recovery_report.md",
]


def main() -> None:
    run_pipeline(
        config_path=ROOT / "configs" / "voa_recovery_upgrade.yaml",
        run_label="validation_smoke",
    )
    missing = [path for path in REQUIRED_OUTPUTS if not (ROOT / path).exists()]
    if missing:
        raise SystemExit("Missing expected outputs: " + ", ".join(missing))

    metrics = json.loads((ROOT / "outputs" / "recovery_route_classifier" / "metrics.json").read_text(encoding="utf-8-sig"))
    if metrics["n_episodes"] <= 0:
        raise SystemExit("Validation failed: n_episodes is not positive.")
    if not 0.0 <= metrics["accuracy"] <= 1.0:
        raise SystemExit("Validation failed: accuracy is outside [0, 1].")
    print("VOA recovery pipeline validation passed.")


if __name__ == "__main__":
    main()
