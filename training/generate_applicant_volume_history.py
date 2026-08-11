"""
Generate a synthetic monthly applicant-volume dataset for TLDC forecasting.

Output
------
datasets/applicant_volume.csv

Columns
-------
application_date  : first day of the month (YYYY-MM-DD)
course_applied    : TESDA course name
total_applications: total applicants for that course across ALL barangays

Coverage
--------
January 2021 – December 2025  →  60 months × 8 courses = 480 rows

Design notes
------------
- Barangay is NOT a column.  total_applications is already aggregated
  across all barangays, so ARIMA trains on organisation-wide volume.
- Realistic seasonality, long-term trends, course demand differences,
  and moderate random variation are baked in.
- Fixed random seed guarantees reproducible output.
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

START_YEAR = 2021
END_YEAR = 2025

APPLICATION_DATE_COLUMN = "application_date"
COURSE_COLUMN = "course_applied"
COUNT_COLUMN = "total_applications"

# Each course: (base_monthly_volume, annual_growth_rate, noise_std_fraction)
# base_monthly_volume  – approximate total TLDC-wide applicants per month
# annual_growth_rate   – fractional year-on-year trend  (+0.05 = +5 % p.a.)
# noise_std_fraction   – noise as a fraction of the base (controls variability)
COURSE_PROFILES: dict[str, tuple[float, float, float]] = {
    "Cookery NC II":                                 (420.0,  0.06, 0.10),
    "Bread and Pastry NC II":                        (310.0,  0.04, 0.10),
    "Computer Systems Servicing NC II":              (280.0,  0.08, 0.12),
    "Carpentry NC II":                               (200.0,  0.03, 0.13),
    "Masonry NC II":                                 (180.0,  0.02, 0.13),
    "Shielded Metal Arc Welding NC I":               (170.0,  0.03, 0.12),
    "Electrical Installation and Maintenance NC II": (190.0,  0.05, 0.11),
    "Driving NC II":                                 (230.0,  0.04, 0.10),
}

# Monthly seasonality multipliers (index 0 = January … index 11 = December).
# Peak enrolment in Jan/Feb (post-holiday) and Jul/Aug (mid-year intake).
SEASONAL_MULTIPLIERS = np.array(
    [1.15, 1.10, 1.00, 0.95, 0.90, 0.92,
     1.08, 1.12, 1.00, 0.95, 0.90, 1.05],
    dtype=float,
)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build_dataset(seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Return a 480-row DataFrame of monthly TLDC applicant volumes per course."""
    rng = np.random.default_rng(seed)

    dates = pd.date_range(
        start=f"{START_YEAR}-01-01",
        end=f"{END_YEAR}-12-01",
        freq="MS",
    )  # 60 monthly periods

    rows: list[dict] = []

    for course, (base, growth_rate, noise_frac) in COURSE_PROFILES.items():
        for date in dates:
            # Years elapsed since the start of the series (fractional).
            years_elapsed = (date.year - START_YEAR) + (date.month - 1) / 12.0

            # Long-term trend component.
            trend = base * ((1.0 + growth_rate) ** years_elapsed)

            # Seasonal component.
            seasonal = trend * SEASONAL_MULTIPLIERS[date.month - 1]

            # Random noise (normal, clamped to keep values positive).
            noise = rng.normal(loc=0.0, scale=seasonal * noise_frac)

            total = int(round(max(1.0, seasonal + noise)))

            rows.append(
                {
                    APPLICATION_DATE_COLUMN: date,
                    COURSE_COLUMN: course,
                    COUNT_COLUMN: total,
                }
            )

    dataframe = (
        pd.DataFrame(rows)
        .sort_values([APPLICATION_DATE_COLUMN, COURSE_COLUMN])
        .reset_index(drop=True)
    )

    return dataframe


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(dataframe: pd.DataFrame) -> None:
    """Raise AssertionError if the dataset does not meet all requirements."""
    expected_rows = 60 * len(COURSE_PROFILES)
    assert len(dataframe) == expected_rows, (
        f"Expected {expected_rows} rows, got {len(dataframe)}"
    )

    expected_cols = {APPLICATION_DATE_COLUMN, COURSE_COLUMN, COUNT_COLUMN}
    assert set(dataframe.columns) == expected_cols, (
        f"Unexpected columns: {set(dataframe.columns)}"
    )

    assert "barangay" not in dataframe.columns, "barangay column must not be present"

    assert dataframe[COUNT_COLUMN].min() >= 1, "All counts must be positive integers"

    assert dataframe.isnull().sum().sum() == 0, "Dataset contains missing values"

    assert dataframe[COURSE_COLUMN].nunique() == len(COURSE_PROFILES), (
        "Course count mismatch"
    )

    months = dataframe[APPLICATION_DATE_COLUMN].nunique()
    assert months == 60, f"Expected 60 months, got {months}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dataset = build_dataset()
    validate(dataset)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_PATH, index=False, date_format="%Y-%m-%d")

    print("=" * 60)
    print("Dataset generated successfully.")
    print(f"Output : {OUTPUT_PATH.resolve()}")
    print("=" * 60)

    print(f"\nRows            : {len(dataset)}")
    print(f"Columns         : {list(dataset.columns)}")
    print(f"Unique courses  : {dataset[COURSE_COLUMN].nunique()}")
    print(
        f"Date range      : "
        f"{dataset[APPLICATION_DATE_COLUMN].min().date()} → "
        f"{dataset[APPLICATION_DATE_COLUMN].max().date()}"
    )
    print(f"Min total_apps  : {dataset[COUNT_COLUMN].min()}")
    print(f"Max total_apps  : {dataset[COUNT_COLUMN].max()}")
    print(f"Missing values  : {dataset.isnull().sum().sum()}")
    print(f"barangay column : {'present' if 'barangay' in dataset.columns else 'absent ✓'}")

    print("\nFirst 10 rows:")
    print(dataset.head(10).to_string(index=False))

    print("\nLast 10 rows:")
    print(dataset.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
