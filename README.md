# HARP-VLA: Runtime Instability Analysis and Selective Recovery

中文题目：面向 VLA 机器人策略的运行时不稳定性分析与选择性恢复

## 这个项目一句话在做什么？

HARP-VLA 现在不是一个简单的“机器人失败后恢复”项目。

它现在研究的是：**VLA 机器人策略在执行过程中为什么会逐渐变得不稳定，以及系统应该什么时候恢复、怎么恢复、恢复到哪个 expert、什么时候必须示教锚定或人工复查。**

更通俗地说：

> 这个项目是在给 VLA 机器人加一个“执行时可靠性监督层”。机器人一边执行任务，一边检查自己是不是正在偏离成功轨迹。如果偏离，就判断是轻微偏移、严重失败、需要 demo anchor，还是需要 human review。

## 为什么这个项目升级了？

早期项目更像：

> VLA 失败了，我能不能把它救回来？

现在升级后的问题是：

> VLA 为什么会失败？失败是不是提前可见？什么时候该恢复？恢复强度多大？恢复到哪个策略？什么时候不能自动恢复？

这个变化很重要，因为它从一个工程恢复技巧，升级成了一个更像论文的问题：

> Runtime instability analysis and selective recovery for VLA robotic policies.

中文：面向 VLA 机器人策略的运行时不稳定性分析与选择性恢复。

## 和 RAM 的关系

RAM 更偏向 planning-side：

- 检索 object-centric spatial priors
- 让机器人在执行前更懂物体和空间关系
- 帮助规划更合理的 subgoal 或 action

HARP-VLA 更偏向 execution-side：

- 执行之后检查 subgoal 是否真的达成
- 发现 action-outcome 是否偏离
- 检索 failure-state recovery experts / demonstrations
- 决定是否轻恢复、强恢复、示教锚定或人工复查

一句漂亮的表达：

> RAM makes the robot spatially aware before execution; HARP-VLA makes the robot failure-aware during execution.

中文：

> RAM 让机器人执行前更懂空间；HARP-VLA 让机器人执行中更懂失败。

## 目前的五层研究逻辑

### 1. Embedding Instability

核心想法：

VLA 失败不是最后一步突然失败，而是在执行过程中逐渐偏离成功轨迹。

项目把这种偏离表示成：

- action-outcome embedding 远离 success manifold
- 当前状态越来越接近 failure cluster
- retrieval confidence 下降
- action-outcome residual 升高

这说明失败可以被提前观察，而不是只能事后统计。

### 2. Progress Confirmation

核心想法：

风险信号不能单独触发恢复。

如果系统只看到 risk 高就立刻恢复，可能会误干预本来可以成功的轨迹。所以 HARP-VLA 需要同时看：

- risk 是否升高
- task progress 是否停滞
- 当前状态是否真的偏离目标

这让系统从“看到风险就慌”升级成“确认进展停滞后再恢复”。

### 3. Failure-State Retrieval

核心想法：

不同失败状态不能用同一个恢复动作解决。

项目现在会根据当前失败状态去检索：

- 更像历史成功？
- 更像历史失败？
- 更像某种 demo recovery 状态？
- 更适合哪个 recovery expert？

这一步让恢复从“统一 fallback”升级成“按失败类型选择 expert”。

### 4. Demo-Anchored Recovery

核心想法：

示教不是简单 replay。

在这个项目里，demo 更像一个稳定先验：

- 当 retrieval confidence 低
- 当 residual 高
- 当 learned recovery 不稳定
- 当状态接近高风险区域

系统可以选择 demo_anchor，让恢复行为靠近可靠示教，而不是盲目继续自动恢复。

### 5. Selective Fallback / Calibration

核心想法：

恢复强度不能乱调。

过早恢复、过强恢复，可能会破坏本来能成功的轨迹；但太晚恢复，又可能已经无法挽救。所以项目现在关注：

- continue
- recover_light
- recover_strong
- demo_anchor
- human_review

也就是说，它不是只问“恢复不恢复”，而是问：

> 恢复到什么程度？什么时候恢复？什么时候不要自动恢复？

## 当前最重要的证据口径

报告里现在采用的是比较成熟、诚实的表述：

- task0 有 25 个有效 seed/init 评估
- 21/25 success
- 13 个 zero-backup successes
- 4 个有效 recovery failures
- 早期 seed1000/seed1001 的 10/10 是 initial tuned-controller evidence
- 10/10 不再被包装成最终全项目口径
- seed shift 暴露出固定阈值不够鲁棒

这很重要，因为项目没有吹成“全成功”。现在更强的说法是：

> HARP-VLA 能观察并分析 VLA 执行中的不稳定性，并将不同失败状态路由到不同恢复策略。

## 2026-06-25 这次主要升级了什么？

这次升级新增了一个 execution-time reliability layer，也就是执行期可靠性层。

它会从每个 rollout/window 中提取或派生：

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

然后训练一个 recovery route classifier。

输入：

