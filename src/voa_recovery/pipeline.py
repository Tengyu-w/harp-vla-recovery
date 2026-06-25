from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split


ROUTE_FEATURES = [
    "embedding_distance",
    "failure_neighbor_ratio",
    "progress_slope",
    "action_outcome_residual",
    "retrieval_confidence",
    "start_risk",
]

EXTRACTED_FEATURES = [
    "policy_embedding_norm",
    "action_embedding_norm",
    "state_embedding_norm",
    "action_outcome_residual",
    "progress_slope",
    "retrieval_distance",
    "retrieval_confidence",
    "risk_score",
]

EXECUTION_STATUS = [
    "clean_success",
    "natural_failure",
    "learned_recovery_success",
    "learned_recovery_failure",
    "anchored_recovery_success",
    "human_review_needed",
]

ROUTES = [
    "continue",
    "recover_light",
    "recover_strong",
    "demo_anchor",
    "human_review",
]

MANUAL_OR_ANCHOR_ROUTES = {"demo_anchor", "human_review"}


@dataclass(frozen=True)
class PipelinePaths:
    route_dir: Path
    timing_dir: Path
    report_path: Path


def run_pipeline(
    config_path: Path,
    input_rollouts: Path | None = None,
    run_label: str | None = None,
) -> dict[str, str]:
    root = config_path.resolve().parents[1]
    config = _load_config(config_path)
    paths = _resolve_paths(root, config)
    paths.route_dir.mkdir(parents=True, exist_ok=True)
    paths.timing_dir.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    config_input = config.get("data", {}).get("input_rollouts")
    if input_rollouts is None and config_input:
        input_rollouts = (root / config_input).resolve()

    if input_rollouts:
        raw_df = _load_real_rollouts(input_rollouts)
        dataset_mode = "real_rollout_table"
        source_path = str(input_rollouts)
    else:
        seed = int(config.get("data", {}).get("random_seed", 46))
        n = int(config.get("data", {}).get("n_synthetic_episodes", 360))
        raw_df = make_synthetic_rollouts(n=n, seed=seed)
        dataset_mode = "synthetic_smoke_run"
        source_path = "generated synthetic smoke data"

    df, derivation_notes = prepare_execution_features(raw_df)
    _validate_input_columns(df)

    feature_table_path = paths.route_dir / "execution_features.csv"
    df.to_csv(feature_table_path, index=False)

    model, metrics, predictions = train_route_classifier(
        df=df,
        test_size=float(config.get("data", {}).get("test_size", 0.30)),
        seed=int(config.get("data", {}).get("random_seed", 46)),
        output_dir=paths.route_dir,
        run_label=run_label or dataset_mode,
        dataset_mode=dataset_mode,
        derivation_notes=derivation_notes,
    )

    timing_summary = run_timing_ablation(df=df, output_dir=paths.timing_dir)
    report_text = build_report(
        config=config,
        metrics=metrics,
        timing_summary=timing_summary,
        dataset_mode=dataset_mode,
        source_path=source_path,
        feature_table_path=feature_table_path,
        predictions_path=paths.route_dir / "route_predictions.csv",
        derivation_notes=derivation_notes,
    )
    paths.report_path.write_text(report_text, encoding="utf-8-sig")

    return {
        "features": str(feature_table_path),
        "metrics": str(paths.route_dir / "metrics.json"),
        "confusion_matrix": str(paths.route_dir / "confusion_matrix.png"),
        "feature_importance": str(paths.route_dir / "feature_importance.csv"),
        "predictions": str(paths.route_dir / "route_predictions.csv"),
        "route_explanations": str(paths.route_dir / "route_explanations.csv"),
        "timing_summary": str(paths.timing_dir / "summary.csv"),
        "timing_by_route": str(paths.timing_dir / "summary_by_route.csv"),
        "report": str(paths.report_path),
    }


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}


