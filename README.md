# HARP-VLA: Runtime Instability Analysis and Selective Recovery

中文：面向 VLA 机器人策略的运行时不稳定性分析与选择性恢复

## 1. Project Motivation

Vision-Language-Action (VLA) policies can execute complex robotic tasks from visual and language inputs, but their failures are often difficult to interpret. A rollout may look acceptable for many steps, then gradually drift, stall, miss contact, or enter a state where the original policy can no longer recover.

Early versions of this project focused on the question:

> If a VLA policy fails, can we recover it?

The current version asks a deeper research question:

> How does VLA execution become unstable, and how should a robot decide when, how strongly, and through which expert to recover?

This is why the project is now framed as:

> Runtime Instability Analysis and Selective Recovery for Vision-Language-Action Robotic Policies.

The goal is not to claim that every failure is solved. The goal is to build an execution-time reliability layer that can observe instability, confirm whether intervention is needed, retrieve relevant recovery evidence, and choose an appropriate recovery route.

## 2. Relation to RAM

This project is complementary to Retrieval-Augmented Manipulation (RAM).

RAM is mainly a planning-side method:

- retrieve object-centric spatial priors
- improve spatial awareness before execution
- help the robot plan better subgoals or actions

HARP-VLA is mainly an execution-side method:

- verify whether execution actually reaches the intended subgoal
- detect action-outcome mismatch during rollout
- retrieve failure-state recovery experts or demonstrations
- decide whether to continue, recover, demo-anchor, or request human review

Core framing:

> RAM makes the robot spatially aware before execution; HARP-VLA makes the robot failure-aware during execution.

中文：

> RAM 让机器人执行前更懂空间；HARP-VLA 让机器人执行中更懂失败。

## 3. Central Research Problem

The project studies four execution-time questions:

1. **How does failure appear?**  
   Does the rollout suddenly fail, or does it gradually move away from successful behavior?

2. **When should recovery trigger?**  
   Should the system intervene immediately when risk rises, or wait until task progress also stalls?

3. **Which recovery expert should be used?**  
   Are all failures handled by one fallback policy, or should different failure states retrieve different recovery experts?

4. **How strong should recovery be?**  
   Should the robot continue, lightly recover, strongly recover, use demonstration anchoring, or stop for human review?

These questions form the full HARP-VLA logic.

## 4. Role of Runtime Instability Analysis

Runtime instability analysis is not just a classifier. It is the evidence layer that makes recovery decisions meaningful.

The classifier only answers the final routing question:

> Given the current evidence, which recovery route should be selected?

The instability analysis answers the earlier and more important diagnostic questions:

- Is the rollout moving away from normal successful execution?
- Is the action producing the expected physical outcome?
- Is task progress slowing down or stalled?
- Is the current state close to historical success, historical failure, or an uncertain region?
- Is the system still confident enough to recover autonomously?

In HARP-VLA, instability is measured through runtime signals:

- `embedding_distance`: distance from the success/recovery manifold
- `action_outcome_residual`: mismatch between intended action and observed outcome
- `progress_slope`: whether the task is still making progress
- `retrieval_confidence`: confidence that retrieved evidence matches the current state
- `failure_neighbor_ratio`: local density of historical failure states
- `start_risk` / `risk_score`: estimated recovery risk

The analysis pipeline is:

```text
rollout execution
  -> embedding drift / residual / progress / retrieval signals
  -> runtime instability evidence
  -> recovery route classifier
  -> continue / recover_light / recover_strong / demo_anchor / human_review
```

Therefore, the research contribution is not simply "classifying failures." The key contribution is making VLA execution instability visible, measurable, and actionable before the final failure state.

## 5. Method Logic

HARP-VLA is built as a five-layer reliability pipeline. Each layer solves a weakness in the previous layer.

### Layer 1: Embedding Instability

**Problem.**  
If we only look at final success or failure, we learn too late. The robot may already be unrecoverable.

**Idea.**  
VLA failure can be observed before the terminal state. During execution, action-outcome embeddings can gradually drift away from a success manifold and move closer to historical failure regions.

**Signals.**

- policy embedding
- action embedding
- state embedding
- embedding distance
- action-outcome residual
- retrieval distance

**Role in the system.**  
This layer turns failure from a binary final label into a measurable runtime instability signal.

### Layer 2: Progress Confirmation

**Problem.**  
Risk alone is not enough. A high-risk signal may appear even when the task is still progressing. Triggering recovery too early can damage trajectories that would have succeeded.

**Idea.**  
The system should confirm that task progress has stalled before escalating recovery.

**Signals.**

- progress slope
- recent subgoal progress
- action-outcome residual
- risk score

**Role in the system.**  
This layer prevents unnecessary intervention. It connects instability detection to actual task progress.

### Layer 3: Failure-State Retrieval

**Problem.**  
Different failures need different recovery behavior. A grasp slip, a visual-state mismatch, and a near-target drift should not all use the same fallback.

**Idea.**  
Retrieve historical failure states, success states, or recovery examples that are close to the current execution state.

**Signals.**

- retrieval confidence
- failure-neighbor ratio
- distance to success states
- distance to failure states

**Role in the system.**  
This layer converts "something is wrong" into "this looks like a specific type of failure."

