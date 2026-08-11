"""
Descriptive statistics for the Applicant Volume Forecasting module.

Registration analytics come from applicant_volume_history.csv.
Demographic analytics come from a temporary descriptive source that will
later be replaced by the TLDC MySQL applicants table.

ARIMA forecasting never uses these descriptive statistics.
"""

from __future__ import annotations

import pandas as pd

from services.forecasting_repository import (
    BARANGAY_COLUMN,
    COURSE_COLUMN,
    ForecastingRepository,
    get_forecasting_repository,
)

AGE_BINS = [0, 17, 24, 34, 44, 54, 200]
AGE_LABELS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55+"]


class ForecastingStatistics:
    """Build historical analytics for forecasting dashboards."""

    def __init__(self, repository: ForecastingRepository | None = None) -> None:
        self._repository = repository or get_forecasting_repository()

    def _build_distribution(
        self,
        records: pd.DataFrame,
        column: str,
        limit: int | None = None,
    ) -> list[dict]:
        """Return value counts as label, count, and percentage entries."""
        if records.empty or column not in records.columns:
            return []

        total = len(records)
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

    def _build_age_distribution(self, records: pd.DataFrame) -> list[dict]:
        if records.empty or "age" not in records.columns:
            return []

        age_groups = pd.cut(
            records["age"],
            bins=AGE_BINS,
            labels=AGE_LABELS,
            right=True,
            include_lowest=True,
        )
        total = len(records)
        counts = age_groups.value_counts().reindex(AGE_LABELS, fill_value=0)

        return [
            {
                "label": str(label),
                "count": int(count),
                "percentage": round((count / total) * 100, 1) if total else 0.0,
            }
            for label, count in counts.items()
        ]

    def _most_common_label(self, records: pd.DataFrame, column: str) -> str | None:
        if records.empty or column not in records.columns:
            return None
        mode_values = records[column].mode()
        if mode_values.empty:
            return None
        return str(mode_values.iloc[0])

    def get_barangay_profile(self, barangay: str) -> dict:
        """
        Build a historical applicant profile for one barangay.

        Registration totals/courses come from the forecasting history.
        Demographics come from the temporary descriptive source (future MySQL).
        None of these values are forecasted.
        """
        registrations = self._repository.get_registrations_for_barangay(barangay)
        demographics = self._repository.get_demographic_profiles_for_barangay(barangay)

        total_from_registrations = len(registrations)
        profile_records = demographics if not demographics.empty else registrations
        total_applicants = (
            len(demographics) if not demographics.empty else total_from_registrations
        )

        sex_distribution = self._build_distribution(profile_records, "sex")
        male_count = next(
            (item["count"] for item in sex_distribution if item["label"] == "Male"),
            0,
        )
        female_count = next(
            (item["count"] for item in sex_distribution if item["label"] == "Female"),
            0,
        )
        average_age = (
            round(float(profile_records["age"].mean()), 1)
            if "age" in profile_records.columns and not profile_records.empty
            else None
        )

        course_column = (
            "course_applied"
            if "course_applied" in profile_records.columns
            else COURSE_COLUMN
        )

        return {
            "barangay": barangay,
            "total_applicants": total_applicants,
            "registration_event_count": total_from_registrations,
            "male_count": male_count,
            "female_count": female_count,
            "average_age": average_age,
            "sex_distribution": sex_distribution,
            "age_distribution": self._build_age_distribution(profile_records),
            "educational_attainment_distribution": self._build_distribution(
                profile_records,
                "educational_attainment",
            ),
            "employment_status_distribution": self._build_distribution(
                profile_records,
                "employment_status",
            ),
            "learner_classification_distribution": self._build_distribution(
                profile_records,
                "learner_classification",
            ),
            "most_applied_course": self._most_common_label(profile_records, course_column),
            "course_distribution": self._build_distribution(
                profile_records,
                course_column,
                limit=8,
            ),
            "desired_career_distribution": self._build_distribution(
                profile_records,
                "desired_career",
                limit=8,
            ),
            "current_skill_distribution": self._build_distribution(
                profile_records,
                "current_skill",
                limit=8,
            ),
            "note": (
                "These values are historical summaries only and are not forecasted. "
                "ARIMA uses registration history for volume forecasts only. "
                "Demographic attributes currently come from a temporary descriptive "
                "dataset and will later be loaded from the TLDC MySQL applicants table."
            ),
        }

    def get_organization_distributions(self) -> dict:
        """Return organization-wide distributions for charts and insights."""
        registrations = self._repository.get_registration_history()
        demographics = self._repository.get_demographic_profiles()
        profile_records = demographics if not demographics.empty else registrations
        course_column = (
            "course_applied"
            if "course_applied" in profile_records.columns
            else COURSE_COLUMN
        )

        return {
            "employment_distribution": self._build_distribution(
                profile_records,
                "employment_status",
            ),
            "education_distribution": self._build_distribution(
                profile_records,
                "educational_attainment",
            ),
            "course_distribution": self._build_distribution(
                profile_records,
                course_column,
                limit=10,
            ),
            "sex_distribution": self._build_distribution(profile_records, "sex"),
            "age_distribution": self._build_age_distribution(profile_records),
            "learner_classification_distribution": self._build_distribution(
                profile_records,
                "learner_classification",
            ),
            "barangay_distribution": self._build_distribution(
                registrations,
                BARANGAY_COLUMN,
                limit=10,
            ),
            "most_popular_course": self._most_common_label(profile_records, course_column),
            "most_common_employment_status": self._most_common_label(
                profile_records,
                "employment_status",
            ),
            "most_common_educational_attainment": self._most_common_label(
                profile_records,
                "educational_attainment",
            ),
        }


_statistics: ForecastingStatistics | None = None


def get_forecasting_statistics() -> ForecastingStatistics:
    """Return the singleton forecasting statistics service."""
    global _statistics

    if _statistics is None:
        _statistics = ForecastingStatistics()

    return _statistics
