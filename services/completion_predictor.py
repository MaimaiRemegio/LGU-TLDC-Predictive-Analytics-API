"""
Barangay recommendation service for the LGU-TLDC Predictive Analytics API.

Uses a Random Forest model trained to predict the probability of successful
training completion (Graduate vs Dropout). The barangay is an input feature,
so the same applicant profile is scored against every barangay and the
barangays are ranked by predicted completion probability.
"""

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from services.completion_model_config import (
    ENCODERS_PATH,
    FEATURE_COLUMNS,
    GRADUATE_LABEL,
    MODEL_PATH,
    TARGET_COLUMN,
)

BARANGAY_FEATURE_KEY = "barangay"
TARGET_ENCODER_KEY = TARGET_COLUMN


from services.model_metadata import get_confidence_label


class UnknownCategoryError(ValueError):
    """Raised when an input value is not recognized by a stored LabelEncoder."""


class CompletionPredictor:
    """Rank barangays by predicted training-completion probability."""

    def __init__(self) -> None:
        self._model: RandomForestClassifier = joblib.load(MODEL_PATH)
        self._encoders: dict[str, LabelEncoder] = joblib.load(ENCODERS_PATH)

        target_encoder = self._encoders[TARGET_ENCODER_KEY]
        self._graduate_encoded = int(target_encoder.transform([GRADUATE_LABEL])[0])
        # Column of predict_proba() that corresponds to the "Graduate" class.
        self._graduate_column = list(self._model.classes_).index(self._graduate_encoded)

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

    def _encode_row(self, applicant: dict) -> dict[str, int | float]:
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

        return encoded_row

    def recommend_barangays(self, applicant: dict) -> list[dict]:
        """
        Score the applicant profile against every barangay and return all
        barangays ranked by predicted training-completion probability.

        For each barangay, the score is P(Graduate | barangay, course, profile)
        taken directly from the Random Forest's predict_proba output. It is a
        probability estimate, not a tally of how many trees voted.
        """
        barangay_encoder = self._encoders[BARANGAY_FEATURE_KEY]
        barangays = [str(label) for label in barangay_encoder.classes_]

        encoded_rows = [
            self._encode_row({**applicant, BARANGAY_FEATURE_KEY: barangay})
            for barangay in barangays
        ]
        features = pd.DataFrame(encoded_rows)[FEATURE_COLUMNS]

        graduate_probabilities = self._model.predict_proba(features)[:, self._graduate_column]

        recommendations = [
            {
                "barangay": barangay,
                "completion_probability": round(float(probability) * 100, 1),
                "confidence_level": get_confidence_label(round(float(probability) * 100, 1)),
            }
            for barangay, probability in zip(barangays, graduate_probabilities)
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
