# VOA Representation-Guided Recovery Upgrade

## Goal

Upgrade the VOA manipulation project from simple post-failure recovery to an
execution-time reliability layer:

- identify the current failure state
- choose recovery strength
- decide whether demonstration anchoring is needed
- decide whether human review is safer than autonomous recovery
- estimate whether recovery timing is still effective

## Research Framing

English title:

Representation-Guided Recovery for VLA Manipulation

RAM-facing title:

Execution-Time Reliability Layer for Retrieval-Augmented Manipulation

Chinese title:

表征引导的 VLA 机器人操作恢复

Core sentence:

RAM makes the robot spatially aware before execution; HARP-VLA/VOA makes the
robot failure-aware during execution.

中文：

RAM 让机器人执行前更懂空间；VOA 的执行期可靠性层让机器人执行中更懂失败。

## Implemented Experiments

Experiment A: execution embedding extraction

- exports `outputs/recovery_route_classifier/execution_features.csv`
- supports direct features or raw columns such as embeddings, action vectors,
  progress history, retrieval distances, and neighbor counts

Experiment B: recovery route classifier

- trains a safety-biased random forest route classifier
- outputs `continue`, `recover_light`, `recover_strong`, `demo_anchor`, or
  `human_review`
- writes metrics, confusion matrix, feature importance, predictions, and
  explanations

Experiment C: recovery strength explanation

- writes per-row explanations to
  `outputs/recovery_route_classifier/route_explanations.csv`
- uses the same evidence vocabulary as the report: success manifold distance,
  failure-neighbor density, residual, confidence, and risk

Experiment D: counterfactual recovery timing

- compares immediate recovery, delayed 10 steps, delayed 40 steps, and no
  recovery
- writes global and route-level summaries under
  `outputs/recovery_timing_ablation/`

## Real Data Contract

Minimum CSV columns:

- `execution_status` or `route_label`
- `embedding_distance`
- `failure_neighbor_ratio`
- `progress_slope`
- `action_outcome_residual`
- `retrieval_confidence`
- `start_risk`

Derivable raw columns:

- `policy_embedding`
- `action_embedding`
- `state_embedding`
- `retrieved_success_embedding`
- `intended_action`
- `observed_action`
- `observed_delta`
- `progress_history`
- `progress_start`
- `progress_end`
- `failure_neighbor_count`
- `success_neighbor_count`
- `retrieval_distance`
- `success_retrieval_distance`
- `failure_retrieval_distance`
- `risk_score`
- `risk_score_start`
- `initial_risk`

Vector columns can be written as space-, comma-, or semicolon-separated values.

## Commands

Smoke run:

```bash
python scripts/run_voa_recovery_upgrade.py --run-label voa_synthetic_smoke
```

Real rollout table:

```bash
python scripts/run_voa_recovery_upgrade.py --input-rollouts path/to/voa_rollout_features.csv --run-label voa_real_rollouts
```

Template:

```text
data_templates/voa_rollout_features_template.csv
```

## Evidence Discipline

The synthetic smoke run is only a pipeline check. Real claims require real VOA
rollouts, task/seed metadata, and a leakage check that confirms the classifier
uses only execution-time information.

Before hardware-facing use, validate in simulation or logged replay. Hardware
execution is deliberately outside this upgrade package.
