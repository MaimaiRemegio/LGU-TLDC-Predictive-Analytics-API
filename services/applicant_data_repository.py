"""
Applicant profile data access for barangay recommendation.

Loads matching applicant profiles from the synthetic dataset (or future TLDC
database) when staff selects a training program.
"""

from pathlib import Path

import pandas as pd

from services.completion_model_config import (
    DATA_RELIABILITY_LIMITED,
    DATA_RELIABILITY_RELIABLE,
    GRADUATE_LABEL,
    HISTORICAL_SUPPORTING_EVIDENCE_LABEL,
    MIN_HISTORICAL_APPLICANTS_FOR_RELIABILITY,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "datasets" / "historical_training_course_specific.csv"

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

    def _count_graduates(self, records: pd.DataFrame) -> int:
        return int((records["training_outcome"] == GRADUATE_LABEL).sum())

    def _assess_data_reliability(self, applicant_count: int) -> str:
        if applicant_count < MIN_HISTORICAL_APPLICANTS_FOR_RELIABILITY:
            return DATA_RELIABILITY_LIMITED
        return DATA_RELIABILITY_RELIABLE

    def get_barangay_historical_supporting_evidence_for_course(
        self, course_applied: str
    ) -> dict[str, dict]:
        """
        Return per-barangay historical statistics for the selected course.

        All values are labeled as supporting evidence and are not used by the
        Random Forest to compute the AI Recommendation Score.
        """
        records = self.get_records_for_course(course_applied)
        total_applicants = len(records)

        if total_applicants == 0:
            return {}

        evidence_by_barangay: dict[str, dict] = {}

        for barangay, barangay_records in records.groupby("barangay"):
            barangay_name = str(barangay)
            applicant_count = len(barangay_records)
            graduates = self._count_graduates(barangay_records)
            dropouts = applicant_count - graduates

            completion_percentage = (
                round((graduates / applicant_count) * 100, 1)
                if applicant_count > 0
                else 0.0
            )
            dropout_percentage = (
                round((dropouts / applicant_count) * 100, 1)
                if applicant_count > 0
                else 0.0
            )
            participation_percentage = round((applicant_count / total_applicants) * 100, 1)

            evidence_by_barangay[barangay_name] = {
                "label": HISTORICAL_SUPPORTING_EVIDENCE_LABEL,
                "historical_participation_percentage": participation_percentage,
                "historical_completion_percentage": completion_percentage,
                "historical_dropout_percentage": dropout_percentage,
                "historical_applicant_count": int(applicant_count),
                "data_reliability": self._assess_data_reliability(applicant_count),
            }

        return evidence_by_barangay

    def get_barangay_participation_for_course(self, course_applied: str) -> dict[str, dict]:
        """
        Return course-specific historical applicant counts and participation
        percentages for every barangay in the dataset.
        """
        evidence = self.get_barangay_historical_supporting_evidence_for_course(course_applied)

        return {
            barangay: {
                "historical_applicants": stats["historical_applicant_count"],
                "historical_participation_percentage": stats["historical_participation_percentage"],
                "data_reliability": stats["data_reliability"],
            }
            for barangay, stats in evidence.items()
        }


_repository: ApplicantDataRepository | None = None


def get_applicant_data_repository() -> ApplicantDataRepository:
    """Return the singleton applicant data repository."""
    global _repository

    if _repository is None:
        _repository = ApplicantDataRepository()

    return _repository
