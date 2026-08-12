"""
Unit tests for time-scale–correct growth and trend calculations.

Verifies that:
  A. next_week uses genuine weekly ARIMA forecast (not monthly/4.33).
  B. next_month compares weekly-average forecast against weekly history.
  C. next_quarter compares weekly-average forecast against weekly history.
  D. growth percentages use matching weekly units.
  E. trend labels use the corrected growth values.
  F. ARIMA forecast values themselves are not changed by the comparison fix.
  G. Barangay Recommendation code is not imported or touched.

Architecture:
  - Source data: daily observations
  - Repository aggregates: daily → weekly
  - Model: ARIMA(1,1,1) on weekly series
  - Forecast horizons:
    * next_week = ARIMA step 1
    * next_month = sum of ARIMA steps 1-4
    * next_quarter = sum of ARIMA steps 1-13
  - Growth baseline: mean of last 4 weeks (weekly average)
  - Growth comparison:
    * next_week: step 1 vs recent_weekly_avg
    * next_month: sum(steps 1-4)/4 vs recent_weekly_avg
    * next_quarter: sum(steps 1-13)/13 vs recent_weekly_avg
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from services.forecasting_service import (
    ForecastingService,
    STEPS_NEXT_WEEK,
    STEPS_NEXT_MONTH,
    STEPS_NEXT_QUARTER,
    RECENT_PERIODS_FOR_TREND,
    TREND_STABLE_THRESHOLD_PERCENT,
)


# ---------------------------------------------------------------------------
# Stub repository — no real CSV or PKL needed for these unit tests
# ---------------------------------------------------------------------------

class StubRepository:
    """Minimal repository that serves a single synthetic course with WEEKLY series."""

    # Weekly series: 12 weeks all at exactly 100 (weekly applicants)
    _series = pd.Series(
        [100.0] * 12,
        index=pd.date_range("2024-01-01", periods=12, freq="W"),
    )

    def get_available_courses(self) -> list[str]:
        return ["Test Course"]

    def get_course_series(self, course: str) -> pd.Series:
        """Return weekly aggregated series."""
        return self._series

    def get_course_total_historical(self, course: str) -> int:
        return int(self._series.sum())

    def get_tldc_series(self, frequency: str = "W") -> pd.Series:
        """Return TLDC-wide weekly series."""
        return self._series

    def get_total_historical_applicants(self) -> int:
        return int(self._series.sum())

    def get_most_popular_course(self) -> str | None:
        return "Test Course"

    def get_available_barangays(self) -> list[str]:
        return []

    def validate_course(self, course: str) -> str:
        return course


class StubStatistics:
    def get_organization_distributions(self) -> dict:
        return {
            "most_popular_course": "Test Course",
            "most_common_employment_status": None,
            "most_common_educational_attainment": None,
            "employment_distribution": [],
            "education_distribution": [],
            "course_distribution": [],
            "sex_distribution": [],
            "age_distribution": [],
            "learner_classification_distribution": [],
            "barangay_distribution": [],
        }

    def get_barangay_profile(self, barangay: str) -> dict:
        return {}


# ---------------------------------------------------------------------------
# Build a service with controlled ARIMA forecasts via monkeypatching
# ---------------------------------------------------------------------------

def _make_service(weekly_preds: list[float]) -> ForecastingService:
    """
    Return a ForecastingService whose ARIMA output is replaced with
    the supplied weekly_preds list — no actual ARIMA fitting occurs.
    """
    svc = ForecastingService.__new__(ForecastingService)
    svc._repository = StubRepository()
    svc._statistics = StubStatistics()
    svc._weekly_series = {"Test Course": StubRepository._series}
    svc._weekly_models = {"Test Course": None}
    svc._weekly_forecast = {"Test Course": weekly_preds}
    svc._cached_distributions = None
    svc._cached_course_forecasts = {}
    return svc


# ---------------------------------------------------------------------------
# Shared known values
#
# Historical weekly series: all 100.  recent_weekly_avg = 100 (last 4 weeks).
# Forecasts: [120, 112, 108, ...]   (week 1 = 120, clearly above baseline)
# ---------------------------------------------------------------------------
WEEKLY_PREDS = [120.0, 115.0, 112.0, 110.0, 108.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0, 99.0]
RECENT_AVG = 100.0   # mean of last 4 values in the stub weekly series

# Expected growth values (pre-computed for clarity in assertions)
# next_week: week_1 (120) vs baseline (100) → +20%
EXPECTED_WEEK_GROWTH = round(((120.0 - RECENT_AVG) / RECENT_AVG) * 100, 1)  # +20.0

# next_month: avg(steps 1-4) vs baseline (100)
MONTH_WEEKLY_AVG = (120.0 + 115.0 + 112.0 + 110.0) / 4  # 114.25
EXPECTED_MONTH_GROWTH = round(((MONTH_WEEKLY_AVG - RECENT_AVG) / RECENT_AVG) * 100, 1)  # +14.3

# next_quarter: avg(steps 1-13) vs baseline (100)
QUARTER_WEEKLY_AVG = sum(WEEKLY_PREDS[:13]) / 13  # 108.0
EXPECTED_QUARTER_GROWTH = round(((QUARTER_WEEKLY_AVG - RECENT_AVG) / RECENT_AVG) * 100, 1)  # +8.0


# ---------------------------------------------------------------------------
# A. next_week: genuine weekly ARIMA forecast (not monthly/4.33)
# ---------------------------------------------------------------------------

def test_next_week_is_genuine_weekly_forecast():
    """next_week must be ARIMA step 1, not monthly forecast / 4.33"""
    svc = _make_service(WEEKLY_PREDS)
    items = svc.get_course_forecasts(period="next_week")
    item = items[0]

    # forecasted_applicant_count must be the raw weekly value (step 1)
    assert item["forecasted_applicant_count"] == 120.0, (
        f"next_week should be {WEEKLY_PREDS[0]}, got {item['forecasted_applicant_count']}"
    )

    # growth_percentage: week_1 (120) vs recent_weekly_avg (100)
    assert item["growth_percentage"] == EXPECTED_WEEK_GROWTH, (
        f"next_week growth should be {EXPECTED_WEEK_GROWTH}, got {item['growth_percentage']}"
    )
    assert item["trend"] == "Increasing"


# ---------------------------------------------------------------------------
# B. next_month: weekly-average forecast vs weekly-average history
# ---------------------------------------------------------------------------

def test_next_month_growth_uses_weekly_average_comparison():
    svc = _make_service(WEEKLY_PREDS)
    items = svc.get_course_forecasts(period="next_month")
    assert len(items) == 1
    item = items[0]

    # forecasted_applicant_count is the SUM of 4 weekly forecasts
    expected_month_total = sum(WEEKLY_PREDS[:STEPS_NEXT_MONTH])
    assert item["forecasted_applicant_count"] == expected_month_total, (
        f"next_month should be {expected_month_total}, got {item['forecasted_applicant_count']}"
    )

    # growth_percentage: avg(steps 1-4) vs recent_weekly_avg
    assert item["growth_percentage"] == EXPECTED_MONTH_GROWTH, (
        f"next_month growth should be {EXPECTED_MONTH_GROWTH}, got {item['growth_percentage']}"
    )
    assert item["trend"] == "Increasing"


# ---------------------------------------------------------------------------
# C. next_quarter: weekly-average forecast vs weekly-average history
# ---------------------------------------------------------------------------

def test_next_quarter_growth_uses_weekly_average_not_raw_total():
    svc = _make_service(WEEKLY_PREDS)
    items = svc.get_course_forecasts(period="next_quarter")
    item = items[0]

    # forecasted_applicant_count is the SUM of 13 weekly forecasts
    quarter_total = sum(WEEKLY_PREDS[:STEPS_NEXT_QUARTER])
    assert item["forecasted_applicant_count"] == quarter_total, (
        f"next_quarter should be {quarter_total}, got {item['forecasted_applicant_count']}"
    )

    # growth_percentage must NOT be (total - recent_avg) / recent_avg
    # It must compare (quarter_total/13) vs recent_weekly_avg
    assert item["growth_percentage"] == EXPECTED_QUARTER_GROWTH, (
        f"next_quarter growth should be {EXPECTED_QUARTER_GROWTH}, got {item['growth_percentage']}"
    )
    assert item["trend"] == "Increasing"


# ---------------------------------------------------------------------------
# D & E. Trend labels match corrected growth values
# ---------------------------------------------------------------------------

def test_trend_stable_when_growth_within_threshold():
    # Forecasts slightly below baseline (within ±5%)
    # baseline = 100, forecast week 1 = 99.6 → growth = -0.4%
    preds = [99.6, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 89.0, 88.0]
    svc = _make_service(preds)
    items = svc.get_course_forecasts(period="next_week")
    assert items[0]["trend"] == "Stable"
    assert abs(items[0]["growth_percentage"]) <= TREND_STABLE_THRESHOLD_PERCENT


def test_trend_decreasing_when_growth_below_minus_5pct():
    # baseline = 100, forecast week 1 = 90 → growth = -10%
    preds = [90.0, 88.0, 86.0, 84.0, 82.0, 80.0, 78.0, 76.0, 74.0, 72.0, 70.0, 68.0, 66.0]
    svc = _make_service(preds)
    items = svc.get_course_forecasts(period="next_week")
    assert items[0]["trend"] == "Decreasing"
    assert items[0]["growth_percentage"] < -TREND_STABLE_THRESHOLD_PERCENT


# ---------------------------------------------------------------------------
# F. ARIMA forecast values themselves are unchanged
# ---------------------------------------------------------------------------

def test_arima_forecast_values_are_not_altered():
    """
    forecast_next_week / next_month / next_quarter must equal the raw
    ARIMA predictions — the growth fix must not modify these values.
    """
    svc = _make_service(WEEKLY_PREDS)
    items = svc.get_course_forecasts(period="next_week")
    item = items[0]

    # Check that the raw forecast fields contain correct values
    assert item["forecast_next_week"] == WEEKLY_PREDS[0]  # step 1
    assert item["forecast_next_month"] == sum(WEEKLY_PREDS[:STEPS_NEXT_MONTH])  # sum of 4 weeks
    assert item["forecast_next_quarter"] == sum(WEEKLY_PREDS[:STEPS_NEXT_QUARTER])  # sum of 13 weeks


# ---------------------------------------------------------------------------
# G. All three periods: growth units are self-consistent
# ---------------------------------------------------------------------------

def test_all_three_periods_use_weekly_average_comparison():
    """
    next_week, next_month, and next_quarter all use weekly-average comparison.
    All growth percentages should be positive and reasonable (no unit-mismatch).
    """
    svc = _make_service(WEEKLY_PREDS)

    week_items  = svc.get_course_forecasts(period="next_week")
    month_items = svc.get_course_forecasts(period="next_month")
    qtr_items   = svc.get_course_forecasts(period="next_quarter")

    # All three must show positive growth (forecasts are above baseline)
    for item, label in [(week_items[0], "next_week"), (month_items[0], "next_month"), (qtr_items[0], "next_quarter")]:
        assert item["growth_percentage"] > 0, (
            f"{label} should show positive growth for forecasts above baseline"
        )
        assert item["growth_percentage"] < 100.0, (
            f"{label} growth should not be absurdly large (no unit-mismatch inflation)"
        )
        assert item["trend"] == "Increasing", (
            f"{label} trend should be Increasing when growth > {TREND_STABLE_THRESHOLD_PERCENT}%"
        )

    # Week should have highest growth (single week above average)
    # Quarter should have lowest growth (averaging over 13 weeks brings it down)
    assert week_items[0]["growth_percentage"] > qtr_items[0]["growth_percentage"], (
        "next_week growth should be higher than next_quarter (less averaging)"
    )

