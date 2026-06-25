# Execution-Time Reliability Layer for VOA Manipulation

中文题目：面向VOA操作的执行期可靠性层

Generated: 2026-06-25

## Takeaway

This upgrade turns the VOA recovery project from "recover after failure" into an
execution-time reliability layer: the system uses representation distance,
action-outcome residual, retrieval confidence, local failure evidence, progress
slope, and start risk to classify the current recovery route and recovery
strength.

RAM makes the robot spatially aware before execution; HARP-VLA/VOA-style
recovery makes the robot failure-aware during execution.

中文：RAM 让机器人执行前更懂空间；VOA 的恢复可靠性层让机器人执行中更懂失败。

## Evidence Status

Current run mode: `synthetic_smoke_run`.

Source table: `generated synthetic smoke data`.

Feature export: `C:\Users\77941\Documents\github\outputs\recovery_route_classifier\execution_features.csv`.

Prediction export: `C:\Users\77941\Documents\github\outputs\recovery_route_classifier\route_predictions.csv`.

Evidence note: Synthetic smoke metrics validate the pipeline only. Replace the input table with real VOA rollouts before making empirical claims.

## Experiment A: Execution Embedding And Reliability Features

The exported execution table includes:

- policy, action, and state embedding norms
- embedding distance to the retrieved success/recovery manifold
- action-outcome residual
- progress slope
- retrieval distance and retrieval confidence
- failure-neighbor ratio
- start risk and risk score
- route explanation and safety gate

Feature derivation notes:

- All required features were provided directly.

## Experiment B: Recovery Route Classifier

Inputs:

- `embedding_distance`
- `failure_neighbor_ratio`
- `progress_slope`
- `action_outcome_residual`
- `retrieval_confidence`
- `start_risk`

Outputs:

- `continue`
- `recover_light`
- `recover_strong`
- `demo_anchor`
- `human_review`

Metrics:

- Accuracy: `0.944`
- Macro-F1: `0.943`
- Missed manual/demo-anchor escalation rate: `0.073`
- False manual/demo-anchor escalation rate: `0.019`

Generated files:

- `outputs/recovery_route_classifier/metrics.json`
- `outputs/recovery_route_classifier/confusion_matrix.png`
- `outputs/recovery_route_classifier/feature_importance.csv`
- `outputs/recovery_route_classifier/route_predictions.csv`
- `outputs/recovery_route_classifier/route_explanations.csv`

## Experiment C: Recovery Strength Explanation

The explanation layer reports:

- Light recovery: the state is still close to the success manifold, but progress has mildly stalled.
- Strong recovery: the state is close to historical failure neighborhoods and action-outcome residual is high.
- Demo-anchor fallback: retrieval confidence is low enough that demonstration evidence should anchor the recovery.
- Human review: visual state, goal state, or risk cannot be confirmed with enough confidence for automatic recovery.

## Experiment D: Timing-Sensitive Recovery Decision

Counterfactual timing policies:

| policy             | delay_steps   |   estimated_success_rate |   estimated_mean_risk |   recoverable_episode_fraction | note                                                                                   |
|:-------------------|:--------------|-------------------------:|----------------------:|-------------------------------:|:---------------------------------------------------------------------------------------|
| immediate_recovery | 0             |                 0.566387 |              0.606347 |                       0.497222 | proxy counterfactual from execution features; validate with real intervention rollouts |
| delay_10_steps     | 10            |                 0.534436 |              0.677732 |                       0.469444 | proxy counterfactual from execution features; validate with real intervention rollouts |
| delay_40_steps     | 40            |                 0.494182 |              0.807284 |                       0.366667 | proxy counterfactual from execution features; validate with real intervention rollouts |
| no_recovery        | none          |                 0.189608 |              0.666866 |                       0.166667 | proxy counterfactual from execution features; validate with real intervention rollouts |

This turns recovery from a binary trigger into a timing-sensitive decision:
"how late can the system trigger recovery before the episode is no longer
recoverable?"

Generated files:

- `outputs/recovery_timing_ablation/summary.csv`
- `outputs/recovery_timing_ablation/summary_by_route.csv`

## Contribution Framing

RAM improves spatial planning before execution, but execution can still fail
because of slip, missed contact, subgoal mismatch, or uncertain visual state.
The VOA upgrade adds:

- subgoal outcome verification
- failure-state retrieval
- risk-gated demonstration anchoring
- recovery timing decision

中文贡献表达：

RAM 提升执行前的空间规划质量；VOA 的执行期可靠性层负责执行中的失败识别、恢复强度选择、示教锚定和人工接管判断。

## Claims

Confirmed by this run:

- The representation-guided recovery pipeline is executable end to end.
- Required outputs are generated in stable locations.
- The route classifier, explanation export, and timing ablation share one feature schema.

Suggested but not proven until real VOA rollouts are used:

- Retrieval confidence and action-outcome residual can separate light recovery, strong recovery, demo anchoring, and human review cases.
- Earlier recovery should dominate delayed recovery when residual and risk grow over time.

Not yet proven:

- Real robot or simulator success-rate improvement.
- Cross-task generalization.
- Calibration of the route confidence as a deployable safety score.

## Real-Data CSV Contract

Minimum columns:

- `execution_status` or `route_label`
- `embedding_distance`
- `failure_neighbor_ratio`
- `progress_slope`
- `action_outcome_residual`
- `retrieval_confidence`
- `start_risk`

The pipeline can also derive features from raw columns such as:

- `policy_embedding`, `action_embedding`, `state_embedding`
- `retrieved_success_embedding`
- `intended_action`, `observed_action`, `observed_delta`
- `progress_history` or `progress_start`/`progress_end`
- `failure_neighbor_count`, `success_neighbor_count`
- `retrieval_distance`, `success_retrieval_distance`, `failure_retrieval_distance`
- `risk_score`, `risk_score_start`, `initial_risk`

Run:

```bash
python scripts/run_voa_recovery_upgrade.py --input-rollouts path/to/voa_rollout_features.csv --run-label voa_real_rollouts
```

## Next Real-Data Checks

- Verify that route labels do not leak future success information into execution-time features.
- Report task split, seed count, and train/test split policy.
- Add calibration and coverage-risk curves before claiming deployment readiness.
- Keep hardware-facing recovery disabled until validated in simulation or logged replay.
