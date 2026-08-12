"""
Data access layer for the TLDC Applicant Volume Forecasting module.

Primary ARIMA source
--------------------
datasets/applicant_volume.csv
  Columns: date, course, applicant_count

Each row is one (date, course) observation with a DAILY applicant count.
The repository aggregates daily data to WEEKLY totals before returning
ARIMA-ready series — weekly aggregation balances noise reduction with
enough observations for a sound ARIMA model.

Descriptive profiles
--------------------
datasets/historical_training.csv is used only for barangay demographic
profile panels (sex, age, education, etc.).  It is NEVER passed to ARIMA.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Primary ARIMA data source.
DEFAULT_VOLUME_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"

# Demographic profile source (descriptive only, never used by ARIMA).
DEFAULT_DEMOGRAPHIC_PROFILE_PATH = (
    PROJECT_ROOT / "datasets" / "historical_training.csv"
)

# Column names in the daily CSV.
DATE_COLUMN = "date"
COURSE_COLUMN = "course"
COUNT_COLUMN = "applicant_count"

# Column names for the demographic CSV.
BARANGAY_COLUMN = "barangay"

# Weekly aggregation anchor: weeks end on Sunday.
WEEKLY_FREQ = "W-SUN"

# Keep backward-compatible aliases so callers can still pass "M" or "W".
_FREQ_ALIAS = {
    "D": "D", "day": "D", "daily": "D",
    "W": "W", "week": "W", "weekly": "W",
    "M": "M", "month": "M", "monthly": "M",
}


class CourseNotFoundError(ValueError):
    """Raised when a requested course is not present in the volume dataset."""


class BarangayNotFoundError(ValueError):
    """Raised when a requested barangay is not present in demographic profiles."""


class ForecastingRepository:
    """
    Repository for the TLDC applicant volume forecasting pipeline.

    ARIMA input
    -----------
    get_course_series(course)  → weekly pd.Series  (primary ARIMA input)
    get_tldc_series()          → weekly pd.Series  (all courses summed)
    get_available_courses()    → list[str]

    The repository reads DAILY data and returns WEEKLY aggregated series.
    This is intentional:
      - Daily series (1 826 obs) would make walk-forward backtesting very slow.
      - Weekly series (~260 obs) is large enough for ARIMA(1,1,1) and gives
        meaningful next_week / next_month / next_quarter forecasts.

    Descriptive (not ARIMA)
    -----------------------
    get_demographic_profiles_for_barangay(barangay) → pd.DataFrame
    get_available_barangays()                        → list[str]
    """

    def __init__(
        self,
        volume_path: Path = DEFAULT_VOLUME_PATH,
        demographic_profile_path: Path | None = DEFAULT_DEMOGRAPHIC_PROFILE_PATH,
    ) -> None:
        self._volume_path = volume_path
        self._daily = self._load_daily(volume_path)
        self._demographic_profiles = self._load_demographic_profiles(
            demographic_profile_path
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_daily(self, path: Path) -> pd.DataFrame:
        """Load and validate the daily applicant-count dataset."""
        if not path.exists():
            raise FileNotFoundError(
                f"Volume dataset not found: {path}. "
                "Run training/generate_applicant_volume_history.py first."
            )

        df = pd.read_csv(path, parse_dates=[DATE_COLUMN])

        required = {DATE_COLUMN, COURSE_COLUMN, COUNT_COLUMN}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Volume dataset is missing columns: {sorted(missing)}")

        df = df.sort_values([COURSE_COLUMN, DATE_COLUMN]).reset_index(drop=True)
        return df

    def _load_demographic_profiles(self, path: Path | None) -> pd.DataFrame:
        """Load descriptive applicant attributes for barangay profile panels."""
        if path is None or not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        if BARANGAY_COLUMN not in df.columns:
            return pd.DataFrame()
        return df

    # ------------------------------------------------------------------
    # Course-level helpers — PRIMARY ARIMA INPUT
    # ------------------------------------------------------------------

    def get_available_courses(self) -> list[str]:
        """Return courses present in the volume dataset (sorted)."""
        return sorted(self._daily[COURSE_COLUMN].unique().tolist())

    def validate_course(self, course: str) -> str:
        """Raise CourseNotFoundError when the course is unknown."""
        if course not in set(self.get_available_courses()):
            raise CourseNotFoundError(
                f"Unknown course '{course}'. "
                f"Available: {', '.join(self.get_available_courses())}"
            )
        return course

    def get_course_series(self, course: str) -> pd.Series:
        """
        Return a WEEKLY applicant-count series for one course.

        Daily counts are summed per week (week ending Sunday).
        This is the primary ARIMA input.
        """
        self.validate_course(course)
        subset = self._daily[self._daily[COURSE_COLUMN] == course].copy()
        daily = (
            subset.set_index(DATE_COLUMN)[COUNT_COLUMN]
            .astype(float)
            .sort_index()
        )
        daily.index = pd.DatetimeIndex(daily.index)
        weekly = daily.resample(WEEKLY_FREQ).sum()
        return weekly.asfreq(WEEKLY_FREQ)

    def get_course_total_historical(self, course: str) -> int:
        """Return the total daily applicant_count across all days for one course."""
        self.validate_course(course)
        return int(
            self._daily.loc[self._daily[COURSE_COLUMN] == course, COUNT_COLUMN].sum()
        )

    # ------------------------------------------------------------------
    # TLDC-wide series (all courses summed)
    # ------------------------------------------------------------------

    def get_tldc_series(self, frequency: str = "W") -> pd.Series:
        """
        Return the organisation-wide applicant total.

        Default frequency is weekly (matches the ARIMA training series).
        Pass frequency="M" for monthly totals (used by chart/summary helpers).
        """
        if self._daily.empty:
            return pd.Series(dtype=float)

        daily_total = (
            self._daily.groupby(DATE_COLUMN)[COUNT_COLUMN]
            .sum()
            .sort_index()
            .astype(float)
        )
        daily_total.index = pd.DatetimeIndex(daily_total.index)

        freq_key = _FREQ_ALIAS.get(frequency, "W")
        if freq_key == "M":
            return daily_total.resample("MS").sum().asfreq("MS")
        if freq_key == "D":
            return daily_total.asfreq("D", fill_value=0.0)
        # Default: weekly
        return daily_total.resample(WEEKLY_FREQ).sum().asfreq(WEEKLY_FREQ)

    def get_course_monthly_series(self, course: str) -> pd.Series:
        """
        Return a MONTHLY applicant-count series for one course.

        Used by chart helpers that display monthly historical trends.
        """
        self.validate_course(course)
        subset = self._daily[self._daily[COURSE_COLUMN] == course].copy()
        daily = (
            subset.set_index(DATE_COLUMN)[COUNT_COLUMN]
            .astype(float)
            .sort_index()
        )
        daily.index = pd.DatetimeIndex(daily.index)
        return daily.resample("MS").sum().asfreq("MS")

    def get_total_historical_applicants(self) -> int:
        """Return total applicants across all courses and all days."""
        return int(self._daily[COUNT_COLUMN].sum())

    def get_most_popular_course(self) -> str | None:
        """Return the course with the highest total historical applicant count."""
        if self._daily.empty:
            return None
        totals = self._daily.groupby(COURSE_COLUMN)[COUNT_COLUMN].sum()
        return str(totals.idxmax())

    # ------------------------------------------------------------------
    # Registration history (used by ForecastingStatistics)
    # ------------------------------------------------------------------

    def get_registration_history(self) -> pd.DataFrame:
        """
        Return the daily dataframe as a registration-history-compatible view.

        Used by forecasting_statistics for organisation-wide distributions.
        """
        return self._daily

    # ------------------------------------------------------------------
    # Descriptive barangay helpers (NOT used by ARIMA)
    # ------------------------------------------------------------------

    def get_demographic_profiles(self) -> pd.DataFrame:
        """Return all demographic profile records (not used by ARIMA)."""
        return self._demographic_profiles

    def get_available_barangays(self) -> list[str]:
        """Return barangays present in the demographic profiles."""
        if self._demographic_profiles.empty:
            return []
        return sorted(self._demographic_profiles[BARANGAY_COLUMN].unique().tolist())

    def validate_barangay(self, barangay: str) -> str:
        """Raise BarangayNotFoundError when the barangay is unknown."""
        available = set(self.get_available_barangays())
        if barangay not in available:
            raise BarangayNotFoundError(
                f"Unknown barangay '{barangay}'. "
                f"Available barangays: {', '.join(sorted(available))}"
            )
        return barangay

    def get_demographic_profiles_for_barangay(self, barangay: str) -> pd.DataFrame:
        """Return demographic attributes for one barangay."""
        self.validate_barangay(barangay)
        if self._demographic_profiles.empty:
            return pd.DataFrame()
        return self._demographic_profiles[
            self._demographic_profiles[BARANGAY_COLUMN] == barangay
        ]

    def get_registrations_for_barangay(self, barangay: str) -> pd.DataFrame:
        """Return demographic profile records for one barangay."""
        return self.get_demographic_profiles_for_barangay(barangay)


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_repository: ForecastingRepository | None = None


def get_forecasting_repository() -> ForecastingRepository:
    """Return the singleton forecasting repository."""
    global _repository
    if _repository is None:
        _repository = ForecastingRepository()
    return _repository
