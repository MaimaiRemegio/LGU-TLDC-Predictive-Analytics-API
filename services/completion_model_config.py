"""
Shared configuration for the barangay completion Random Forest model.

Centralizes feature definitions used by training, prediction, and metadata
services to avoid duplicated column lists across the codebase.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "trained_models" / "completion_model.pkl"
ENCODERS_PATH = PROJECT_ROOT / "trained_models" / "completion_encoders.pkl"
METRICS_PATH = PROJECT_ROOT / "trained_models" / "completion_model_metrics.json"
FEATURE_IMPORTANCE_PATH = PROJECT_ROOT / "trained_models" / "completion_feature_importance.json"

FEATURE_COLUMNS = [
    "barangay",
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
    "barangay",
    "course_applied",
    "sex",
    "educational_attainment",
    "employment_status",
    "current_skill",
    "desired_career",
    "learner_classification",
]

TARGET_COLUMN = "training_outcome"
GRADUATE_LABEL = "Graduate"
DROPOUT_LABEL = "Dropout"

# Human-readable labels for dashboard and defense explanations.
FEATURE_DISPLAY_NAMES = {
    "barangay": "Barangay",
    "course_applied": "Course Applied",
    "age": "Age",
    "sex": "Sex",
    "educational_attainment": "Educational Attainment",
    "employment_status": "Employment Status",
    "current_skill": "Current Skill",
    "desired_career": "Desired Career",
    "learner_classification": "Learner Classification",
}

MIN_HISTORICAL_APPLICANTS_FOR_RELIABILITY = 20
HISTORICAL_SUPPORTING_EVIDENCE_LABEL = "Historical Supporting Evidence"
DATA_RELIABILITY_LIMITED = "Limited historical data"
DATA_RELIABILITY_RELIABLE = "Reliable"