def _resolve_paths(root: Path, config: dict[str, Any]) -> PipelinePaths:
    outputs = config.get("outputs", {})
    return PipelinePaths(
        route_dir=(root / outputs.get("route_classifier_dir", "outputs/recovery_route_classifier")).resolve(),
        timing_dir=(root / outputs.get("timing_ablation_dir", "outputs/recovery_timing_ablation")).resolve(),
        report_path=(root / outputs.get("report_path", "reports/representation_guided_recovery_report.md")).resolve(),
    )


def _load_real_rollouts(input_rollouts: Path) -> pd.DataFrame:
    if not input_rollouts.exists():
        raise FileNotFoundError(f"Input rollout table not found: {input_rollouts}")
    if input_rollouts.suffix.lower() != ".csv":
        raise ValueError("The VOA recovery upgrade currently expects a CSV rollout table.")
    return pd.read_csv(input_rollouts)


def prepare_execution_features(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = raw_df.copy()
    notes: list[str] = []

    if "episode_id" not in df.columns:
        df.insert(0, "episode_id", [f"episode_{idx:04d}" for idx in range(len(df))])
        notes.append("episode_id was generated from row index.")

    _derive_norm_feature(df, "policy_embedding", "policy_embedding_norm", notes)
    _derive_norm_feature(df, "action_embedding", "action_embedding_norm", notes)
    _derive_norm_feature(df, "state_embedding", "state_embedding_norm", notes)
    _derive_embedding_distance(df, notes)
    _derive_action_outcome_residual(df, notes)
    _derive_progress_slope(df, notes)
    _derive_failure_neighbor_ratio(df, notes)
    _derive_retrieval_confidence(df, notes)
    _derive_risk_features(df, notes)

    if "execution_status" not in df.columns:
        if "route_label" not in df.columns:
            raise ValueError("Provide execution_status, route_label, or both for the route classifier.")
        df["execution_status"] = "unlabeled_execution"
        notes.append("execution_status was not provided; rows were marked as unlabeled_execution.")

    if "route_label" not in df.columns:
        df["route_label"] = [_route_from_status_and_features(status, row) for status, (_, row) in zip(df["execution_status"], df.iterrows())]
        notes.append("route_label was generated with the risk-gated routing heuristic.")

    for col in ROUTE_FEATURES + EXTRACTED_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    missing_before_fill = {
        col: int(df[col].isna().sum())
        for col in ROUTE_FEATURES
        if col in df.columns and int(df[col].isna().sum()) > 0
    }
    if missing_before_fill:
        for col, count in missing_before_fill.items():
            fill_value = float(df[col].median()) if not df[col].dropna().empty else 0.5
            df[col] = df[col].fillna(fill_value)
            notes.append(f"{col} had {count} missing values filled with median {fill_value:.3f}.")

    df["route_explanation"] = [explain_route(row) for _, row in df.iterrows()]
    df["safety_gate"] = [
        "manual_or_anchor" if route in MANUAL_OR_ANCHOR_ROUTES else "automatic"
        for route in df["route_label"]
    ]
    return df, notes


def _validate_input_columns(df: pd.DataFrame) -> None:
    required = set(ROUTE_FEATURES + ["execution_status", "route_label"])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            "Rollout table is missing required columns after feature derivation: "
            + ", ".join(missing)
            + ". Required classifier features are: "
            + ", ".join(ROUTE_FEATURES)
        )


def _derive_norm_feature(df: pd.DataFrame, vector_col: str, norm_col: str, notes: list[str]) -> None:
    if norm_col in df.columns:
        return
    if vector_col not in df.columns:
        return
    df[norm_col] = [_vector_norm(_parse_vector(value)) for value in df[vector_col]]
    notes.append(f"{norm_col} was derived from {vector_col}.")


def _derive_embedding_distance(df: pd.DataFrame, notes: list[str]) -> None:
    if "embedding_distance" in df.columns:
        return
    success_cols = ["retrieved_success_embedding", "nearest_success_embedding", "success_embedding"]
    success_col = next((col for col in success_cols if col in df.columns), None)
    if "state_embedding" in df.columns and success_col:
        df["embedding_distance"] = [
            _vector_distance(_parse_vector(state), _parse_vector(success))
            for state, success in zip(df["state_embedding"], df[success_col])
        ]
        notes.append(f"embedding_distance was derived from state_embedding and {success_col}.")
        return
    if "retrieval_distance" in df.columns:
        df["embedding_distance"] = pd.to_numeric(df["retrieval_distance"], errors="coerce")
        notes.append("embedding_distance was copied from retrieval_distance.")


