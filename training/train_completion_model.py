"""
Train the Random Forest completion model from the production database.

The model predicts:

    training_outcome
        1 = Graduate
        0 = Dropout

The applicant's barangay is an input feature, not the prediction target.

The training data is retrieved using a read-only SELECT query.

No INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE operations are performed.
"""

import json
import sys
from pathlib import Path

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


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from services.database import read_sql

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


RANDOM_STATE = 42
TEST_SIZE = 0.2


# ---------------------------------------------------------------------------
# DATABASE QUERY
# ---------------------------------------------------------------------------

TRAINING_QUERY = """
SELECT
    application_id,
    barangay_code,
    barangay,
    course_id,
    course_applied,
    submitted_at,
    age,
    sex,
    employment_status,
    educational_attainment,
    current_skill,
    desired_career,
    learner_classification,
    training_outcome
FROM ml_training_dataset
WHERE training_outcome IS NOT NULL
"""


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

def load_training_dataset() -> pd.DataFrame:
    """
    Load historical training records directly from the production database.

    This uses read_sql(), which accepts SELECT statements only.
    """

    print("Connecting to production database...")
    print("Reading ml_training_dataset...")

    dataframe = read_sql(TRAINING_QUERY)

    print(f"Rows retrieved: {len(dataframe)}")

    return dataframe


# ---------------------------------------------------------------------------
# DATA VALIDATION
# ---------------------------------------------------------------------------

def validate_dataset(dataframe: pd.DataFrame) -> None:
    """Validate that the database returned usable ML training data."""

    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            "The database dataset is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if dataframe.empty:
        raise ValueError(
            "The database returned zero training records."
        )

    missing_values = dataframe[
        FEATURE_COLUMNS + [TARGET_COLUMN]
    ].isnull().sum()

    problematic = missing_values[missing_values > 0]

    if not problematic.empty:
        print("\nWarning: missing values detected:")

        for column, count in problematic.items():
            print(f"  {column}: {count}")

    outcome_counts = dataframe[TARGET_COLUMN].value_counts()

    print("\nTraining outcome distribution:")

    for outcome, count in outcome_counts.items():
        print(f"  {outcome}: {count}")

    unique_outcomes = dataframe[TARGET_COLUMN].nunique()

    if unique_outcomes < 2:
        raise ValueError(
            "Training cannot proceed yet because the dataset contains "
            "only one training_outcome class. You need both Graduate "
            "and Dropout records."
        )


# ---------------------------------------------------------------------------
# ENCODING
# ---------------------------------------------------------------------------

def encode_features(
    dataframe: pd.DataFrame,
    categorical_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Convert categorical columns to numeric labels."""

    encoded = dataframe.copy()

    label_encoders: dict[str, LabelEncoder] = {}

    for column in categorical_columns:

        encoder = LabelEncoder()

        values = encoded[column].fillna("Unknown").astype(str)

        encoded[column] = encoder.fit_transform(values)

        label_encoders[column] = encoder

    return encoded, label_encoders


def prepare_data(
    dataframe: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.Series,
    dict[str, LabelEncoder],
]:
    """Prepare features and target for Random Forest training."""

    features = dataframe[FEATURE_COLUMNS].copy()

    target = dataframe[TARGET_COLUMN].copy()

    combined = pd.concat(
        [features, target],
        axis=1,
    )

    encoding_columns = (
        CATEGORICAL_COLUMNS
        + [TARGET_COLUMN]
    )

    encoded, label_encoders = encode_features(
        combined,
        encoding_columns,
    )

    x = encoded[FEATURE_COLUMNS]

    y = encoded[TARGET_COLUMN]

    return x, y, label_encoders


# ---------------------------------------------------------------------------
# MODEL
# ---------------------------------------------------------------------------

def train_model(
    x_train: pd.DataFrame,
    y_train: pd.Series,
) -> RandomForestClassifier:
    """
    Train the Random Forest completion model.
    """

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight="balanced",
    )

    model.fit(
        x_train,
        y_train,
    )

    return model


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def compute_validation_metrics(
    model: RandomForestClassifier,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    target_encoder: LabelEncoder,
) -> dict:
    """
    Calculate validation metrics.

    Graduate is treated as the positive class.
    """

    predictions = model.predict(x_test)

    probabilities = model.predict_proba(x_test)

    graduate_label = "Graduate"

    if graduate_label not in target_encoder.classes_:
        raise ValueError(
            "Graduate is not present in the target encoder."
        )

    graduate_index = list(
        target_encoder.classes_
    ).index(graduate_label)

    y_true_binary = (
        y_test == graduate_index
    ).astype(int)

    y_prob_graduate = probabilities[
        :,
        list(model.classes_).index(graduate_index),
    ]

    report = classification_report(
        y_test,
        predictions,
        target_names=target_encoder.classes_,
        output_dict=True,
        zero_division=0,
    )

    graduate_metrics = report.get(
        graduate_label,
        {},
    )

    # ROC-AUC requires both classes in the test set.
    if len(np.unique(y_true_binary)) == 2:
        roc_auc = roc_auc_score(
            y_true_binary,
            y_prob_graduate,
        )
    else:
        roc_auc = None

    return {
        "accuracy": round(
            float(
                accuracy_score(
                    y_test,
                    predictions,
                )
            ),
            4,
        ),

        "precision": round(
            float(
                precision_score(
                    y_test,
                    predictions,
                    pos_label=graduate_index,
                    zero_division=0,
                )
            ),
            4,
        ),

        "recall": round(
            float(
                recall_score(
                    y_test,
                    predictions,
                    pos_label=graduate_index,
                    zero_division=0,
                )
            ),
            4,
        ),

        "f1_score": round(
            float(
                f1_score(
                    y_test,
                    predictions,
                    pos_label=graduate_index,
                    zero_division=0,
                )
            ),
            4,
        ),

        "roc_auc": (
            round(float(roc_auc), 4)
            if roc_auc is not None
            else None
        ),

        "confusion_matrix": (
            confusion_matrix(
                y_test,
                predictions,
            ).tolist()
        ),

        "class_labels": list(
            target_encoder.classes_
        ),

        "classification_report": report,

        "graduate_class_metrics": {
            "precision": graduate_metrics.get(
                "precision",
                0.0,
            ),

            "recall": graduate_metrics.get(
                "recall",
                0.0,
            ),

            "f1_score": graduate_metrics.get(
                "f1-score",
                0.0,
            ),

            "support": graduate_metrics.get(
                "support",
                0,
            ),
        },
    }


# ---------------------------------------------------------------------------
# FEATURE IMPORTANCE
# ---------------------------------------------------------------------------

def compute_feature_importance(
    model: RandomForestClassifier,
) -> list[dict]:
    """Extract Random Forest feature importance."""

    importances = model.feature_importances_

    ranked_indices = np.argsort(
        importances
    )[::-1]

    return [
        {
            "feature": FEATURE_COLUMNS[index],

            "display_name": FEATURE_DISPLAY_NAMES[
                FEATURE_COLUMNS[index]
            ],

            "importance": round(
                float(importances[index]),
                6,
            ),
        }

        for index in ranked_indices
    ]


# ---------------------------------------------------------------------------
# FILE OUTPUT
# ---------------------------------------------------------------------------

def save_json(
    data: dict | list,
    path: Path,
) -> None:
    """Save JSON output."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
        )


