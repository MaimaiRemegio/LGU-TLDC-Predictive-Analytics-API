"""
Train a Random Forest classifier to recommend TESDA courses
based on applicant profile and context features.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "datasets" / "training_data.csv"
MODEL_PATH = PROJECT_ROOT / "trained_models" / "course_model.pkl"
ENCODERS_PATH = PROJECT_ROOT / "trained_models" / "label_encoders.pkl"

# Feature and target column definitions
FEATURE_COLUMNS = [
    "month",
    "barangay",
    "employment_status",
    "educational_attainment",
    "current_skill",
    "work_experience",
    "desired_career",
]
TARGET_COLUMN = "applied_course"

# Columns encoded with LabelEncoder (month is already numeric)
CATEGORICAL_COLUMNS = [
    "barangay",
    "employment_status",
    "educational_attainment",
    "current_skill",
    "work_experience",
    "desired_career",
    TARGET_COLUMN,
]

TEST_SIZE = 0.2
RANDOM_STATE = 42


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the training dataset from CSV."""
    return pd.read_csv(path)


def encode_features(
    dataframe: pd.DataFrame,
    categorical_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """
    Convert categorical columns to numeric labels.
    Returns the encoded dataframe and a dictionary of fitted encoders.
    """
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
    encoded, label_encoders = encode_features(combined, CATEGORICAL_COLUMNS)

    x = encoded[FEATURE_COLUMNS]
    y = encoded[TARGET_COLUMN]

    return x, y, label_encoders


def train_model(x_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    """Train a Random Forest classifier on the training split."""
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train, y_train)
    return model


def evaluate_model(
    model: RandomForestClassifier,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    target_encoder: LabelEncoder,
) -> None:
    """Print accuracy and a per-class classification report."""
    predictions = model.predict(x_test)

    accuracy = accuracy_score(y_test, predictions)
    target_labels = target_encoder.classes_

    print(f"Accuracy: {accuracy:.4f}")
    print("Classification Report:")
    print(
        classification_report(
            y_test,
            predictions,
            target_names=target_labels,
        )
    )


def save_artifacts(
    model: RandomForestClassifier,
    label_encoders: dict[str, LabelEncoder],
) -> None:
    """Persist the trained model and label encoders to disk."""
    if not isinstance(label_encoders, dict):
        raise TypeError("label_encoders must be a dictionary of fitted LabelEncoders.")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, MODEL_PATH)

    # Always overwrite any existing encoder file from a previous run.
    if ENCODERS_PATH.exists():
        ENCODERS_PATH.unlink()

    print("Encoders stored:")
    print(label_encoders.keys())

    joblib.dump(label_encoders, ENCODERS_PATH)

    try:
        loaded_encoders = joblib.load(ENCODERS_PATH)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load saved encoders from {ENCODERS_PATH}"
        ) from exc

    if not isinstance(loaded_encoders, dict):
        raise RuntimeError("Loaded encoders file did not contain a dictionary.")

    if set(loaded_encoders.keys()) != set(label_encoders.keys()):
        raise RuntimeError("Loaded encoders keys do not match saved encoders.")

    print("Loaded encoders:")
    print(loaded_encoders.keys())

    print(MODEL_PATH.resolve())
    print(ENCODERS_PATH.resolve())
    print(MODEL_PATH.stat().st_size)
    print(ENCODERS_PATH.stat().st_size)


def main() -> None:
    # 1. Load dataset
    dataset = load_dataset(DATASET_PATH)

    # 2–3. Prepare features, target, and encoders
    x, y, label_encoders = prepare_data(dataset)

    # 4. Split into training and testing sets
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    # 5. Train the model
    model = train_model(x_train, y_train)

    # 6. Evaluate performance
    evaluate_model(model, x_test, y_test, label_encoders[TARGET_COLUMN])

    # 7–8. Save model and encoders
    save_artifacts(model, label_encoders)

    print("Model trained successfully.")


if __name__ == "__main__":
    main()
