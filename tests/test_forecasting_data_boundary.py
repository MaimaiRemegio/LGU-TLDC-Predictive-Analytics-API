"""
Test data boundary protection and gap handling in forecasting.

These tests protect against the issue where incomplete/future data
contaminated ARIMA training with artificial zero-valued months.
"""

import pandas as pd
import pytest
from services.forecasting_repository import (
    ForecastingRepository,
    HISTORICAL_CUTOFF_DATE,
)


def test_historical_cutoff_constant_is_defined():
    """Verify HISTORICAL_CUTOFF_DATE constant exists."""
    assert HISTORICAL_CUTOFF_DATE is not None
    assert isinstance(HISTORICAL_CUTOFF_DATE, str)
    # Should match dataset generator END_DATE
    assert HISTORICAL_CUTOFF_DATE == "2025-12-31"


def test_get_course_series_respects_cutoff(tmp_path):
    """
    Verify get_course_series() excludes data after HISTORICAL_CUTOFF_DATE.
    
    This prevents incomplete/future data from entering ARIMA training.
    """
    # Create test dataset with data beyond cutoff
    csv_path = tmp_path / "test_volume.csv"
    data = []
    
    # Add 2025 data (should be included)
    for day in range(1, 32):
        data.append({
            "date": f"2025-12-{day:02d}",
            "course": "Test Course",
            "applicant_count": 5
        })
    
    # Add 2026 data (should be excluded)
    for day in range(1, 11):
        data.append({
            "date": f"2026-01-{day:02d}",
            "course": "Test Course",
            "applicant_count": 5
        })
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    
    # Load via repository
    repo = ForecastingRepository(volume_path=csv_path, demographic_profile_path=None)
    series = repo.get_course_series("Test Course")
    
    # Verify: series should not contain 2026 data
    # Note: Weekly resampling with W-SUN can have a week ending in early Jan 2026
    # that includes late Dec 2025 days. This is acceptable.
    # The key is no weeks deep into 2026.
    last_week = series.index.max()
    assert last_week.year == 2026 and last_week.month == 1 and last_week.day <= 7, \
        f"Last week should be first week of Jan 2026 (covering late Dec 2025), got {last_week}"
    
    # Count weeks in December 2025
    dec_2025_weeks = series[series.index >= "2025-12-01"]
    assert len(dec_2025_weeks) >= 4  # At least 4 weeks in December


def test_get_tldc_series_weekly_respects_cutoff(tmp_path):
    """
    Verify get_tldc_series(frequency='W') respects HISTORICAL_CUTOFF_DATE.
    
    Weekly series is used for ARIMA training.
    """
    csv_path = tmp_path / "test_volume.csv"
    data = []
    
    # Add data through 2025 and into 2026
    courses = ["Course A", "Course B"]
    for course in courses:
        for month in [12, 1]:  # Dec 2025, Jan 2026
            year = 2025 if month == 12 else 2026
            for day in range(1, 6):
                data.append({
                    "date": f"{year}-{month:02d}-{day:02d}",
                    "course": course,
                    "applicant_count": 3
                })
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    
    repo = ForecastingRepository(volume_path=csv_path, demographic_profile_path=None)
    series = repo.get_tldc_series(frequency="W")
    
    # Verify weekly series does not include 2026
    assert series.index.max() <= pd.to_datetime("2026-01-04")  # First week might overlap
    # But check that we don't have weeks deep into 2026
    assert not any(idx.year == 2026 and idx.month > 1 for idx in series.index)


def test_get_tldc_series_monthly_includes_all_data(tmp_path):
    """
    Verify get_tldc_series(frequency='M') returns all data for charts.
    
    Monthly series is used for dashboard charts, not ARIMA training,
    so it should include all available data.
    """
    csv_path = tmp_path / "test_volume.csv"
    data = []
    
    for month in [12, 1]:
        year = 2025 if month == 12 else 2026
        data.append({
            "date": f"{year}-{month:02d}-15",
            "course": "Test Course",
            "applicant_count": 10
        })
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    
    repo = ForecastingRepository(volume_path=csv_path, demographic_profile_path=None)
    series = repo.get_tldc_series(frequency="M")
    
    # Monthly charts should show all data (including 2026 if present)
    # This is intentional - charts show current state
    assert len(series) >= 2


