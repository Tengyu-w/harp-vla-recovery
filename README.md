# HARP-VLA: Runtime Instability Analysis and Selective Recovery

中文题目：面向 VLA 机器人策略的运行时不稳定性分析与选择性恢复

This repository contains the current upgraded HARP-VLA research package. The
project is no longer framed as only "VLA failure recovery"; the main research
direction is execution-time reliability for Vision-Language-Action robotic
policies.

## Core Thesis

VLA failures are not merely random terminal-step failures. They emerge as
runtime instability: action-outcome embeddings drift away from the success
manifold, task progress stalls, and retrieval confidence changes before the
episode fully fails.

HARP-VLA studies how to detect this instability, decide whether recovery is
needed, choose the correct recovery expert, and calibrate fallback strength.

RAM makes the robot spatially aware before execution; HARP-VLA makes the robot
failure-aware during execution.

中文：RAM 让机器人执行前更懂空间；HARP-VLA 让机器人执行中更懂失败。

## Five-Layer Research Logic

1. Embedding instability: failures gradually move away from the success manifold
   in action-outcome embedding space.
2. Progress confirmation: risk alone should not trigger recovery; stalled task
   progress is needed to avoid unnecessary intervention.
3. Failure-state retrieval: different failure states require different recovery
   experts.
4. Demo-anchored recovery: demonstrations are not simple replay; they provide a
   stable prior for learned recovery experts.
5. Selective fallback and calibration: recovery strength must be calibrated
   because overly strong or premature fallback can damage trajectories that
   would otherwise recover.

## Current Evidence Framing

The report preserves the mature evidence wording:

- task0 has 25 valid seed/init evaluations
- 21/25 success
- 13 zero-backup successes
- 4 effective recovery failures
- the early seed1000/1001 10/10 result is initial tuned-controller evidence,
  not the final full-project headline
- fixed thresholds are not yet robust under seed shift

This is intentionally conservative. The project claim is not "everything
succeeds"; the stronger claim is that runtime instability is measurable and can
be routed into selective recovery decisions.

## 2026-06-25 Upgrade

The latest upgrade adds an execution-time reliability layer with:

- execution embedding feature extraction
- action-outcome residuals
- retrieval confidence
- local failure-neighbor ratio
- recovery route classification
- route explanations
- counterfactual recovery timing ablation
- visual diagnostics and report integration

Route outputs:

- `continue`
- `recover_light`
- `recover_strong`
- `demo_anchor`
- `human_review`

## Repository Layout

- `src/voa_recovery/`: recovery reliability pipeline
- `scripts/`: runnable experiment, validation, visualization, and DOCX assembly scripts
- `configs/`: experiment configuration
- `data_templates/`: CSV template for real rollout features
- `outputs/`: current smoke-run metrics, figures, predictions, and timing summaries
- `reports/`: markdown report and upgraded integrated DOCX
- `docs/`: method notes and real-data contract

## Run

Synthetic smoke validation:

```bash
python scripts/run_voa_recovery_upgrade.py --run-label voa_synthetic_smoke
python scripts/validate_voa_recovery_pipeline.py
python scripts/generate_voa_visuals.py
```

Real rollout table:

```bash
python scripts/run_voa_recovery_upgrade.py --input-rollouts path/to/voa_rollout_features.csv --run-label voa_real_rollouts
python scripts/generate_voa_visuals.py
```

## Important Limitation

The committed smoke outputs validate the pipeline and visualization stack only.
They are not real robot performance claims. Real claims require logged VOA/HARP
rollouts, task and seed metadata, leakage checks, and simulator or hardware
validation.