- embedding distance
- failure-neighbor ratio
- progress slope
- action-outcome residual
- retrieval confidence
- start risk

输出：

- `continue`
- `recover_light`
- `recover_strong`
- `demo_anchor`
- `human_review`

## 每个 route 是什么意思？

### continue

当前状态还比较接近成功轨迹，任务进展正常，不需要干预。

### recover_light

当前状态轻微停滞或偏移，但还接近 success manifold。适合轻恢复。

### recover_strong

当前状态明显靠近历史失败区域，action-outcome residual 高，需要更强恢复。

### demo_anchor

当前 retrieval confidence 不够高，或者 learned recovery 不够可靠，需要用示教作为稳定先验。

### human_review

视觉状态、目标状态或风险状态无法确认，自动恢复不可信，需要人工复查。

## 这次新增了哪些可视化？

为了让工作量和解释性更直观，新增了 11 张图：

- route distribution
- feature importance
- timing ablation
- timing-by-route heatmap
- risk-confidence space
- residual-progress diagnostic space
- execution manifold PCA proxy
- route confidence histogram
- rollout trigger timeline
- decision flow diagram
- simulation-style diagnostic panels

这些图放在：

```text
outputs/voa_visual_upgrade_figures/
```

注意：其中 simulation-style diagnostic panels 是示意图，不是真实 simulator screenshot。

## 当前仓库里有哪些重要文件？

### 代码

```text
src/voa_recovery/pipeline.py
```

核心 pipeline，包括：

- 特征派生
- route label 生成
- classifier 训练
- prediction export
- route explanation
- timing ablation
- report generation

### 运行脚本

```text
scripts/run_voa_recovery_upgrade.py
scripts/validate_voa_recovery_pipeline.py
scripts/generate_voa_visuals.py
scripts/append_voa_visual_upgrade_to_docx.py
```

### 配置

```text
configs/voa_recovery_upgrade.yaml
```

### 数据模板

```text
data_templates/voa_rollout_features_template.csv
```

### 输出结果

```text
outputs/recovery_route_classifier/
outputs/recovery_timing_ablation/
outputs/voa_visual_upgrade_figures/
```

### 报告

```text
reports/representation_guided_recovery_report.md
reports/HARP_VLA_Upgraded_Full_Experiment_Report_2026-06-25_VOA_visual_upgrade.docx
```

## 当前 smoke run 的结果

当前 committed smoke run 是 synthetic validation，不是真实机器人结论。

它的作用是验证：

- pipeline 能跑通
- classifier 能训练
- metrics 能输出
- route explanations 能生成
- timing ablation 能生成
- visual figures 能生成
- Word 整合报告能插入这些图

当前 smoke metrics：

- accuracy: 0.944
- macro-F1: 0.943
- missed manual/demo escalation rate: 0.073
- false manual/demo escalation rate: 0.019

这些数字只能说明管线工作正常，不能说明真实机器人已经达到这个性能。

## 怎么运行？

### 1. 跑 synthetic smoke validation

```bash
python scripts/run_voa_recovery_upgrade.py --run-label voa_synthetic_smoke
python scripts/validate_voa_recovery_pipeline.py
python scripts/generate_voa_visuals.py
```

### 2. 接入真实 rollout CSV

```bash
python scripts/run_voa_recovery_upgrade.py --input-rollouts path/to/voa_rollout_features.csv --run-label voa_real_rollouts
python scripts/generate_voa_visuals.py
```

## 真实数据需要什么格式？

最少需要：

- `execution_status` 或 `route_label`
- `embedding_distance`
- `failure_neighbor_ratio`
- `progress_slope`
- `action_outcome_residual`
- `retrieval_confidence`
- `start_risk`

也可以提供更原始的数据，让 pipeline 自动派生特征，例如：

- `policy_embedding`
- `action_embedding`
- `state_embedding`
- `retrieved_success_embedding`
- `intended_action`
- `observed_action`
- `progress_history`
- `failure_neighbor_count`
- `success_neighbor_count`
- `retrieval_distance`
- `risk_score`

## 这个项目现在还没有证明什么？

目前还不能说：

- 真实机器人上已经显著提升成功率
- 所有任务都能泛化
- recovery threshold 已经完全校准
- human review gate 已经可以安全部署

目前能说的是：

- 项目已经从“恢复技巧”升级成“运行时可靠性分析框架”
- 它有明确的五层研究逻辑
- 它有结构化实验输出
- 它有可视化解释
- 它能接入真实 rollout 数据继续验证

## 最终项目定位

HARP-VLA 到目前为止的定位是：

> A runtime reliability layer for VLA robotic policies that detects execution instability, verifies task progress, retrieves failure-state recovery evidence, routes recovery strength, and calibrates fallback decisions.

中文：

> HARP-VLA 是一个面向 VLA 机器人策略的执行期可靠性层，用于检测运行时不稳定性、确认任务进展、检索失败状态恢复证据、选择恢复强度，并校准 fallback / demo-anchor / human-review 决策。
