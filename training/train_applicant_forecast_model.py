"""
Train ARIMA-based forecasting models for monthly applicant volume.

One ARIMA model is fitted per barangay and course time series. The saved
artifact supports forecasts for the next month, quarter, and 12 months.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.arima.model import ARIMA

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"
MODEL_PATH = PROJECT_ROOT / "trained_models" / "applicant_forecast_model.pkl"

DATE_COLUMN = "date"
BARANGAY_COLUMN = "barangay"
COURSE_COLUMN = "course"
TARGET_COLUMN = "applicant_count"

ARIMA_ORDER = (1, 1, 1)
HOLDOUT_MONTHS = 6

FORECAST_HORIZONS = {
    "next_month": 1,
    "next_quarter": 3,
    "next_6_months": 6,
    "next_12_months": 12,
}


def load_dataset(path: Path) -> pd.DataFrame:
    """Load applicant volume data and parse dates."""
    dataset = pd.read_csv(path)
    dataset[DATE_COLUMN] = pd.to_datetime(dataset[DATE_COLUMN])
    return dataset.sort_values([BARANGAY_COLUMN, COURSE_COLUMN, DATE_COLUMN]).reset_index(drop=True)


def get_series_groups(dataset: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    """Split the dataset into monthly applicant count series."""
    series_groups = []

    grouped = dataset.groupby([BARANGAY_COLUMN, COURSE_COLUMN], sort=True)
    for (barangay, course), group in grouped:
        series = group.set_index(DATE_COLUMN)[TARGET_COLUMN].astype(float)
        series = series.asfreq("MS")
        series_groups.append((barangay, course, series))

    return series_groups


def train_arima_model(series: pd.Series) -> ARIMA:
    """Fit an ARIMA model on a single monthly time series."""
    model = ARIMA(series, order=ARIMA_ORDER)
    return model.fit()


def evaluate_series_forecast(series: pd.Series) -> tuple[float, float]:
    """Evaluate ARIMA performance on the final holdout months."""
    if len(series) <= HOLDOUT_MONTHS + 3:
        return np.nan, np.nan

    train_series = series.iloc[:-HOLDOUT_MONTHS]
    test_series = series.iloc[-HOLDOUT_MONTHS:]

    fitted_model = train_arima_model(train_series)
    predictions = fitted_model.forecast(steps=HOLDOUT_MONTHS)
    predictions = np.asarray(predictions)

    mae = mean_absolute_error(test_series, predictions)
    rmse = np.sqrt(mean_squared_error(test_series, predictions))
    return float(mae), float(rmse)


def train_all_models(series_groups: list[tuple[str, str, pd.Series]]) -> dict[tuple[str, str], object]:
    """Train one ARIMA model for every barangay and course combination."""
    trained_models: dict[tuple[str, str], object] = {}

    for barangay, course, series in series_groups:
        fitted_model = train_arima_model(series)
        trained_models[(barangay, course)] = fitted_model

    return trained_models


def evaluate_all_models(series_groups: list[tuple[str, str, pd.Series]]) -> dict[str, float]:
    """Compute average MAE and RMSE across all valid series."""
    mae_scores: list[float] = []
    rmse_scores: list[float] = []

    for _, _, series in series_groups:
        mae, rmse = evaluate_series_forecast(series)
        if not np.isnan(mae) and not np.isnan(rmse):
            mae_scores.append(mae)
            rmse_scores.append(rmse)

    return {
        "mae": float(np.mean(mae_scores)),
        "rmse": float(np.mean(rmse_scores)),
    }


def build_forecast_bundle(
    trained_models: dict[tuple[str, str], object],
    metrics: dict[str, float],
) -> dict:
    """Package trained models and metadata for inference."""
    return {
        "models": trained_models,
        "forecast_horizons": FORECAST_HORIZONS,
        "arima_order": ARIMA_ORDER,
        "metrics": metrics,
    }


def forecast_series(model, steps: int) -> np.ndarray:
    """Generate a forecast for the requested number of months."""
    return np.asarray(model.forecast(steps=steps))


def print_sample_forecasts(
    trained_models: dict[tuple[str, str], object],
    sample_key: tuple[str, str],
) -> None:
    """Display example forecasts for one barangay and course."""
    barangay, course = sample_key
    model = trained_models[sample_key]

    print(f"\nSample forecasts for {barangay} - {course}:")
    for label, steps in FORECAST_HORIZONS.items():
        values = forecast_series(model, steps)
        rounded_values = [round(float(value), 2) for value in values]
        print(f"  {label} ({steps} month(s)): {rounded_values}")


def save_model(bundle: dict, output_path: Path) -> None:
    """Persist the trained forecasting bundle."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_path)


def main() -> None:
    dataset = load_dataset(DATASET_PATH)
    series_groups = get_series_groups(dataset)

    print(f"Loaded {len(dataset)} records across {len(series_groups)} time series.")

    metrics = evaluate_all_models(series_groups)
    print(f"MAE: {metrics['mae']:.4f}")
    print(f"RMSE: {metrics['rmse']:.4f}")

    trained_models = train_all_models(series_groups)
    bundle = build_forecast_bundle(trained_models, metrics)
    save_model(bundle, MODEL_PATH)

    sample_key = series_groups[0][:2]
    print_sample_forecasts(trained_models, sample_key)

    print("\nForecast model trained successfully.")
    print(MODEL_PATH.resolve())


if __name__ == "__main__":
    main()
