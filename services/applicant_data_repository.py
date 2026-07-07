"""
Applicant profile data access for barangay recommendation.

Loads matching applicant profiles from the synthetic dataset (or future TLDC
database) when staff selects a training program.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "datasets" / "historical_training.csv"

PROFILE_FIELDS = [
    "course_applied",
    "age",
    "sex",
    "educational_attainment",
    "employment_status",
    "current_skill",
    "desired_career",
    "learner_classification",
]


class CourseNotFoundError(ValueError):
    """Raised when no applicant records exist for the requested course."""


class ApplicantDataRepository:
    """Read applicant profiles used for barangay recommendation."""

    def __init__(self, dataset_path: Path = DEFAULT_DATASET_PATH) -> None:
        self._dataset_path = dataset_path
        self._dataframe = pd.read_csv(dataset_path)

    def get_available_courses(self) -> list[str]:
        """Return all training programs present in the dataset."""
        return sorted(self._dataframe["course_applied"].unique().tolist())

    def get_records_for_course(self, course_applied: str) -> pd.DataFrame:
        """Return all applicant records for a training program."""
        records = self._dataframe[self._dataframe["course_applied"] == course_applied]

        if records.empty:
            available = ", ".join(self.get_available_courses())
            raise CourseNotFoundError(
                f"No applicant records found for course '{course_applied}'. "
                f"Available courses: {available}"
            )

        return records

    def get_historical_data(self) -> pd.DataFrame:
        """Return a copy of the historical training dataset."""
        return self._dataframe.copy()

    def get_applicant_profile_for_course(self, course_applied: str) -> dict:
        """
        Load one representative applicant profile that matches the selected course.

        Uses the most common categorical values and median age from the synthetic
        dataset so the model receives a realistic applicant profile.
        """
        records = self.get_records_for_course(course_applied)

        return {
            "course_applied": course_applied,
            "age": int(records["age"].median()),
            "sex": records["sex"].mode().iloc[0],
            "educational_attainment": records["educational_attainment"].mode().iloc[0],
            "employment_status": records["employment_status"].mode().iloc[0],
            "current_skill": records["current_skill"].mode().iloc[0],
            "desired_career": records["desired_career"].mode().iloc[0],
            "learner_classification": records["learner_classification"].mode().iloc[0],
        }

    def _build_distribution(self, records: pd.DataFrame, column: str, limit: int | None = None) -> list[dict]:
        """Return value counts as label, count, and percentage entries."""
        total = len(records)
        if total == 0:
            return []

        counts = records[column].value_counts()
        if limit is not None:
            counts = counts.head(limit)

        return [
            {
                "label": str(label),
                "count": int(count),
                "percentage": round((count / total) * 100, 1),
            }
            for label, count in counts.items()
        ]

    def get_course_workforce_profile(self, course_applied: str) -> dict:
        """
        Summarize historical learners for a training program.

        Used by the Barangay Recommendation dashboard to show course-level
        workforce analytics alongside AI deployment recommendations.
        """
        records = self.get_records_for_course(course_applied)
        total_applicants = len(records)
        graduates = int((records["training_outcome"] == "Graduate").sum())
        completion_rate = (
            round((graduates / total_applicants) * 100, 1)
            if total_applicants > 0
            else 0.0
        )

        return {
            "course_applied": course_applied,
            "total_historical_applicants": total_applicants,
            "historical_graduates": graduates,
            "historical_completion_rate": completion_rate,
            "most_common_skills": self._build_distribution(records, "current_skill", limit=5),
            "most_common_educational_attainment": self._build_distribution(
                records, "educational_attainment", limit=5
            ),
            "employment_status_distribution": self._build_distribution(
                records, "employment_status"
            ),
            "most_common_desired_careers": self._build_distribution(
                records, "desired_career", limit=5
            ),
            "learner_classification_distribution": self._build_distribution(
                records, "learner_classification"
            ),
        }


_repository: ApplicantDataRepository | None = None


def get_applicant_data_repository() -> ApplicantDataRepository:
    """Return the singleton applicant data repository."""
    global _repository

    if _repository is None:
        _repository = ApplicantDataRepository()

    return _repository