def save_artifacts(
    model: RandomForestClassifier,
    label_encoders: dict[str, LabelEncoder],
    metrics: dict,
    feature_importance: list[dict],
) -> None:
    """Save trained model and metadata."""

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        model,
        MODEL_PATH,
        compress=3,
    )

    joblib.dump(
        label_encoders,
        ENCODERS_PATH,
        compress=3,
    )

    save_json(
        metrics,
        METRICS_PATH,
    )

    save_json(
        feature_importance,
        FEATURE_IMPORTANCE_PATH,
    )

    model_size_mb = (
        MODEL_PATH.stat().st_size
        / (1024 * 1024)
    )

    print("\nArtifacts saved:")

    print(
        f"  Model: {MODEL_PATH.resolve()}"
    )

    print(
        f"  Model size: {model_size_mb:.2f} MB"
    )

    print(
        f"  Encoders: {ENCODERS_PATH.resolve()}"
    )

    print(
        f"  Metrics: {METRICS_PATH.resolve()}"
    )

    print(
        f"  Feature importance: "
        f"{FEATURE_IMPORTANCE_PATH.resolve()}"
    )


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

def print_validation_summary(
    metrics: dict,
) -> None:
    """Print validation results."""

    print("\n==============================")
    print("MODEL VALIDATION")
    print("==============================")

    print(
        f"Accuracy:  {metrics['accuracy']:.4f}"
    )

    print(
        f"Precision: {metrics['precision']:.4f}"
    )

    print(
        f"Recall:    {metrics['recall']:.4f}"
    )

    print(
        f"F1-score:  {metrics['f1_score']:.4f}"
    )

    print(
        f"ROC-AUC:   {metrics['roc_auc']}"
    )

    print("\nConfusion Matrix:")

    print(
        np.array(
            metrics["confusion_matrix"]
        )
    )

    print("\nClassification Report:")

    for label in metrics["class_labels"]:

        class_metrics = (
            metrics[
                "classification_report"
            ][label]
        )

        print(
            f"  {label}: "
            f"precision={class_metrics['precision']:.4f}, "
            f"recall={class_metrics['recall']:.4f}, "
            f"f1={class_metrics['f1-score']:.4f}"
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:

    print("==============================")
    print("TLDC COMPLETION MODEL TRAINER")
    print("==============================")

    dataframe = load_training_dataset()

    validate_dataset(dataframe)

    x, y, label_encoders = prepare_data(
        dataframe
    )

    print(
        f"\nFeatures used: {', '.join(FEATURE_COLUMNS)}"
    )

    print(
        f"Target: {TARGET_COLUMN}"
    )

    # Stratification keeps Graduate/Dropout proportions
    # similar between training and testing data.
    x_train, x_test, y_train, y_test = (
        train_test_split(
            x,
            y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=y,
        )
    )

    print(
        f"\nTraining rows: {len(x_train)}"
    )

    print(
        f"Testing rows:  {len(x_test)}"
    )

    print("\nTraining Random Forest...")

    model = train_model(
        x_train,
        y_train,
    )

    metrics = compute_validation_metrics(
        model,
        x_test,
        y_test,
        label_encoders[TARGET_COLUMN],
    )

    feature_importance = (
        compute_feature_importance(model)
    )

    print_validation_summary(
        metrics
    )

    print("\nTop 5 Influential Features:")

    for item in feature_importance[:5]:

        print(
            f"  {item['display_name']}: "
            f"{item['importance']:.4f}"
        )

    save_artifacts(
        model,
        label_encoders,
        metrics,
        feature_importance,
    )

    print(
        "\nSUCCESS: Completion model trained "
        "from database data."
    )


if __name__ == "__main__":
    main()