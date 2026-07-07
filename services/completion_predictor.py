"""
Barangay recommendation service for the LGU-TLDC Predictive Analytics API.

Uses a Random Forest model trained to predict the best barangay from an
applicant profile and selected training program.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "trained_models" / "completion_model.pkl"
ENCODERS_PATH = PROJECT_ROOT / "trained_models" / "completion_encoders.pkl"

FEATURE_COLUMNS = [
    "course_applied",
    "age",
    "sex",
    "educational_attainment",
    "employment_status",
    "current_skill",
    "desired_career",
    "learner_classification",
]

CATEGORICAL_COLUMNS = [
    "course_applied",
    "sex",
    "educational_attainment",
    "employment_status",
    "current_skill",
    "desired_career",
    "learner_classification",
]

TARGET_ENCODER_KEY = "barangay"


class UnknownCategoryError(ValueError):
    """Raised when an input value is not recognized by a stored LabelEncoder."""


class CompletionPredictor:
    """Recommend barangays using the trained Random Forest model."""

    def __init__(self) -> None:
        self._model: RandomForestClassifier = joblib.load(MODEL_PATH)
        self._encoders: dict[str, LabelEncoder] = joblib.load(ENCODERS_PATH)

    def _encode_value(self, column: str, value: str) -> int:
        encoder = self._encoders[column]
        known_values = list(encoder.classes_)

        if value not in known_values:
            accepted = ", ".join(known_values)
            raise UnknownCategoryError(
                f"Unknown value '{value}' for field '{column}'. "
                f"Accepted values: {accepted}"
            )

        return int(encoder.transform([value])[0])

    def _prepare_features(self, applicant: dict) -> pd.DataFrame:
        encoded_row: dict[str, int | float] = {}

        for column in FEATURE_COLUMNS:
            if column not in applicant:
                raise ValueError(f"Missing required field: '{column}'")

            if column == "age":
                age = applicant[column]
                if not isinstance(age, int) or isinstance(age, bool):
                    raise ValueError("Field 'age' must be an integer.")
                encoded_row[column] = age
                continue

            encoded_row[column] = self._encode_value(column, str(applicant[column]))

        return pd.DataFrame([encoded_row])[FEATURE_COLUMNS]

    def recommend_barangays(self, applicant: dict) -> list[dict]:
        """
        Predict barangay suitability probabilities for the applicant profile
        and return all barangays ranked from highest to lowest probability.
        """
        features = self._prepare_features(applicant)
        probabilities = self._model.predict_proba(features)[0]

        barangay_encoder = self._encoders[TARGET_ENCODER_KEY]
        barangay_labels = list(barangay_encoder.classes_)

        recommendations = [
            {
                "barangay": barangay,
                "completion_probability": round(float(probability) * 100, 1),
            }
            for barangay, probability in zip(barangay_labels, probabilities)
        ]

        recommendations.sort(
            key=lambda item: item["completion_probability"],
            reverse=True,
        )
        return recommendations


_predictor: CompletionPredictor | None = None


def get_completion_predictor() -> CompletionPredictor:
    """Return the singleton barangay recommendation predictor."""
    global _predictor

    if _predictor is None:
        _predictor = CompletionPredictor()

    return _predictor


def recommend_barangays(applicant: dict) -> list[dict]:
    """Convenience wrapper for ranked barangay recommendations."""
    return get_completion_predictor().recommend_barangays(applicant)
