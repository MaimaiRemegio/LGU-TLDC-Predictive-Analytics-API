"""
Data access layer for the Applicant Volume Forecasting module.

Uses event-level applicant registration history:

    application_date, barangay, course_applied

ARIMA forecasting never reads historical_training.csv. That file belongs
to the Barangay Recommendation Random Forest pipeline.

This repository is intentionally CSV-backed today. A future MySQL
implementation can provide the same methods from the TLDC applicants
table without changing forecasting or statistics services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRATION_HISTORY_PATH = (
    PROJECT_ROOT / "datasets" / "applicant_volume_history.csv"
)
# Temporary descriptive-profile source until the TLDC MySQL applicants table
# is connected. This file is NEVER used by ARIMA forecasting.
DEFAULT_DEMOGRAPHIC_PROFILE_PATH = (
    PROJECT_ROOT / "datasets" / "historical_training.csv"
)

APPLICATION_DATE_COLUMN = "application_date"
BARANGAY_COLUMN = "barangay"
COURSE_COLUMN = "course_applied"
COUNT_COLUMN = "applicant_count"

AggregationFrequency = Literal["D", "W", "M"]

FREQUENCY_ALIASES = {
    "day": "D",
    "daily": "D",
    "D": "D",
    "week": "W",
    "weekly": "W",
    "W": "W",
    "month": "M",
    "monthly": "M",
    "M": "M",
    "MS": "M",
}

PANDAS_FREQUENCY = {
    "D": "D",
    "W": "W-SUN",
    "M": "MS",
}


class BarangayNotFoundError(ValueError):
    """Raised when a requested barangay is not present in registration history."""


class ForecastingRepository:
    """
    Repository for chronological applicant registration events.

    Each record represents one application. Forecasting services aggregate
    these events by day, week, or month before fitting ARIMA models.
    """

    def __init__(
        self,
        registration_history_path: Path = DEFAULT_REGISTRATION_HISTORY_PATH,
        demographic_profile_path: Path | None = DEFAULT_DEMOGRAPHIC_PROFILE_PATH,
    ) -> None:
        self._registration_history_path = registration_history_path
        self._demographic_profile_path = demographic_profile_path
        self._registrations = self._load_registration_history(registration_history_path)
        self._demographic_profiles = self._load_demographic_profiles(
            demographic_profile_path
        )

    def _load_registration_history(self, path: Path) -> pd.DataFrame:
        """Load event-level registration history and validate required columns."""
        if not path.exists():
            raise FileNotFoundError(
                f"Registration history not found: {path}. "
                "Run training/generate_applicant_volume_history.py first."
            )

        dataframe = pd.read_csv(path, parse_dates=[APPLICATION_DATE_COLUMN])
        required_columns = {
            APPLICATION_DATE_COLUMN,
            BARANGAY_COLUMN,
            COURSE_COLUMN,
        }
        missing = required_columns - set(dataframe.columns)
        if missing:
            raise ValueError(
                f"Registration history is missing columns: {sorted(missing)}"
            )

        dataframe = dataframe.sort_values(
            [APPLICATION_DATE_COLUMN, BARANGAY_COLUMN, COURSE_COLUMN]
        ).reset_index(drop=True)
        return dataframe

    def _load_demographic_profiles(self, path: Path | None) -> pd.DataFrame:
        """
        Load descriptive applicant attributes for barangay profile panels.

        This is a temporary stand-in for the future MySQL applicants table.
        It is used only for historical descriptive analytics and is never
        passed into ARIMA models.
        """
        if path is None or not path.exists():
            return pd.DataFrame()

        dataframe = pd.read_csv(path)
        if BARANGAY_COLUMN not in dataframe.columns:
            return pd.DataFrame()
        return dataframe

    def get_demographic_profiles(self) -> pd.DataFrame:
        """Return descriptive applicant attribute records (not used by ARIMA)."""
        return self._demographic_profiles

    def get_demographic_profiles_for_barangay(self, barangay: str) -> pd.DataFrame:
        """Return descriptive applicant attributes for one barangay."""
        self.validate_barangay(barangay)
        if self._demographic_profiles.empty:
            return pd.DataFrame()
        return self._demographic_profiles[
            self._demographic_profiles[BARANGAY_COLUMN] == barangay
        ]

    def get_registration_history(self) -> pd.DataFrame:
        """Return the event-level registration history (read-only view)."""
        return self._registrations

    def get_registration_event_count(self) -> int:
        """Return total registration events without copying the frame."""
        return int(len(self._registrations))

    def get_barangay_registration_counts(self) -> dict[str, int]:
        """Return registration event counts keyed by barangay."""
        counts = self._registrations[BARANGAY_COLUMN].value_counts()
        return {str(barangay): int(count) for barangay, count in counts.items()}

    def get_available_barangays(self) -> list[str]:
        """Return barangays present in the registration history."""
        return sorted(self._registrations[BARANGAY_COLUMN].unique().tolist())

    def validate_barangay(self, barangay: str) -> str:
        """Raise BarangayNotFoundError when the barangay is unknown."""
        available = set(self.get_available_barangays())
        if barangay not in available:
            raise BarangayNotFoundError(
                f"Unknown barangay '{barangay}'. "
                f"Available barangays: {', '.join(sorted(available))}"
            )
        return barangay

    def _normalize_frequency(self, frequency: str) -> AggregationFrequency:
        if frequency not in FREQUENCY_ALIASES:
            accepted = ", ".join(sorted(FREQUENCY_ALIASES))
            raise ValueError(
                f"Unsupported aggregation frequency '{frequency}'. "
                f"Accepted values: {accepted}"
            )
        return FREQUENCY_ALIASES[frequency]  # type: ignore[return-value]

    def aggregate_registrations(
        self,
        frequency: str = "M",
        barangay: str | None = None,
    ) -> pd.DataFrame:
        """
        Aggregate registration events into applicant counts over time.

        frequency:
          - D / day: daily counts
          - W / week: weekly counts
          - M / month: monthly counts
        """
        freq = self._normalize_frequency(frequency)
        pandas_freq = PANDAS_FREQUENCY[freq]

        records = self._registrations
        if barangay is not None:
            self.validate_barangay(barangay)
            records = records[records[BARANGAY_COLUMN] == barangay]

        if records.empty:
            return pd.DataFrame(
                columns=[APPLICATION_DATE_COLUMN, BARANGAY_COLUMN, COUNT_COLUMN]
            )

        filled_frames: list[pd.DataFrame] = []
        for current_barangay, group in records.groupby(BARANGAY_COLUMN, sort=True):
            series = (
                group.set_index(APPLICATION_DATE_COLUMN)[COURSE_COLUMN]
                .resample(pandas_freq)
                .size()
                .astype(float)
                .rename(COUNT_COLUMN)
            )
            series = series.asfreq(pandas_freq, fill_value=0.0)
            restored = series.rename(COUNT_COLUMN).reset_index()
            restored = restored.rename(columns={"index": APPLICATION_DATE_COLUMN})
            if APPLICATION_DATE_COLUMN not in restored.columns:
                restored.columns = [APPLICATION_DATE_COLUMN, COUNT_COLUMN]
            restored[BARANGAY_COLUMN] = current_barangay
            filled_frames.append(restored)

        return (
            pd.concat(filled_frames, ignore_index=True)
            .sort_values([BARANGAY_COLUMN, APPLICATION_DATE_COLUMN])
            .reset_index(drop=True)
        )

    def get_barangay_series(
        self,
        barangay: str,
        frequency: str = "M",
    ) -> pd.Series:
        """Return a continuous applicant-count series for one barangay."""
        self.validate_barangay(barangay)
        freq = self._normalize_frequency(frequency)
        pandas_freq = PANDAS_FREQUENCY[freq]

        records = self._registrations[
            self._registrations[BARANGAY_COLUMN] == barangay
        ]
        if records.empty:
            return pd.Series(dtype=float)

        series = (
            records.set_index(APPLICATION_DATE_COLUMN)[COURSE_COLUMN]
            .resample(pandas_freq)
            .size()
            .astype(float)
            .rename(COUNT_COLUMN)
        )
        return series.asfreq(pandas_freq, fill_value=0.0)

    def get_tldc_series(self, frequency: str = "M") -> pd.Series:
        """Return organization-wide applicant counts at the requested frequency."""
        freq = self._normalize_frequency(frequency)
        pandas_freq = PANDAS_FREQUENCY[freq]

        if self._registrations.empty:
            return pd.Series(dtype=float)

        series = (
            self._registrations.set_index(APPLICATION_DATE_COLUMN)[COURSE_COLUMN]
            .resample(pandas_freq)
            .size()
            .astype(float)
            .rename(COUNT_COLUMN)
        )
        return series.asfreq(pandas_freq, fill_value=0.0)

    def get_current_applicant_count(self, barangay: str, frequency: str = "M") -> int:
        """Return the most recent period's applicant total for a barangay."""
        series = self.get_barangay_series(barangay, frequency=frequency)
        if series.empty:
            return 0
        return int(round(float(series.iloc[-1])))

    def get_registrations_for_barangay(self, barangay: str) -> pd.DataFrame:
        """Return raw registration events for one barangay (read-only view)."""
        self.validate_barangay(barangay)
        return self._registrations[
            self._registrations[BARANGAY_COLUMN] == barangay
        ]


_repository: ForecastingRepository | None = None


def get_forecasting_repository() -> ForecastingRepository:
    """Return the singleton forecasting repository."""
    global _repository

    if _repository is None:
        _repository = ForecastingRepository()

    return _repository
