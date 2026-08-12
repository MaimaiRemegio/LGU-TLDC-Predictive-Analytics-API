"""
Generate a synthetic DAILY applicant-volume dataset for TLDC forecasting.

IMPORTANT — SYNTHETIC DATA NOTICE
-----------------------------------
All values are synthetically generated for prototype / capstone development
only.  They do NOT represent actual TESDA or TLDC applicant records.
When real TLDC data becomes available the model must be retrained on actual
historical records.

Output
------
datasets/applicant_volume.csv

Columns
-------
date            : calendar date (YYYY-MM-DD)
course          : exact TESDA course name (canonical 21-course list)
applicant_count : synthetic daily applicants for that course (0–10, integer)

Coverage
--------
January 1 2021 – December 31 2025
  1,826 days × 21 courses = 38,346 rows

Design
------
- Each course has a distinct demand profile (average daily applicant rate).
- Daily counts are drawn from a Poisson distribution so that:
    - The expected value per day reflects the course demand level.
    - Values are naturally non-negative integers.
    - The maximum per cell is capped at 10.
- Weekend effect: Saturday/Sunday have 40 % lower expected counts.
- Monthly seasonality multipliers reduce/increase the expected count
  through the year (same pattern as before — Jan/Feb and Jul/Aug peaks).
- Mild annual growth trend is applied.
- Fixed random seed (42) guarantees reproducible output.
- No barangay column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

DATE_COLUMN = "date"
COURSE_COLUMN = "course"
COUNT_COLUMN = "applicant_count"

MAX_DAILY_COUNT = 10          # Hard cap per requirement
WEEKEND_FACTOR = 0.6          # Sat/Sun have 60% of weekday expected rate

# ---------------------------------------------------------------------------
# Canonical 21-course list
# These strings are the exact identifiers used in the TLDC database.
# Do NOT modify, abbreviate, or rename them.
# ---------------------------------------------------------------------------
CANONICAL_COURSES: list[str] = [
    "Bookkeeping NC II",
    "Computer Systems Servicing NC II",
    "Carpentry NC II",
    "Construction Painting NC II",
    "Cookery NC II",
    "Driving NC II",
    "Electrical Installation and Maintenance NC II",
    "Electronic Products Assembly and Servicing NC II",
    "HEO (Bulldozer) NC II",
    "HEO (Forklift) NC II",
    "HEO (Hydraulic Excavator) NC II",
    "HEO (Wheel Loader) NC II",
    "Landscape Installation and Maintenance (Softscape)",
    "Organic Agriculture Production NC II",
    "Machining NC I",
    "Machining NC II",
    "Masonry NC I",
    "Masonry NC II",
    "Shielded Metal Arc Welding NC I",
    "Shielded Metal Arc Welding NC II",
    "Trainers Methodology Level I",
]

assert len(CANONICAL_COURSES) == 21
assert len(set(CANONICAL_COURSES)) == 21

# ---------------------------------------------------------------------------
# Course demand profiles
#
# Each entry: (base_daily_rate, annual_growth_rate)
#
#   base_daily_rate   average applicants per WEEKDAY at the start of 2021
#                     Calibrated so monthly totals stay realistic (daily × 22
#                     working days ≈ monthly total).
#                     Scaled so MAX daily Poisson draw ≤ 10 is achievable.
#   annual_growth_rate fractional year-on-year trend
#
# Poisson λ is clipped to ≤ 9 so that P(X > 10) ≈ 0 and the cap at 10
# almost never fires.
# ---------------------------------------------------------------------------
COURSE_PROFILES: dict[str, tuple[float, float]] = {
    "Bookkeeping NC II":                                (4.5, 0.06),
    "Computer Systems Servicing NC II":                 (5.0, 0.08),
    "Carpentry NC II":                                  (3.5, 0.03),
    "Construction Painting NC II":                      (2.5, 0.03),
    "Cookery NC II":                                    (6.5, 0.06),
    "Driving NC II":                                    (6.0, 0.05),
    "Electrical Installation and Maintenance NC II":    (3.8, 0.05),
    "Electronic Products Assembly and Servicing NC II": (3.0, 0.07),
    "HEO (Bulldozer) NC II":                            (1.5, 0.04),
    "HEO (Forklift) NC II":                             (1.8, 0.04),
    "HEO (Hydraulic Excavator) NC II":                  (1.6, 0.04),
    "HEO (Wheel Loader) NC II":                         (1.7, 0.04),
    "Landscape Installation and Maintenance (Softscape)":(2.0, 0.03),
    "Organic Agriculture Production NC II":             (2.3, 0.04),
    "Machining NC I":                                   (2.0, 0.03),
    "Machining NC II":                                  (1.8, 0.03),
    "Masonry NC I":                                     (2.5, 0.02),
    "Masonry NC II":                                    (2.8, 0.02),
    "Shielded Metal Arc Welding NC I":                  (2.8, 0.03),
    "Shielded Metal Arc Welding NC II":                 (2.6, 0.03),
    "Trainers Methodology Level I":                     (1.0, 0.05),
}

assert set(COURSE_PROFILES.keys()) == set(CANONICAL_COURSES)

# Monthly seasonality multipliers (index 0 = Jan … 11 = Dec)
SEASONAL_MULTIPLIERS = np.array(
    [1.15, 1.10, 1.02, 0.93, 0.90, 0.94,
     1.08, 1.12, 1.00, 0.94, 0.91, 1.06],
    dtype=float,
)
assert len(SEASONAL_MULTIPLIERS) == 12


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build_dataset(seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Return a daily applicant-count DataFrame.

    Each (date, course) pair has applicant_count in [0, 10].
    """
    rng = np.random.default_rng(seed)

    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    start_year = dates[0].year

    rows: list[dict] = []

    for course in CANONICAL_COURSES:
        base_rate, growth_rate = COURSE_PROFILES[course]

        for date in dates:
            # Years elapsed since start (fractional).
            years_elapsed = (
                (date.year - start_year) + (date.month - 1) / 12.0
            )

            # Trend component.
            trend_rate = base_rate * ((1.0 + growth_rate) ** years_elapsed)

            # Seasonal component.
            seasonal_rate = trend_rate * SEASONAL_MULTIPLIERS[date.month - 1]

            # Weekend effect.
            if date.dayofweek >= 5:  # 5=Saturday, 6=Sunday
                lam = seasonal_rate * WEEKEND_FACTOR
            else:
                lam = seasonal_rate

            # Clip lambda so Poisson draw very rarely exceeds MAX_DAILY_COUNT.
            lam = min(lam, MAX_DAILY_COUNT - 1.0)

            # Draw from Poisson and cap.
            count = int(min(rng.poisson(lam), MAX_DAILY_COUNT))

            rows.append(
                {
                    DATE_COLUMN: date.strftime("%Y-%m-%d"),
                    COURSE_COLUMN: course,
                    COUNT_COLUMN: count,
                }
            )

    df = (
        pd.DataFrame(rows)
        .sort_values([DATE_COLUMN, COURSE_COLUMN])
        .reset_index(drop=True)
    )
    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> None:
    """Raise AssertionError if the dataset does not meet all requirements."""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    expected_rows = len(dates) * len(CANONICAL_COURSES)

    assert len(df) == expected_rows, (
        f"Expected {expected_rows} rows, got {len(df)}"
    )

    expected_cols = {DATE_COLUMN, COURSE_COLUMN, COUNT_COLUMN}
    assert set(df.columns) == expected_cols, (
        f"Unexpected columns: {set(df.columns)}"
    )

    assert df[COUNT_COLUMN].min() >= 0, "applicant_count must be >= 0"
    assert df[COUNT_COLUMN].max() <= MAX_DAILY_COUNT, (
        f"applicant_count must be <= {MAX_DAILY_COUNT}, got {df[COUNT_COLUMN].max()}"
    )

    assert df.isnull().sum().sum() == 0, "Dataset contains missing values"

    present_courses = set(df[COURSE_COLUMN].unique())
    assert present_courses == set(CANONICAL_COURSES), (
        f"Course mismatch. Missing: {set(CANONICAL_COURSES) - present_courses}"
    )

    # No duplicate (date, course) pairs.
    dupes = df.duplicated(subset=[DATE_COLUMN, COURSE_COLUMN]).sum()
    assert dupes == 0, f"{dupes} duplicate (date, course) pairs found"

    # Every course has complete daily coverage.
    for course in CANONICAL_COURSES:
        n = int((df[COURSE_COLUMN] == course).sum())
        assert n == len(dates), (
            f"Expected {len(dates)} rows for '{course}', got {n}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = build_dataset()
    validate(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")

    print("=" * 64)
    print("SYNTHETIC DAILY DATASET — applicant_volume.csv")
    print("NOTE: All values are synthetically generated.")
    print("      Not actual TESDA/TLDC applicant records.")
    print("=" * 64)
    print(f"Output          : {OUTPUT_PATH.resolve()}")
    print(f"Total rows      : {len(df):,}")
    print(f"Columns         : {list(df.columns)}")
    print(f"Unique courses  : {df[COURSE_COLUMN].nunique()}")
    print(f"Date range      : {df[DATE_COLUMN].min()} → {df[DATE_COLUMN].max()}")
    print(f"Days covered    : {len(dates):,}")
    print(f"Min count       : {df[COUNT_COLUMN].min()}")
    print(f"Max count       : {df[COUNT_COLUMN].max()}")
    print(f"Missing values  : {df.isnull().sum().sum()}")
    print(f"Duplicate pairs : {df.duplicated(subset=[DATE_COLUMN, COURSE_COLUMN]).sum()}")
    print()
    print("Sample rows (first 5):")
    print(df.head(5).to_string(index=False))
    print()
    print("Daily total range check:")
    daily_totals = df.groupby(DATE_COLUMN)[COUNT_COLUMN].sum()
    print(f"  Min daily total (all courses): {daily_totals.min()}")
    print(f"  Max daily total (all courses): {daily_totals.max()}")


if __name__ == "__main__":
    main()
