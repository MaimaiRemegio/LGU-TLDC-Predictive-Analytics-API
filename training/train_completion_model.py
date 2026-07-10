"""
Train a Random Forest classifier that predicts the probability of successful
training completion (Graduate vs Dropout) from an applicant profile, the
selected course, and the candidate barangay.

Saves the trained model, label encoders, validation metrics, and feature
importance for use by the API and dashboard.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from services.completion_model_config import (
    CATEGORICAL_COLUMNS,
    ENCODERS_PATH,
    FEATURE_COLUMNS,
    FEATURE_DISPLAY_NAMES,
    FEATURE_IMPORTANCE_PATH,
    METRICS_PATH,
    MODEL_PATH,
    TARGET_COLUMN,
)

DATASET_PATH = PROJECT_ROOT / "datasets" / "historical_training.csv"

TEST_SIZE = 0.2
RANDOM_STATE = 42


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the historical training dataset from CSV."""
    return pd.read_csv(path)


def encode_features(
    dataframe: pd.DataFrame,
    categorical_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Convert categorical columns to numeric labels."""
    encoded = dataframe.copy()
    label_encoders: dict[str, LabelEncoder] = {}

    for column in categorical_columns:
        encoder = LabelEncoder()
        encoded[column] = encoder.fit_transform(encoded[column])
        label_encoders[column] = encoder

    return encoded, label_encoders


def prepare_data(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, dict[str, LabelEncoder]]:
    """Select features and target, then encode categorical values."""
    features = dataframe[FEATURE_COLUMNS].copy()
    target = dataframe[TARGET_COLUMN].copy()

    combined = pd.concat([features, target], axis=1)
    encoding_columns = CATEGORICAL_COLUMNS + [TARGET_COLUMN]
    encoded, label_encoders = encode_features(combined, encoding_columns)

    x = encoded[FEATURE_COLUMNS]
    y = encoded[TARGET_COLUMN]

    return x, y, label_encoders


def train_model(x_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    """
    Train a Random Forest classifier on the training split.

    min_samples_leaf regularizes the trees so predict_proba outputs are
    well-calibrated completion probabilities.
    """
    model = RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=50,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train, y_train)
    return model


def compute_validation_metrics(
    model: RandomForestClassifier,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    target_encoder: LabelEncoder,
) -> dict:
    """
    Compute classification metrics on the held-out test set.

    Graduate is treated as the positive class for precision, recall, F1, and AUC.
    """
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)

    graduate_label = "Graduate"
    graduate_index = list(target_encoder.classes_).index(graduate_label)
    y_true_binary = (y_test == graduate_index).astype(int)
    y_prob_graduate = probabilities[:, graduate_index]

    report = classification_report(
        y_test,
        predictions,
        target_names=target_encoder.classes_,
        output_dict=True,
        zero_division=0,
    )
    graduate_metrics = report.get(graduate_label, {})

    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, pos_label=graduate_index, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, pos_label=graduate_index, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_test, predictions, pos_label=graduate_index, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true_binary, y_prob_graduate)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "class_labels": list(target_encoder.classes_),
        "classification_report": report,
        "graduate_class_metrics": {
            "precision": graduate_metrics.get("precision", 0.0),
            "recall": graduate_metrics.get("recall", 0.0),
            "f1_score": graduate_metrics.get("f1-score", 0.0),
            "support": graduate_metrics.get("support", 0),
        },
    }


def compute_feature_importance(model: RandomForestClassifier) -> list[dict]:
    """Extract and rank Random Forest feature importances."""
    importances = model.feature_importances_
    ranked_indices = np.argsort(importances)[::-1]

    return [
        {
            "feature": FEATURE_COLUMNS[index],
            "display_name": FEATURE_DISPLAY_NAMES[FEATURE_COLUMNS[index]],
            "importance": round(float(importances[index]), 6),
        }
        for index in ranked_indices
    ]


def save_json(data: dict | list, path: Path) -> None:
    """Persist metrics or feature importance as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def print_validation_summary(metrics: dict) -> None:
    """Print validation metrics for the training console."""
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1-score:  {metrics['f1_score']:.4f}")
    print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")
    print("Confusion Matrix:")
    print(np.array(metrics["confusion_matrix"]))
    print("Classification Report:")
    for label in metrics["class_labels"]:
        class_metrics = metrics["classification_report"][label]
        print(
            f"  {label}: precision={class_metrics['precision']:.4f}, "
            f"recall={class_metrics['recall']:.4f}, "
            f"f1={class_metrics['f1-score']:.4f}"
        )


def save_artifacts(
    model: RandomForestClassifier,
    label_encoders: dict[str, LabelEncoder],
    metrics: dict,
    feature_importance: list[dict],
) -> None:
    """Persist model, encoders, validation metrics, and feature importance."""
    if not isinstance(label_encoders, dict):
        raise TypeError("label_encoders must be a dictionary of fitted LabelEncoders.")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    if ENCODERS_PATH.exists():
        ENCODERS_PATH.unlink()
    joblib.dump(label_encoders, ENCODERS_PATH)

    save_json(metrics, METRICS_PATH)
    save_json(feature_importance, FEATURE_IMPORTANCE_PATH)

    print("Artifacts saved:")
    print(f"  Model:              {MODEL_PATH.resolve()}")
    print(f"  Encoders:           {ENCODERS_PATH.resolve()}")
    print(f"  Validation metrics: {METRICS_PATH.resolve()}")
    print(f"  Feature importance: {FEATURE_IMPORTANCE_PATH.resolve()}")


def main() -> None:
    dataset = load_dataset(DATASET_PATH)
    x, y, label_encoders = prepare_data(dataset)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    model = train_model(x_train, y_train)
    metrics = compute_validation_metrics(model, x_test, y_test, label_encoders[TARGET_COLUMN])
    feature_importance = compute_feature_importance(model)

    print_validation_summary(metrics)
    print("\nTop 5 Influential Features:")
    for item in feature_importance[:5]:
        print(f"  {item['display_name']}: {item['importance']:.4f}")

    save_artifacts(model, label_encoders, metrics, feature_importance)
    print("\nBarangay recommendation model trained successfully.")


if __name__ == "__main__":
    main()