def _derive_action_outcome_residual(df: pd.DataFrame, notes: list[str]) -> None:
    if "action_outcome_residual" in df.columns:
        return
    action_pairs = [
        ("intended_action", "observed_action"),
        ("intended_action", "observed_delta"),
        ("commanded_action", "observed_delta"),
    ]
    for intended_col, observed_col in action_pairs:
        if intended_col in df.columns and observed_col in df.columns:
            df["action_outcome_residual"] = [
                _vector_distance(_parse_vector(intended), _parse_vector(observed))
                for intended, observed in zip(df[intended_col], df[observed_col])
            ]
            notes.append(f"action_outcome_residual was derived from {intended_col} and {observed_col}.")
            return


def _derive_progress_slope(df: pd.DataFrame, notes: list[str]) -> None:
    if "progress_slope" in df.columns:
        return
    if "progress_history" in df.columns:
        df["progress_slope"] = [_progress_slope(_parse_vector(value)) for value in df["progress_history"]]
        notes.append("progress_slope was derived from progress_history.")
        return
    if {"progress_start", "progress_end"}.issubset(df.columns):
        denom = pd.to_numeric(df.get("window_steps", 1), errors="coerce").fillna(1).clip(lower=1)
        df["progress_slope"] = (
            pd.to_numeric(df["progress_end"], errors="coerce") - pd.to_numeric(df["progress_start"], errors="coerce")
        ) / denom
        df["progress_slope"] = df["progress_slope"].map(lambda value: _clip(float(value), -1.0, 1.0))
        notes.append("progress_slope was derived from progress_start/progress_end.")


def _derive_failure_neighbor_ratio(df: pd.DataFrame, notes: list[str]) -> None:
    if "failure_neighbor_ratio" in df.columns:
        return
    if {"failure_neighbor_count", "success_neighbor_count"}.issubset(df.columns):
        failure = pd.to_numeric(df["failure_neighbor_count"], errors="coerce").fillna(0)
        success = pd.to_numeric(df["success_neighbor_count"], errors="coerce").fillna(0)
        denom = (failure + success).replace(0, np.nan)
        df["failure_neighbor_ratio"] = (failure / denom).fillna(0.5)
        notes.append("failure_neighbor_ratio was derived from neighbor counts.")


def _derive_retrieval_confidence(df: pd.DataFrame, notes: list[str]) -> None:
    if "retrieval_distance" not in df.columns and "embedding_distance" in df.columns:
        df["retrieval_distance"] = df["embedding_distance"]
        notes.append("retrieval_distance was copied from embedding_distance.")

    if "retrieval_confidence" in df.columns:
        return
    if {"success_retrieval_distance", "failure_retrieval_distance"}.issubset(df.columns):
        success = pd.to_numeric(df["success_retrieval_distance"], errors="coerce")
        failure = pd.to_numeric(df["failure_retrieval_distance"], errors="coerce")
        df["retrieval_confidence"] = 1.0 / (1.0 + np.exp(4.0 * (success - failure)))
        notes.append("retrieval_confidence was derived from success/failure retrieval distances.")
        return
    if "retrieval_distance" in df.columns:
        distance = pd.to_numeric(df["retrieval_distance"], errors="coerce")
        df["retrieval_confidence"] = np.exp(-3.0 * distance).clip(0.0, 1.0)
        notes.append("retrieval_confidence was derived from retrieval_distance.")


