from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voa_recovery.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the VOA representation-guided recovery upgrade pipeline."
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "voa_recovery_upgrade.yaml"),
        help="Path to the upgrade YAML config.",
    )
    parser.add_argument(
        "--input-rollouts",
        default=None,
        help=(
            "Optional CSV with rollout-level execution features. If omitted, "
            "the pipeline runs a synthetic smoke dataset."
        ),
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Optional label written into metrics and the report.",
    )
    args = parser.parse_args()

    result = run_pipeline(
        config_path=Path(args.config),
        input_rollouts=Path(args.input_rollouts) if args.input_rollouts else None,
        run_label=args.run_label,
    )

    print("VOA recovery upgrade pipeline completed.")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
