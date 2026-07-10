"""
Model validation metrics and feature importance for the completion model.

Loads metrics saved during training and exposes helpers for confidence
labels, top influencing features, and defense-ready summaries.
"""

import json
from pathlib import Path

from services.completion_model_config import (
    FEATURE_DISPLAY_NAMES,
    FEATURE_IMPORTANCE_PATH,
    METRICS_PATH,
)

CONFIDENCE_THRESHOLDS = (
    (90.0, "Very High Confidence"),
    (80.0, "High Confidence"),
    (70.0, "Moderate Confidence"),
    (0.0, "Low Confidence"),
)


def get_confidence_label(completion_probability: float) -> str:
    """
    Map a predicted completion probability (0-100) to a confidence label.

    90-100 = Very High Confidence
    80-89  = High Confidence
    70-79  = Moderate Confidence
    Below 70 = Low Confidence
    """
    for threshold, label in CONFIDENCE_THRESHOLDS:
        if completion_probability >= threshold:
            return label
    return "Low Confidence"


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def get_model_validation_metrics() -> dict | None:
    """Return saved validation metrics from training, or None if not yet generated."""
    data = _load_json(METRICS_PATH)
    return data if isinstance(data, dict) else None


def get_feature_importance() -> list[dict]:
    """
    Return all feature importance values sorted from highest to lowest.

    Each item: {"feature": str, "display_name": str, "importance": float}
    """
    data = _load_json(FEATURE_IMPORTANCE_PATH)
    if not isinstance(data, list):
        return []
    return data


def get_top_influencing_features(limit: int = 5) -> list[str]:
    """
    Return the top N most influential features by Random Forest importance.

    Display names are used for capstone-friendly explanations.
    """
    importance_data = get_feature_importance()
    return [
        item["display_name"]
        for item in importance_data[:limit]
        if "display_name" in item
    ]


def get_top_influencing_features_detailed(limit: int = 5) -> list[dict]:
    """Return top features with both display name and importance score."""
    return get_feature_importance()[:limit]