def _derive_risk_features(df: pd.DataFrame, notes: list[str]) -> None:
    if "start_risk" not in df.columns:
        for candidate in ["risk_score_start", "initial_risk", "risk_score"]:
            if candidate in df.columns:
                df["start_risk"] = pd.to_numeric(df[candidate], errors="coerce")
                notes.append(f"start_risk was copied from {candidate}.")
                break

    if "risk_score" not in df.columns and all(col in df.columns for col in ["action_outcome_residual", "retrieval_confidence", "failure_neighbor_ratio", "progress_slope"]):
        df["risk_score"] = (
            0.34 * pd.to_numeric(df["action_outcome_residual"], errors="coerce")
            + 0.26 * (1.0 - pd.to_numeric(df["retrieval_confidence"], errors="coerce"))
            + 0.24 * pd.to_numeric(df["failure_neighbor_ratio"], errors="coerce")
            + 0.16 * (1.0 - pd.to_numeric(df["progress_slope"], errors="coerce").clip(0.0, 1.0))
        ).clip(0.0, 1.0)
        notes.append("risk_score was derived from residual, retrieval confidence, failure-neighbor ratio, and progress slope.")

    if "start_risk" not in df.columns and "risk_score" in df.columns:
        df["start_risk"] = df["risk_score"]
        notes.append("start_risk was copied from derived risk_score.")


