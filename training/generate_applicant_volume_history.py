"""
Generate event-level applicant registration history for ARIMA forecasting.

Each row is one historical registration:

    application_date, barangay, course_applied

This dataset is intentionally separate from historical_training.csv, which
stores applicant attributes and training outcomes for the Random Forest
barangay-recommendation model and is not a time-series registration log.
"""

from __future__ import annotations

import calendar
import random
from pathlib import Path

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_VOLUME_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"
OUTPUT_PATH = PROJECT_ROOT / "datasets" / "applicant_volume_history.csv"

APPLICATION_DATE_COLUMN = "application_date"
BARANGAY_COLUMN = "barangay"
COURSE_COLUMN = "course_applied"


def build_registration_history(source_path: Path = SOURCE_VOLUME_PATH) -> pd.DataFrame:
    """
    Build an event-level registration history from monthly volume totals.

    Each monthly aggregate row is expanded into individual application events
    with dates spread across that month, enabling day/week/month aggregation.
    """
    if not source_path.exists():
        raise FileNotFoundError(
            f"Source volume dataset not found: {source_path}. "
            "Generate datasets/applicant_volume.csv first."
        )

    volume = pd.read_csv(source_path, parse_dates=["date"])
    volume = volume[volume["applicant_count"] > 0].copy()
    volume["year"] = volume["date"].dt.year
    volume["month"] = volume["date"].dt.month
    volume["days_in_month"] = volume.apply(
        lambda row: calendar.monthrange(int(row["year"]), int(row["month"]))[1],
        axis=1,
    )

    application_dates: list[np.ndarray] = []
    barangays: list[np.ndarray] = []
    courses: list[np.ndarray] = []

    for _, row in volume.iterrows():
        count = int(row["applicant_count"])
        month_start = pd.Timestamp(year=int(row["year"]), month=int(row["month"]), day=1)
        day_offsets = np.random.randint(0, int(row["days_in_month"]), size=count)
        dates = month_start + pd.to_timedelta(day_offsets, unit="D")

        application_dates.append(dates.values.astype("datetime64[ns]"))
        barangays.append(np.repeat(str(row["barangay"]), count))
        courses.append(np.repeat(str(row["course"]), count))

    history = pd.DataFrame(
        {
            APPLICATION_DATE_COLUMN: np.concatenate(application_dates),
            BARANGAY_COLUMN: np.concatenate(barangays),
            COURSE_COLUMN: np.concatenate(courses),
        }
    )
    history = history.sort_values(
        [APPLICATION_DATE_COLUMN, BARANGAY_COLUMN, COURSE_COLUMN]
    ).reset_index(drop=True)
    return history


def main() -> None:
    history = build_registration_history()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(OUTPUT_PATH, index=False)

    print("Applicant volume history generated successfully.")
    print(f"Output: {OUTPUT_PATH.resolve()}")
    print(f"Registration events: {len(history):,}")
    print(
        f"Date range: {history[APPLICATION_DATE_COLUMN].min().date()} -> "
        f"{history[APPLICATION_DATE_COLUMN].max().date()}"
    )
    print(f"Barangays: {history[BARANGAY_COLUMN].nunique()}")
    print(f"Courses: {history[COURSE_COLUMN].nunique()}")


if __name__ == "__main__":
    main()
