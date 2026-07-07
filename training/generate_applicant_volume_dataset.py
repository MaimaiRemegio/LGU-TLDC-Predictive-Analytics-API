"""
Generate monthly historical applicant volume data for forecasting models.

Produces one row per barangay, course, and month with realistic seasonal
patterns, long-term trends, and random variation.
"""

import random
from datetime import date
from pathlib import Path

import pandas as pd

random.seed(42)

START_YEAR = 2021
END_YEAR = 2025
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "datasets" / "applicant_volume.csv"

BARANGAYS = [
    "Abuanan", "Alianza", "Atipuluan", "Bacong", "Bagroy", "Balingasag",
    "Binubuhan", "Busay", "Calumangan", "Caridad", "Dulao", "Ilijan",
    "Lag-asan", "Ma-ao", "Mailum", "Malingin", "Napoles", "Pacol",
    "Poblacion", "Sagasa", "Tabunan", "Taloc",
]

HIGH_DEMAND_BARANGAYS = {"Poblacion", "Busay", "Ma-ao", "Taloc"}
MEDIUM_DEMAND_BARANGAYS = {"Bagroy", "Bacong", "Mailum", "Caridad", "Dulao"}

COURSES = [
    "Cookery NC II",
    "Bread and Pastry NC II",
    "Computer Systems Servicing NC II",
    "Carpentry NC II",
    "Masonry NC II",
    "Shielded Metal Arc Welding NC I",
    "Electrical Installation and Maintenance NC II",
    "Driving NC II",
]

# Base monthly applicant volume before modifiers
COURSE_BASE_VOLUME = {
    "Cookery NC II": 38,
    "Bread and Pastry NC II": 32,
    "Computer Systems Servicing NC II": 24,
    "Carpentry NC II": 22,
    "Masonry NC II": 20,
    "Shielded Metal Arc Welding NC I": 18,
    "Electrical Installation and Maintenance NC II": 17,
    "Driving NC II": 26,
}

# Monthly change in volume over the full history (positive = growth, negative = decline)
COURSE_TREND_PER_MONTH = {
    "Cookery NC II": 0.08,
    "Bread and Pastry NC II": 0.05,
    "Computer Systems Servicing NC II": 0.15,
    "Carpentry NC II": -0.03,
    "Masonry NC II": -0.02,
    "Shielded Metal Arc Welding NC I": 0.02,
    "Electrical Installation and Maintenance NC II": 0.04,
    "Driving NC II": 0.12,
}


def generate_month_dates() -> list[date]:
    """Build the first day of every month across the configured year range."""
    dates = []
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            dates.append(date(year, month, 1))
    return dates


def get_barangay_multiplier(barangay: str) -> float:
    if barangay in HIGH_DEMAND_BARANGAYS:
        return random.uniform(1.20, 1.40)
    if barangay in MEDIUM_DEMAND_BARANGAYS:
        return random.uniform(1.00, 1.15)
    return random.uniform(0.75, 0.92)


def get_seasonal_multiplier(month: int, course: str) -> float:
    multiplier = 1.0

    if month == 12:
        multiplier *= random.uniform(0.58, 0.72)

    if month in (6, 7) and course == "Computer Systems Servicing NC II":
        multiplier *= random.uniform(1.25, 1.45)

    if month in (10, 11) and course in {"Cookery NC II", "Bread and Pastry NC II"}:
        multiplier *= random.uniform(1.20, 1.38)

    if month in (3, 4) and course == "Driving NC II":
        multiplier *= random.uniform(1.10, 1.25)

    if month in (1, 2):
        multiplier *= random.uniform(0.92, 1.05)

    return multiplier


def get_trend_multiplier(course: str, month_index: int) -> float:
    monthly_change = COURSE_TREND_PER_MONTH[course]
    return max(0.70, 1.0 + (monthly_change * month_index))


def generate_applicant_count(
    month: int,
    month_index: int,
    barangay: str,
    course: str,
) -> int:
    base_volume = COURSE_BASE_VOLUME[course]
    volume = base_volume
    volume *= get_barangay_multiplier(barangay)
    volume *= get_seasonal_multiplier(month, course)
    volume *= get_trend_multiplier(course, month_index)
    volume *= random.uniform(0.85, 1.15)
    return max(8, min(95, int(round(volume))))


def build_dataset() -> pd.DataFrame:
    records = []
    month_dates = generate_month_dates()

    for month_index, record_date in enumerate(month_dates):
        month = record_date.month

        for barangay in BARANGAYS:
            for course in COURSES:
                applicant_count = generate_applicant_count(
                    month=month,
                    month_index=month_index,
                    barangay=barangay,
                    course=course,
                )
                records.append(
                    {
                        "date": record_date.isoformat(),
                        "barangay": barangay,
                        "course": course,
                        "applicant_count": applicant_count,
                    }
                )

    return pd.DataFrame(records)


def save_dataset(dataset: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)


def main() -> None:
    dataset = build_dataset()
    save_dataset(dataset, OUTPUT_PATH)
    print("Applicant volume dataset generated successfully.")
    print(f"Records: {len(dataset)}")
    print(f"Date range: {dataset['date'].min()} to {dataset['date'].max()}")


if __name__ == "__main__":
    main()