def make_synthetic_rollouts(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    statuses = np.resize(np.array(EXECUTION_STATUS), n)
    rng.shuffle(statuses)

    rows: list[dict[str, Any]] = []
    for episode_id, status in enumerate(statuses):
        profile = _sample_status_profile(status, rng)
        route_label = _route_from_status_and_features(status, pd.Series(profile))
        row = {
            "episode_id": f"smoke_{episode_id:04d}",
            "execution_status": status,
            "route_label": route_label,
            "policy_embedding_norm": _clip(rng.normal(profile["policy_embedding_norm"], 0.06)),
            "action_embedding_norm": _clip(rng.normal(profile["action_embedding_norm"], 0.07)),
            "state_embedding_norm": _clip(rng.normal(profile["state_embedding_norm"], 0.06)),
            "embedding_distance": _clip(rng.normal(profile["embedding_distance"], 0.07)),
            "failure_neighbor_ratio": _clip(rng.normal(profile["failure_neighbor_ratio"], 0.08)),
            "progress_slope": _clip(rng.normal(profile["progress_slope"], 0.08)),
            "action_outcome_residual": _clip(rng.normal(profile["action_outcome_residual"], 0.08)),
            "retrieval_distance": _clip(rng.normal(profile["retrieval_distance"], 0.07)),
            "retrieval_confidence": _clip(rng.normal(profile["retrieval_confidence"], 0.07)),
            "start_risk": _clip(rng.normal(profile["start_risk"], 0.08)),
            "risk_score": _clip(rng.normal(profile["risk_score"], 0.08)),
            "failure_step": int(rng.integers(8, 72)),
            "episode_horizon": 96,
        }
        row["route_explanation"] = explain_route(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _sample_status_profile(status: str, rng: np.random.Generator) -> dict[str, float]:
    profiles = {
        "clean_success": {
            "policy_embedding_norm": 0.35,
            "action_embedding_norm": 0.32,
            "state_embedding_norm": 0.30,
            "embedding_distance": 0.18,
            "failure_neighbor_ratio": 0.08,
            "progress_slope": 0.82,
            "action_outcome_residual": 0.12,
            "retrieval_distance": 0.18,
            "retrieval_confidence": 0.88,
            "start_risk": 0.10,
            "risk_score": 0.10,
        },
        "natural_failure": {
            "policy_embedding_norm": 0.56,
            "action_embedding_norm": 0.62,
            "state_embedding_norm": 0.58,
            "embedding_distance": 0.62,
            "failure_neighbor_ratio": 0.62,
            "progress_slope": 0.24,
            "action_outcome_residual": 0.70,
            "retrieval_distance": 0.65,
            "retrieval_confidence": 0.36,
            "start_risk": 0.60,
            "risk_score": 0.65,
        },
        "learned_recovery_success": {
            "policy_embedding_norm": 0.42,
            "action_embedding_norm": 0.42,
            "state_embedding_norm": 0.38,
            "embedding_distance": 0.34,
            "failure_neighbor_ratio": 0.26,
            "progress_slope": 0.52,
            "action_outcome_residual": 0.34,
            "retrieval_distance": 0.36,
            "retrieval_confidence": 0.68,
            "start_risk": 0.30,
            "risk_score": 0.33,
        },
        "learned_recovery_failure": {
            "policy_embedding_norm": 0.66,
            "action_embedding_norm": 0.70,
            "state_embedding_norm": 0.64,
            "embedding_distance": 0.72,
            "failure_neighbor_ratio": 0.74,
            "progress_slope": 0.18,
            "action_outcome_residual": 0.78,
            "retrieval_distance": 0.72,
            "retrieval_confidence": 0.30,
            "start_risk": 0.72,
            "risk_score": 0.78,
        },
        "anchored_recovery_success": {
            "policy_embedding_norm": 0.48,
            "action_embedding_norm": 0.50,
            "state_embedding_norm": 0.46,
            "embedding_distance": 0.48,
            "failure_neighbor_ratio": 0.42,
            "progress_slope": 0.38,
            "action_outcome_residual": 0.50,
            "retrieval_distance": 0.50,
            "retrieval_confidence": 0.46,
            "start_risk": 0.50,
            "risk_score": 0.52,
        },
        "human_review_needed": {
            "policy_embedding_norm": 0.74,
            "action_embedding_norm": 0.75,
            "state_embedding_norm": 0.76,
            "embedding_distance": 0.82,
            "failure_neighbor_ratio": 0.82,
            "progress_slope": 0.12,
            "action_outcome_residual": 0.84,
            "retrieval_distance": 0.84,
            "retrieval_confidence": 0.18,
            "start_risk": 0.86,
            "risk_score": 0.88,
        },
    }
    profile = profiles[status].copy()
    for key, value in profile.items():
        profile[key] = float(_clip(rng.normal(value, 0.035)))
    return profile


def _route_from_status_and_features(status: str, row: pd.Series | dict[str, Any]) -> str:
    if status == "clean_success":
        return "continue"
    if status == "learned_recovery_success":
        progress = float(row.get("progress_slope", 0.5))
        residual = float(row.get("action_outcome_residual", 0.5))
        return "recover_light" if progress >= 0.42 and residual < 0.46 else "recover_strong"
    if status == "natural_failure":
        confidence = float(row.get("retrieval_confidence", 0.5))
        risk = float(row.get("start_risk", row.get("risk_score", 0.5)))
        if confidence < 0.30 or risk > 0.76:
            return "human_review"
        return "recover_strong"
    if status == "learned_recovery_failure":
        confidence = float(row.get("retrieval_confidence", 0.5))
        risk = float(row.get("start_risk", row.get("risk_score", 0.5)))
        failure_ratio = float(row.get("failure_neighbor_ratio", 0.5))
        if confidence < 0.34 or risk > 0.78 or failure_ratio > 0.78:
            return "human_review"
        return "demo_anchor"
    if status == "anchored_recovery_success":
        return "demo_anchor"
    if status == "human_review_needed":
        return "human_review"
    return _route_from_features(row)


def _route_from_features(row: pd.Series | dict[str, Any]) -> str:
    confidence = float(row.get("retrieval_confidence", 0.5))
    risk = float(row.get("start_risk", row.get("risk_score", 0.5)))
    residual = float(row.get("action_outcome_residual", 0.5))
    progress = float(row.get("progress_slope", 0.5))
    failure_ratio = float(row.get("failure_neighbor_ratio", 0.5))
    embedding_distance = float(row.get("embedding_distance", 0.5))

    if confidence < 0.32 and risk > 0.65:
        return "human_review"
    if confidence < 0.42 and (risk > 0.50 or failure_ratio > 0.52):
        return "demo_anchor"
    if residual > 0.58 or failure_ratio > 0.58 or embedding_distance > 0.62:
        return "recover_strong"
    if progress < 0.55 or residual > 0.32:
        return "recover_light"
    return "continue"


def train_route_classifier(
    df: pd.DataFrame,
    test_size: float,
    seed: int,
    output_dir: Path,
    run_label: str,
    dataset_mode: str,
    derivation_notes: list[str],
) -> tuple[RandomForestClassifier, dict[str, Any], pd.DataFrame]:
    x = df[ROUTE_FEATURES]
    y = df["route_label"]
    stratify = y if y.value_counts().min() >= 2 else None
    indices = np.arange(len(df))
    x_train, x_test, y_train, y_test, idx_train, idx_test = train_test_split(
        x,
        y,
        indices,
        test_size=test_size,
        random_state=seed,
        stratify=stratify,
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=seed,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)

    labels = [route for route in ROUTES if route in sorted(set(y_test) | set(y_pred))]
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    _plot_confusion_matrix(cm, labels, output_dir / "confusion_matrix.png")

    importance = (
        pd.DataFrame({"feature": ROUTE_FEATURES, "importance": model.feature_importances_})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    importance["rank"] = np.arange(1, len(importance) + 1)
    importance["interpretation"] = importance["feature"].map(_feature_interpretation)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)

    predictions = _build_prediction_table(df, model, idx_train, idx_test)
    predictions.to_csv(output_dir / "route_predictions.csv", index=False)
    predictions[
        [
            "episode_id",
            "execution_status",
            "route_label",
            "predicted_route",
            "route_confidence",
            "predicted_route_explanation",
            "route_explanation",
            "safety_gate",
            "predicted_safety_gate",
        ]
    ].to_csv(output_dir / "route_explanations.csv", index=False)

    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    metrics = {
        "run_label": run_label,
        "generated_on": date.today().isoformat(),
        "dataset_mode": dataset_mode,
        "n_episodes": int(len(df)),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "features": ROUTE_FEATURES,
        "extracted_features": EXTRACTED_FEATURES,
        "labels": labels,
        "status_distribution": _value_counts(df["execution_status"]),
        "route_distribution": _value_counts(df["route_label"]),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "macro_f1": float(f1_score(y_test, y_pred, average="macro")),
        "per_class": report,
        "confusion_matrix": {"labels": labels, "matrix": cm.astype(int).tolist()},
        "missed_manual_or_anchor_rate": _missed_escalation_rate(y_test, y_pred),
        "false_manual_or_anchor_rate": _false_escalation_rate(y_test, y_pred),
        "decision_outputs": ROUTES,
        "feature_derivation_notes": derivation_notes,
        "evidence_note": _evidence_note(dataset_mode),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8-sig",
    )
    return model, metrics, predictions


def _build_prediction_table(df: pd.DataFrame, model: RandomForestClassifier, idx_train: np.ndarray, idx_test: np.ndarray) -> pd.DataFrame:
    table = df.copy()
    table["split"] = "unused"
    table.loc[idx_train, "split"] = "train"
    table.loc[idx_test, "split"] = "test"

    probabilities = model.predict_proba(table[ROUTE_FEATURES])
    classes = list(model.classes_)
    predicted_indices = probabilities.argmax(axis=1)
    table["predicted_route"] = [classes[idx] for idx in predicted_indices]
    table["route_confidence"] = probabilities.max(axis=1)
    table["predicted_safety_gate"] = [
        "manual_or_anchor" if route in MANUAL_OR_ANCHOR_ROUTES else "automatic"
        for route in table["predicted_route"]
    ]
    for class_idx, class_name in enumerate(classes):
        table[f"prob_{class_name}"] = probabilities[:, class_idx]
    table["predicted_route_explanation"] = [explain_route({**row.to_dict(), "route_label": row["predicted_route"]}) for _, row in table.iterrows()]
    return table


def _plot_confusion_matrix(cm: np.ndarray, labels: list[str], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 7))
    ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels).plot(
        ax=ax,
        cmap="Blues",
        colorbar=False,
        xticks_rotation=35,
    )
    ax.set_title("VOA Recovery Route Classifier")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _missed_escalation_rate(y_true: pd.Series, y_pred: np.ndarray) -> float:
    true_manual = y_true.isin(MANUAL_OR_ANCHOR_ROUTES).to_numpy()
    if true_manual.sum() == 0:
        return 0.0
    pred_auto = np.array([pred not in MANUAL_OR_ANCHOR_ROUTES for pred in y_pred])
    return float((true_manual & pred_auto).sum() / true_manual.sum())


