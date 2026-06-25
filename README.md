# HARP-VLA: Runtime Instability Analysis and Selective Recovery

中文：面向 VLA 机器人策略的运行时不稳定性分析与选择性恢复

## Overview

HARP-VLA studies how Vision-Language-Action robotic policies become unstable during execution, and how a robot should selectively recover before a failure becomes irreversible.

The project is no longer framed as simple "VLA failure recovery." Its current focus is an execution-time reliability layer that answers:

- Is the current rollout drifting away from the success manifold?
- Has task progress actually stalled?
- Which failure state does the robot resemble?
- Should the system continue, recover lightly, recover strongly, use demo anchoring, or request human review?

Core framing:

> RAM makes the robot spatially aware before execution; HARP-VLA makes the robot failure-aware during execution.

中文：

> RAM 让机器人执行前更懂空间；HARP-VLA 让机器人执行中更懂失败。

## Research Logic

HARP-VLA is organized around five ideas:

1. **Embedding instability**  
   Failures are not only terminal events. They often appear as action-outcome embeddings drifting away from the success manifold.

2. **Progress confirmation**  
   Risk alone should not trigger recovery. The system also checks whether task progress has stalled.

3. **Failure-state retrieval**  
   Different failure states require different recovery experts or demonstrations.

4. **Demo-anchored recovery**  
   Demonstrations are used as stable priors, not simple replay scripts.

5. **Selective fallback and calibration**  
   Recovery strength must be calibrated because overly early or overly strong fallback can damage otherwise recoverable trajectories.

## Current Evidence

The current report uses a conservative evidence framing:

- task0 has **25 valid seed/init evaluations**
- **21/25 success**
- **13 zero-backup successes**
- **4 effective recovery failures**
- early seed1000/1001 **10/10** is treated as initial tuned-controller evidence, not the final full-project headline
- seed shift exposes that fixed recovery thresholds are not yet robust

The main claim is therefore not "all failures are solved." The stronger and more defensible claim is:

> VLA execution instability can be observed, measured, and routed into selective recovery decisions.

## 2026-06-25 Upgrade

The latest upgrade adds a representation-guided recovery layer with:

- execution embedding features
- action-outcome residuals
- progress slope
- retrieval confidence
- failure-neighbor ratio
- risk score
- recovery route classifier
- route explanations
- recovery timing ablation
- visual diagnostic figures

Route outputs:

- `continue`
- `recover_light`
- `recover_strong`
- `demo_anchor`
- `human_review`

## Visual Outputs

The upgrade includes visual diagnostics under:

```text
outputs/voa_visual_upgrade_figures/
```

Key figures include:

- route distribution
- feature importance
- risk-confidence space
- residual-progress space
- execution manifold PCA proxy
- rollout trigger timeline
- recovery timing ablation
- route-level timing heatmap
- decision flow diagram

The simulation-style panels are schematic explanatory visuals, not real simulator screenshots.

## Repository Structure

```text
configs/                         Experiment configuration
data_templates/                  Real rollout CSV template
docs/                            Method notes and data contract
outputs/recovery_route_classifier/   Metrics, predictions, explanations
outputs/recovery_timing_ablation/    Timing ablation summaries
outputs/voa_visual_upgrade_figures/  Visual diagnostics
reports/                         Markdown report and integrated DOCX
scripts/                         Run, validate, visualize, and assemble reports
src/voa_recovery/                Core pipeline
```

## Run

Synthetic smoke run:

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

## Current Smoke Metrics

The committed smoke run validates the pipeline and visualization stack only.

- accuracy: **0.944**
- macro-F1: **0.943**
- missed manual/demo escalation rate: **0.073**
- false manual/demo escalation rate: **0.019**

These are not real robot performance claims. Real claims require logged rollout data, seed/task metadata, leakage checks, and simulator or hardware validation.

## Project Positioning

HARP-VLA is a runtime reliability layer for VLA robotic policies.

It detects execution instability, confirms task progress, retrieves failure-state recovery evidence, routes recovery strength, and calibrates fallback, demo-anchor, and human-review decisions.