def test_gap_in_data_creates_zero_months_with_resample():
    """
    Demonstrate that .resample() fills gaps with zeros.
    
    This is the root cause of the artificial zero problem.
    When daily data has a gap (e.g., 2025-12-31 → 2026-08-10),
    .resample('MS').sum() creates intermediate months with value 0.0.
    """
    # Create series with gap
    dates = pd.DatetimeIndex(['2025-12-31', '2026-08-10'])
    values = pd.Series([100, 50], index=dates)
    
    # Resample to monthly
    monthly = values.resample('MS').sum()
    
    # Verify gap months exist with value 0
    assert len(monthly) == 9  # Dec 2025 through Aug 2026
    
    # Check that Jan-Jul 2026 are zero
    jan_2026 = monthly.loc['2026-01-01']
    assert jan_2026 == 0.0
    
    jul_2026 = monthly.loc['2026-07-01']
    assert jul_2026 == 0.0
    
    # This demonstrates the root cause


def test_cutoff_prevents_gap_zero_contamination(tmp_path):
    """
    Verify that HISTORICAL_CUTOFF_DATE prevents gap-zeros from entering training.
    
    This is the regression test for the main bug:
    - Dataset has 2025-12-31 data
    - Dataset jumps to 2026-08-10 (test artifacts)
    - Without cutoff: .resample() creates Jan-Jul 2026 = 0
    - With cutoff: only 2025 data used, no artificial zeros
    """
    csv_path = tmp_path / "test_volume.csv"
    data = []
    
    # Add complete 2025 December data
    for day in range(1, 32):
        data.append({
            "date": f"2025-12-{day:02d}",
            "course": "Test Course",
            "applicant_count": 5
        })
    
    # Add 2026 August data (simulating test artifacts)
    for day in range(10, 20):
        data.append({
            "date": f"2026-08-{day:02d}",
            "course": "Test Course",
            "applicant_count": 5
        })
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    
    repo = ForecastingRepository(volume_path=csv_path, demographic_profile_path=None)
    
    # Get training series (should respect cutoff)
    training_series = repo.get_course_series("Test Course")
    
    # Verify: no 2026 data beyond first week
    # (First week of 2026 can include late Dec 2025 days due to W-SUN aggregation)
    last_week = training_series.index.max()
    assert last_week.year == 2026 and last_week.month == 1 and last_week.day <= 7, \
        f"Should only have first week of 2026, got {last_week}"
    
    # Most importantly: no weeks in Feb-Aug 2026
    assert not any(idx.year == 2026 and idx.month >= 2 for idx in training_series.index), \
        "Should not have any weeks in Feb 2026 or later"
    
    # If we aggregated to monthly without cutoff, we'd see:
    # 2025-12, 2026-01=0, 2026-02=0, ..., 2026-07=0, 2026-08
    # But with cutoff, we only see up to 2025-12
    
    # This test passes because get_course_series() now filters
    # to HISTORICAL_CUTOFF_DATE before resampling


def test_get_data_date_range_returns_cutoff():
    """
    Verify get_data_date_range() returns HISTORICAL_CUTOFF_DATE as end date.
    
    This ensures model registry shows correct training boundaries.
    """
    repo = ForecastingRepository()
    start, end = repo.get_data_date_range()
    
    # End date should be cutoff, not max date in CSV
    assert end == "2025-12-31"
    assert start == "2021-01-01"


def test_course_series_has_expected_weekly_observations():
    """
    Verify weekly observations count matches 2021-2025 date range.
    
    From 2021-01-01 to 2025-12-31 is approximately:
    - 5 years × 52 weeks/year = 260 weeks
    - Actual: 261 or 262 depending on week boundaries
    """
    repo = ForecastingRepository()
    
    # Pick a course that definitely exists
    courses = repo.get_available_courses()
    assert len(courses) > 0
    
    test_course = courses[0]
    series = repo.get_course_series(test_course)
    
    # Should be around 260-262 weekly observations for 2021-2025
    assert 260 <= len(series) <= 263
    
    # Should NOT be 299 (which would include 2026 data)
    assert len(series) < 299