def _false_escalation_rate(y_true: pd.Series, y_pred: np.ndarray) -> float:
    true_auto = ~y_true.isin(MANUAL_OR_ANCHOR_ROUTES).to_numpy()
    if true_auto.sum() == 0:
        return 0.0
    pred_manual = np.array([pred in MANUAL_OR_ANCHOR_ROUTES for pred in y_pred])
    return float((true_auto & pred_manual).sum() / true_auto.sum())


def _feature_interpretation(feature: str) -> str:
    return {
        "embedding_distance": "Distance from retrieved success/recovery manifold.",
        "failure_neighbor_ratio": "Local density of historical failure neighbors.",
        "progress_slope": "Recent task-progress trend; low slope means stalled execution.",
        "action_outcome_residual": "Mismatch between intended action and observed outcome.",
        "retrieval_confidence": "Confidence that retrieval evidence matches the current state.",
        "start_risk": "Risk estimate at the beginning of the recovery decision window.",
    }[feature]


def run_timing_ablation(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    policies = [
        ("immediate_recovery", 0),
        ("delay_10_steps", 10),
        ("delay_40_steps", 40),
        ("no_recovery", None),
    ]
    rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    for policy, delay in policies:
        success_probs = []
        risk_probs = []
        by_route: dict[str, list[tuple[float, float]]] = {route: [] for route in ROUTES}
        for _, row in df.iterrows():
            success_prob, risk_prob = _counterfactual_success_and_risk(row, delay)
            success_probs.append(success_prob)
            risk_probs.append(risk_prob)
            by_route.setdefault(str(row["route_label"]), []).append((success_prob, risk_prob))
        rows.append(
            {
                "policy": policy,
                "delay_steps": "none" if delay is None else delay,
                "estimated_success_rate": float(np.mean(success_probs)),
                "estimated_mean_risk": float(np.mean(risk_probs)),
                "recoverable_episode_fraction": float(np.mean(np.array(success_probs) >= 0.50)),
                "note": "proxy counterfactual from execution features; validate with real intervention rollouts",
            }
        )
        for route, values in by_route.items():
            if not values:
                continue
            route_rows.append(
                {
                    "policy": policy,
                    "route_label": route,
                    "n": len(values),
                    "estimated_success_rate": float(np.mean([value[0] for value in values])),
                    "estimated_mean_risk": float(np.mean([value[1] for value in values])),
                }
            )
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "summary.csv", index=False)
    pd.DataFrame(route_rows).to_csv(output_dir / "summary_by_route.csv", index=False)
    return summary