### Layer 4: Demo-Anchored Recovery

**Problem.**  
Learned recovery can itself become unstable, especially when retrieval confidence is low or the current state is outside the reliable region.

**Idea.**  
Use demonstrations as stable priors. Demo anchoring is not simple replay; it is a way to constrain recovery toward known reliable behavior.

**When it is useful.**

- retrieval confidence is low
- action-outcome residual is high
- learned recovery has failed before
- current state is near a high-risk region

**Role in the system.**  
This layer gives the system a middle option between autonomous recovery and full human review.

### Layer 5: Selective Fallback and Calibration

**Problem.**  
Recovery strength must be calibrated. Too weak recovery may not fix the failure. Too strong or too early recovery may interrupt a trajectory that was still recoverable.

**Idea.**  
The system should select among multiple recovery routes rather than using one fixed fallback.

**Routes.**

- `continue`: keep executing
- `recover_light`: apply mild correction
- `recover_strong`: use stronger recovery
- `demo_anchor`: use demonstration-guided recovery
- `human_review`: stop automatic recovery and request review

**Role in the system.**  
This layer turns instability analysis into an actionable execution-time decision.

## 6. How the Layers Connect

The project logic is sequential:

```text
Execution rollout
  -> embedding / residual signals
  -> progress confirmation
  -> failure-state retrieval
  -> route classifier
  -> recovery strength / demo anchor / human review
```

Each layer answers a different question:

| Layer | Question | Output |
| --- | --- | --- |
| Embedding instability | Is the rollout drifting? | Runtime instability signal |
| Progress confirmation | Is the task actually stalled? | Intervention evidence |
| Failure-state retrieval | What kind of failure is this? | Similar failure/recovery evidence |
| Demo anchoring | Is autonomous recovery trustworthy? | Demonstration-guided fallback |
| Selective calibration | How strong should recovery be? | Route decision |

This is the main upgrade: HARP-VLA is no longer a single recovery trigger. It is a structured reliability layer.

## 7. Current Evidence

The current report uses a conservative evidence framing:

- task0 has **25 valid seed/init evaluations**
- **21/25 success**
- **13 zero-backup successes**
- **4 effective recovery failures**
- early seed1000/seed1001 **10/10** is treated as initial tuned-controller evidence
- the 10/10 result is not used as the final full-project headline
- seed shift exposes that fixed thresholds are not yet robust

This is important because the project does not claim "all failures are solved."

The more defensible claim is:

> VLA execution instability can be observed, measured, and routed into selective recovery decisions.

## 8. 2026-06-25 Upgrade

The latest upgrade adds a representation-guided recovery layer.

It extracts or derives:

- policy embedding norm
- action embedding norm
- state embedding norm
- embedding distance
- action-outcome residual
- progress slope
- retrieval distance
- retrieval confidence
- failure-neighbor ratio
- start risk
- risk score

These features train a recovery route classifier.

Inputs:

- embedding distance
- failure-neighbor ratio
- progress slope
- action-outcome residual
- retrieval confidence
- start risk

Outputs:

- `continue`
- `recover_light`
- `recover_strong`
- `demo_anchor`
- `human_review`

## 9. Recovery Route Interpretation

| Route | Meaning |
| --- | --- |
| `continue` | The state is still close to the success manifold and progress is acceptable. |
| `recover_light` | The state shows mild drift or progress slowdown, but is still recoverable with light correction. |
| `recover_strong` | The state is close to historical failure regions or has high action-outcome residual. |
| `demo_anchor` | Retrieval confidence is low or learned recovery is unreliable, so demonstration evidence is used as a stabilizing prior. |
| `human_review` | The visual state, goal state, or risk state is too uncertain for trusted automatic recovery. |

## 10. Visual Diagnostics

The upgrade adds visual outputs so the project is easier to inspect and explain.

Figures are stored in:

```text
outputs/voa_visual_upgrade_figures/
```

Key figures:

- route distribution
- feature importance
- risk-confidence space
- residual-progress diagnostic space
- execution manifold PCA proxy
- predicted route confidence
- rollout trigger timeline
- timing ablation
- route-level timing heatmap
- decision flow diagram
- simulation-style diagnostic panels

Note: the simulation-style panels are schematic explanatory visuals, not real simulator screenshots.

## 11. Repository Structure

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

## 12. Run

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

## 13. Current Smoke Metrics

The committed smoke run validates the pipeline and visualization stack only.

- accuracy: **0.944**
- macro-F1: **0.943**
- missed manual/demo escalation rate: **0.073**
- false manual/demo escalation rate: **0.019**

These are not real robot performance claims. Real claims require logged rollout data, seed/task metadata, leakage checks, and simulator or hardware validation.

## 14. Project Positioning

HARP-VLA is a runtime reliability layer for VLA robotic policies.

It detects execution instability, confirms task progress, retrieves failure-state recovery evidence, routes recovery strength, and calibrates fallback, demo-anchor, and human-review decisions.

中文总结：

> HARP-VLA 不是简单的失败恢复模块，而是一个执行期可靠性系统：它分析 VLA 运行时不稳定性，判断是否需要恢复，选择恢复 expert 和恢复强度，并在不确定时转向 demo anchor 或 human review。
