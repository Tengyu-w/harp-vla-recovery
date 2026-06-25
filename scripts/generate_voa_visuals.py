from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from sklearn.decomposition import PCA


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "voa_visual_upgrade_figures"
ROUTE_DIR = ROOT / "outputs" / "recovery_route_classifier"
TIMING_DIR = ROOT / "outputs" / "recovery_timing_ablation"

PALETTE = {
    "continue": "#2E7D32",
    "recover_light": "#1976D2",
    "recover_strong": "#F57C00",
    "demo_anchor": "#7B1FA2",
    "human_review": "#C62828",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    features = pd.read_csv(ROUTE_DIR / "execution_features.csv")
    predictions = pd.read_csv(ROUTE_DIR / "route_predictions.csv")
    explanations = pd.read_csv(ROUTE_DIR / "route_explanations.csv")
    importance = pd.read_csv(ROUTE_DIR / "feature_importance.csv")
    timing = pd.read_csv(TIMING_DIR / "summary.csv")
    timing_by_route = pd.read_csv(TIMING_DIR / "summary_by_route.csv")
    metrics = json.loads((ROUTE_DIR / "metrics.json").read_text(encoding="utf-8-sig"))

    plot_route_distribution(features)
    plot_feature_importance(importance)
    plot_timing_ablation(timing)
    plot_timing_by_route(timing_by_route)
    plot_risk_confidence_space(predictions)
    plot_residual_progress_space(predictions)
    plot_manifold_proxy(features)
    plot_route_confidence(predictions)
    plot_rollout_timeline(features)
    plot_decision_flow()
    plot_simulation_diagnostic_strip(explanations)
    make_manifest(metrics)


def base_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_route_distribution(df: pd.DataFrame) -> None:
    base_style()
    counts = df["route_label"].value_counts().reindex(PALETTE.keys(), fill_value=0)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(counts.index, counts.values, color=[PALETTE[x] for x in counts.index])
    ax.set_title("Recovery Route Distribution")
    ax.set_ylabel("Episodes / windows")
    ax.set_xlabel("Route")
    ax.tick_params(axis="x", rotation=20)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{int(bar.get_height())}", ha="center", fontsize=9)
    save(fig, "fig01_route_distribution.png")


def plot_feature_importance(df: pd.DataFrame) -> None:
    base_style()
    data = df.sort_values("importance")
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.barh(data["feature"], data["importance"], color="#4C78A8")
    ax.set_title("Route Classifier Feature Importance")
    ax.set_xlabel("Random forest importance")
    save(fig, "fig02_feature_importance.png")


def plot_timing_ablation(df: pd.DataFrame) -> None:
    base_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(len(df))
    ax.plot(x, df["estimated_success_rate"], marker="o", linewidth=2.4, color="#2E7D32", label="Estimated success")
    ax.plot(x, df["recoverable_episode_fraction"], marker="s", linewidth=2.4, color="#1976D2", label="Recoverable fraction")
    ax2 = ax.twinx()
    ax2.plot(x, df["estimated_mean_risk"], marker="^", linewidth=2.2, color="#C62828", label="Mean risk")
    ax.set_xticks(x)
    ax.set_xticklabels(df["policy"], rotation=18, ha="right")
    ax.set_ylim(0, 1)
    ax2.set_ylim(0, 1)
    ax.set_ylabel("Success / recoverable")
    ax2.set_ylabel("Risk")
    ax.set_title("Counterfactual Recovery Timing Ablation")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper right", frameon=False)
    save(fig, "fig03_timing_ablation.png")


def plot_timing_by_route(df: pd.DataFrame) -> None:
    base_style()
    pivot = df.pivot(index="route_label", columns="policy", values="estimated_success_rate").reindex(PALETTE.keys())
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    im = ax.imshow(pivot.values, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_title("Timing Ablation by Route")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", color="#1A1A1A", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04, label="Estimated success")
    save(fig, "fig04_timing_by_route_heatmap.png")


def plot_risk_confidence_space(df: pd.DataFrame) -> None:
    base_style()
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    for route, group in df.groupby("predicted_route"):
        ax.scatter(
            group["retrieval_confidence"],
            group["start_risk"],
            s=38,
            alpha=0.70,
            label=route,
            color=PALETTE.get(route, "#666666"),
            edgecolor="white",
            linewidth=0.4,
        )
    ax.axvline(0.38, color="#555555", linestyle="--", linewidth=1.1, label="low-confidence gate")
    ax.axhline(0.72, color="#8D2A2A", linestyle=":", linewidth=1.2, label="high-risk gate")
    ax.set_xlabel("Retrieval confidence")
    ax.set_ylabel("Start risk")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Risk-Gated Retrieval Confidence Space")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    save(fig, "fig05_risk_confidence_space.png")


def plot_residual_progress_space(df: pd.DataFrame) -> None:
    base_style()
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    for route, group in df.groupby("predicted_route"):
        ax.scatter(
            group["action_outcome_residual"],
            group["progress_slope"],
            s=40,
            alpha=0.70,
            label=route,
            color=PALETTE.get(route, "#666666"),
            edgecolor="white",
            linewidth=0.4,
        )
    ax.set_xlabel("Action-outcome residual")
    ax.set_ylabel("Progress slope")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Residual vs. Progress Diagnostic Space")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    save(fig, "fig06_residual_progress_space.png")


def plot_manifold_proxy(df: pd.DataFrame) -> None:
    base_style()
    cols = [
        "embedding_distance",
        "failure_neighbor_ratio",
        "progress_slope",
        "action_outcome_residual",
        "retrieval_confidence",
        "start_risk",
    ]
    x = df[cols].to_numpy()
    coords = PCA(n_components=2, random_state=46).fit_transform(x)
    plot_df = df.copy()
    plot_df["pc1"] = coords[:, 0]
    plot_df["pc2"] = coords[:, 1]
    fig, ax = plt.subplots(figsize=(7.6, 5.8))
    for route, group in plot_df.groupby("route_label"):
        ax.scatter(
            group["pc1"],
            group["pc2"],
            s=38,
            alpha=0.70,
            label=route,
            color=PALETTE.get(route, "#666666"),
            edgecolor="white",
            linewidth=0.4,
        )
    ax.set_title("Execution Representation Space (PCA Proxy)")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(frameon=False, fontsize=8, loc="best")
    save(fig, "fig07_execution_manifold_proxy.png")


def plot_route_confidence(df: pd.DataFrame) -> None:
    base_style()
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bins = np.linspace(0, 1, 16)
    for route, group in df.groupby("predicted_route"):
        ax.hist(group["route_confidence"], bins=bins, alpha=0.50, label=route, color=PALETTE.get(route, "#666666"))
    ax.set_title("Predicted Route Confidence")
    ax.set_xlabel("Classifier confidence")
    ax.set_ylabel("Count")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig08_route_confidence_histogram.png")


def plot_rollout_timeline(df: pd.DataFrame) -> None:
    base_style()
    samples = []
    for route in PALETTE:
        group = df[df["route_label"] == route]
        if not group.empty:
            samples.append(group.iloc[0])
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    y_positions = np.arange(len(samples))
    for y, row in zip(y_positions, samples):
        horizon = int(row.get("episode_horizon", 96))
        failure = int(row.get("failure_step", horizon // 2))
        route = row["route_label"]
        ax.plot([0, horizon], [y, y], color="#DDDDDD", linewidth=8, solid_capstyle="round")
        ax.plot([0, failure], [y, y], color="#90CAF9", linewidth=8, solid_capstyle="round")
        if route != "continue":
            ax.plot([failure, horizon], [y, y], color=PALETTE.get(route, "#888888"), linewidth=8, solid_capstyle="round")
            ax.scatter([failure], [y], s=120, color=PALETTE.get(route, "#888888"), edgecolor="white", zorder=4)
            ax.text(failure + 1, y + 0.15, route, fontsize=8, color="#222222")
        else:
            ax.text(horizon * 0.62, y + 0.15, "continue", fontsize=8, color="#222222")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([row["execution_status"] for row in samples])
    ax.set_xlabel("Execution step")
    ax.set_title("Example Rollout Timeline and Route Trigger")
    ax.set_ylim(-0.6, len(samples) - 0.4)
    save(fig, "fig09_rollout_timeline.png")


def plot_decision_flow() -> None:
    base_style()
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    ax.axis("off")
    boxes = [
        ("Execution window", 0.05, 0.63, "#E3F2FD"),
        ("Embedding / residual\nretrieval features", 0.27, 0.63, "#E8F5E9"),
        ("Route classifier", 0.52, 0.63, "#FFF3E0"),
        ("Recovery action", 0.75, 0.63, "#F3E5F5"),
        ("Timing ablation:\nnow / +10 / +40 / none", 0.52, 0.20, "#FCE4EC"),
    ]
    for text, x, y, color in boxes:
        patch = FancyBboxPatch((x, y), 0.18, 0.18, boxstyle="round,pad=0.02,rounding_size=0.015", fc=color, ec="#555555", lw=1.2)
        ax.add_patch(patch)
        ax.text(x + 0.09, y + 0.09, text, ha="center", va="center", fontsize=10)
    arrows = [((0.23, 0.72), (0.27, 0.72)), ((0.45, 0.72), (0.52, 0.72)), ((0.70, 0.72), (0.75, 0.72)), ((0.61, 0.63), (0.61, 0.40))]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14, lw=1.5, color="#444444"))
    ax.text(0.75, 0.38, "continue\nrecover_light\nrecover_strong\ndemo_anchor\nhuman_review", fontsize=10, va="top")
    ax.set_title("Representation-Guided Recovery Decision Flow", fontsize=14, fontweight="bold")
    save(fig, "fig10_decision_flow.png")


def plot_simulation_diagnostic_strip(df: pd.DataFrame) -> None:
    base_style()
    fig, axes = plt.subplots(1, 4, figsize=(10.2, 3.2))
    titles = ["1. nominal approach", "2. slip / residual", "3. retrieval route", "4. recovery gate"]
    routes = ["continue", "recover_strong", "demo_anchor", "human_review"]
    for ax, title, route in zip(axes, titles, routes):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(Rectangle((0.05, 0.08), 0.90, 0.12, fc="#ECEFF1", ec="#B0BEC5"))
        ax.add_patch(Circle((0.65, 0.38), 0.08, fc="#FFCC80", ec="#EF6C00", lw=1.4))
        gripper_x = {"continue": 0.45, "recover_strong": 0.36, "demo_anchor": 0.50, "human_review": 0.28}[route]
        ax.plot([gripper_x, gripper_x + 0.09], [0.70, 0.48], color="#37474F", lw=4)
        ax.plot([gripper_x + 0.09, gripper_x + 0.18], [0.48, 0.52], color="#37474F", lw=3)
        ax.scatter([gripper_x + 0.18], [0.52], s=60, color=PALETTE[route])
        ax.text(0.5, 0.93, title, ha="center", fontsize=9, fontweight="bold")
        ax.text(0.5, 0.02, route, ha="center", fontsize=8, color=PALETTE[route])
        if route in {"recover_strong", "demo_anchor", "human_review"}:
            ax.add_patch(FancyArrowPatch((0.20, 0.30), (0.47, 0.48), arrowstyle="-|>", mutation_scale=12, color=PALETTE[route], lw=1.6))
    fig.suptitle("Simulation-Style Diagnostic Panels (schematic, not real simulator frames)", fontsize=12, fontweight="bold")
    save(fig, "fig11_simulation_style_diagnostics.png")


def make_manifest(metrics: dict) -> None:
    rows = [
        ("fig01_route_distribution.png", "Route distribution across synthetic smoke execution windows."),
        ("fig02_feature_importance.png", "Feature importance for the recovery route classifier."),
        ("fig03_timing_ablation.png", "Counterfactual recovery timing comparison."),
        ("fig04_timing_by_route_heatmap.png", "Timing sensitivity broken down by route."),
        ("fig05_risk_confidence_space.png", "Risk-gated retrieval confidence space."),
        ("fig06_residual_progress_space.png", "Action-outcome residual versus progress slope."),
        ("fig07_execution_manifold_proxy.png", "PCA proxy of the execution representation space."),
        ("fig08_route_confidence_histogram.png", "Predicted route confidence distribution."),
        ("fig09_rollout_timeline.png", "Example rollout trigger timeline."),
        ("fig10_decision_flow.png", "Representation-guided recovery decision flow."),
        ("fig11_simulation_style_diagnostics.png", "Schematic diagnostic panels; not real simulator screenshots."),
    ]
    manifest = pd.DataFrame(rows, columns=["file", "caption"])
    manifest["metrics_run_label"] = metrics.get("run_label", "")
    manifest.to_csv(OUT / "figure_manifest.csv", index=False)


if __name__ == "__main__":
    main()