def _counterfactual_success_and_risk(row: pd.Series, delay: int | None) -> tuple[float, float]:
    route = row["route_label"]
    if route == "continue":
        return 0.92, 0.10

    confidence = float(row["retrieval_confidence"])
    risk = float(row["start_risk"])
    residual = float(row["action_outcome_residual"])
    failure_ratio = float(row["failure_neighbor_ratio"])
    progress = float(row["progress_slope"])
    embedding_distance = float(row["embedding_distance"])

    base_logit = (
        1.9 * confidence
        + 1.2 * progress
        - 1.4 * risk
        - 1.1 * residual
        - 0.9 * failure_ratio
        - 0.7 * embedding_distance
        + 0.15
    )
    base = 1.0 / (1.0 + math.exp(-base_logit))

    if delay is None:
        no_recovery_success = 0.20 * base if route in {"recover_light", "recover_strong"} else 0.08 * base
        return float(_clip(no_recovery_success)), float(_clip(risk + 0.20))

    effective_window = 16.0 + 28.0 * confidence - 14.0 * risk
    timing_decay = math.exp(-delay / max(effective_window, 6.0))
    strength_bonus = {
        "recover_light": 0.16,
        "recover_strong": 0.08,
        "demo_anchor": 0.22,
        "human_review": 0.30,
    }.get(route, 0.0)
    success = base * (0.62 + 0.38 * timing_decay) + strength_bonus
    intervention_risk = risk + 0.012 * delay + 0.35 * residual - 0.22 * confidence
    return float(_clip(success)), float(_clip(intervention_risk))


def explain_route(row: pd.Series | dict[str, Any]) -> str:
    route = row.get("route_label", "")
    confidence = float(row.get("retrieval_confidence", 0.0))
    risk = float(row.get("start_risk", row.get("risk_score", 0.0)))
    residual = float(row.get("action_outcome_residual", 0.0))
    progress = float(row.get("progress_slope", 0.0))
    failure_ratio = float(row.get("failure_neighbor_ratio", 0.0))

    if route == "continue":
        return "State remains close to the success manifold with strong progress and low residual."
    if route == "recover_light":
        return "State is near the success manifold but progress has mildly stalled."
    if route == "recover_strong":
        return "State is close to historical failure neighborhoods with high action-outcome residual."
    if route == "demo_anchor":
        return "Retrieval evidence is uncertain enough to prefer a demonstration-anchored recovery."
    if route == "human_review":
        if confidence < 0.35 and risk > 0.70:
            return "Retrieval confidence is low and start risk is high; visual or goal state needs review."
        return (
            "Automatic recovery is not trusted under the current residual, risk, "
            f"and failure-neighbor pattern ({residual:.2f}, {risk:.2f}, {failure_ratio:.2f})."
        )
    return "No route explanation available."


def build_report(
    config: dict[str, Any],
    metrics: dict[str, Any],
    timing_summary: pd.DataFrame,
    dataset_mode: str,
    source_path: str,
    feature_table_path: Path,
    predictions_path: Path,
    derivation_notes: list[str],
) -> str:
    project = config.get("project", {})
    accuracy = metrics["accuracy"]
    macro_f1 = metrics["macro_f1"]
    missed = metrics["missed_manual_or_anchor_rate"]
    false_escalation = metrics["false_manual_or_anchor_rate"]
    timing_md = timing_summary.to_markdown(index=False)
    derivation_md = "\n".join(f"- {note}" for note in derivation_notes) if derivation_notes else "- All required features were provided directly."

    return f"""# {project.get("title", "Execution-Time Reliability Layer for VOA Manipulation")}

中文题目：{project.get("chinese_title", "面向VOA操作的执行期可靠性层")}

Generated: {date.today().isoformat()}

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

Current run mode: `{dataset_mode}`.

Source table: `{source_path}`.

Feature export: `{feature_table_path}`.

Prediction export: `{predictions_path}`.

Evidence note: {metrics["evidence_note"]}

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

{derivation_md}

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

- Accuracy: `{accuracy:.3f}`
- Macro-F1: `{macro_f1:.3f}`
- Missed manual/demo-anchor escalation rate: `{missed:.3f}`
- False manual/demo-anchor escalation rate: `{false_escalation:.3f}`

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

{timing_md}

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
"""


def _parse_vector(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        try:
            return np.array(value, dtype=float)
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    text = text.strip("[]()")
    parts = [part for part in re.split(r"[\s,;]+", text) if part]
    try:
        return np.array([float(part) for part in parts], dtype=float)
    except ValueError:
        return None


def _vector_norm(vector: np.ndarray | None) -> float:
    if vector is None or vector.size == 0:
        return float("nan")
    return float(np.linalg.norm(vector))


def _vector_distance(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return float("nan")
    size = min(a.size, b.size)
    return float(np.linalg.norm(a[:size] - b[:size]))


def _progress_slope(values: np.ndarray | None) -> float:
    if values is None or values.size < 2:
        return float("nan")
    x = np.arange(values.size, dtype=float)
    slope = np.polyfit(x, values.astype(float), deg=1)[0]
    return float(_clip(slope, -1.0, 1.0))


def _value_counts(series: pd.Series) -> dict[str, int]:
    return {str(key): int(value) for key, value in series.value_counts(dropna=False).sort_index().items()}


def _evidence_note(dataset_mode: str) -> str:
    if dataset_mode == "synthetic_smoke_run":
        return "Synthetic smoke metrics validate the pipeline only. Replace the input table with real VOA rollouts before making empirical claims."
    return "Metrics come from the provided rollout table. Check label provenance, seeds, and train/test split before making deployment claims."


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))
