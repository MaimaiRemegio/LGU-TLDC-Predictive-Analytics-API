"""
Chronological time-series backtesting for Applicant Volume Forecasting.

Independent from:
  - forecasting_service.py (live ARIMA forecasts)
  - Barangay Recommendation / Random Forest

Uses only registration history from ForecastingRepository
(datasets/applicant_volume_history.csv). Never reads historical_training.csv.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from services.forecasting_repository import (
    ForecastingRepository,
    get_forecasting_repository,
)

ARIMA_ORDER = (1, 1, 1)
DEFAULT_TRAIN_RATIO = 0.8
MIN_TRAINING_PERIODS = 12
EVALUATION_FREQUENCY = "W"

# MAPE assessment thresholds (percent). Configurable.
MAPE_EXCELLENT_MAX = 5.0
MAPE_GOOD_MAX = 10.0
MAPE_ACCEPTABLE_MAX = 20.0

EVALUATION_NOTE = (
    "This model was evaluated using synthetic historical applicant data. "
    "Accuracy results demonstrate prototype forecasting performance only. "
    "Once real TLDC applicant records become available, the model must be "
    "retrained and re-evaluated using actual historical data."
)

ACCURACY_SCOPE = "Model accuracy on synthetic data"
REAL_DATA_DISCLAIMER = (
    "Expected accuracy on future real TLDC data is unknown until the model "
    "is retrained and re-evaluated on actual historical records. "
    "These results do not validate the model for production TLDC use."
)


@dataclass(frozen=True)
class MetricResult:
    mape: float | None
    mae: float | None
    rmse: float | None
    test_periods: int
    mape_periods: int
    actuals: list[float]
    predictions: list[float]


def chronological_split_index(n: int, train_ratio: float = DEFAULT_TRAIN_RATIO) -> int:
    """Return the first test index for an 80/20 chronological split."""
    if n < 2:
        raise ValueError("Series must contain at least 2 periods for backtesting.")
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1 (exclusive).")

    split = int(np.floor(n * train_ratio))
    # Ensure both sides have at least one period when possible.
    split = max(1, min(split, n - 1))
    return split


def classify_mape(mape: float | None) -> str:
    """Map MAPE percent to a human-readable assessment label."""
    if mape is None:
        return "Needs Improvement"
    if mape < MAPE_EXCELLENT_MAX:
        return "Excellent"
    if mape < MAPE_GOOD_MAX:
        return "Good"
    if mape < MAPE_ACCEPTABLE_MAX:
        return "Acceptable"
    return "Needs Improvement"


def compute_forecast_metrics(
    actuals: list[float] | np.ndarray,
    predictions: list[float] | np.ndarray,
) -> MetricResult:
    """
    Compute MAE, RMSE, and MAPE from paired actual vs predicted values.

    MAPE excludes periods where actual == 0 to avoid division by zero.
    MAE and RMSE include all paired periods.
    """
    y = np.asarray(actuals, dtype=float)
    yhat = np.asarray(predictions, dtype=float)

    if y.shape != yhat.shape:
        raise ValueError("actuals and predictions must have the same shape.")
    if len(y) == 0:
        return MetricResult(
            mape=None,
            mae=None,
            rmse=None,
            test_periods=0,
            mape_periods=0,
            actuals=[],
            predictions=[],
        )

    errors = y - yhat
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    positive_mask = y > 0
    mape_periods = int(positive_mask.sum())
    if mape_periods == 0:
        mape = None
    else:
        mape = float(
            np.mean(np.abs(errors[positive_mask] / y[positive_mask])) * 100.0
        )

    return MetricResult(
        mape=None if mape is None else round(mape, 2),
        mae=round(mae, 2),
        rmse=round(rmse, 2),
        test_periods=int(len(y)),
        mape_periods=mape_periods,
        actuals=[round(float(v), 4) for v in y],
        predictions=[round(float(v), 4) for v in yhat],
    )


def _fit_one_step_forecast(train_series: pd.Series) -> float:
    """Fit ARIMA on train_series and return a non-negative one-step forecast."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ARIMA(train_series, order=ARIMA_ORDER).fit()
        prediction = float(np.asarray(fitted.forecast(steps=1), dtype=float)[0])
    return max(0.0, prediction)


def walk_forward_backtest(
    series: pd.Series,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    min_training_periods: int = MIN_TRAINING_PERIODS,
) -> MetricResult:
    """
    Expanding-window one-step-ahead backtest on a chronological series.

    For each test index t in [split, n):
      - train on series.iloc[:t] only
      - forecast one step
      - compare to series.iloc[t]
    """
    if series is None or series.empty:
        return compute_forecast_metrics([], [])

    values = series.astype(float)
    n = len(values)
    split = chronological_split_index(n, train_ratio=train_ratio)

    if split < min_training_periods:
        return compute_forecast_metrics([], [])

    actuals: list[float] = []
    predictions: list[float] = []

    for test_index in range(split, n):
        train = values.iloc[:test_index]
        if len(train) < min_training_periods:
            continue
        forecast = _fit_one_step_forecast(train)
        actuals.append(float(values.iloc[test_index]))
        predictions.append(forecast)

    return compute_forecast_metrics(actuals, predictions)


def _format_period_range(series: pd.Series, start: int, end: int) -> str:
    """Format inclusive index range as YYYY-MM-DD to YYYY-MM-DD."""
    if series.empty or start > end or start < 0 or end >= len(series):
        return "N/A"
    start_date = pd.Timestamp(series.index[start]).strftime("%Y-%m-%d")
    end_date = pd.Timestamp(series.index[end]).strftime("%Y-%m-%d")
    return f"{start_date} to {end_date}"


class ForecastingEvaluationService:
    """Run and cache chronological ARIMA backtesting results."""

    def __init__(
        self,
        repository: ForecastingRepository | None = None,
        train_ratio: float = DEFAULT_TRAIN_RATIO,
        min_training_periods: int = MIN_TRAINING_PERIODS,
    ) -> None:
        self._repository = repository or get_forecasting_repository()
        self._train_ratio = train_ratio
        self._min_training_periods = min_training_periods
        self._cached_result: dict | None = None

    def evaluate(self, force_refresh: bool = False) -> dict:
        """Return overall and barangay-level backtesting metrics."""
        if self._cached_result is not None and not force_refresh:
            return self._cached_result

        overall_series = self._repository.get_tldc_series(EVALUATION_FREQUENCY)
        n = len(overall_series)
        split = chronological_split_index(n, train_ratio=self._train_ratio)

        overall_metrics = walk_forward_backtest(
            overall_series,
            train_ratio=self._train_ratio,
            min_training_periods=self._min_training_periods,
        )

        barangay_results: list[dict] = []
        skipped: list[dict] = []

        for barangay in self._repository.get_available_barangays():
            series = self._repository.get_barangay_series(
                barangay,
                frequency=EVALUATION_FREQUENCY,
            )
            barangay_split = chronological_split_index(
                len(series),
                train_ratio=self._train_ratio,
            )
            if barangay_split < self._min_training_periods:
                skipped.append(
                    {
                        "barangay": barangay,
                        "reason": (
                            f"Insufficient training history "
                            f"({barangay_split} < {self._min_training_periods} weeks)."
                        ),
                    }
                )
                continue

            metrics = walk_forward_backtest(
                series,
                train_ratio=self._train_ratio,
                min_training_periods=self._min_training_periods,
            )
            if metrics.test_periods == 0:
                skipped.append(
                    {
                        "barangay": barangay,
                        "reason": "No successful walk-forward forecasts were produced.",
                    }
                )
                continue

            barangay_results.append(
                {
                    "barangay": barangay,
                    "mape": metrics.mape,
                    "mae": metrics.mae,
                    "rmse": metrics.rmse,
                    "test_periods": metrics.test_periods,
                }
            )

        barangay_results.sort(
            key=lambda item: (
                item["mape"] is None,
                item["mape"] if item["mape"] is not None else float("inf"),
            )
        )

        result = {
            "data_source": "datasets/applicant_volume_history.csv",
            "dataset_type": "synthetic",
            "evaluation_method": "Chronological time-series backtesting",
            "frequency": "weekly",
            "arima_order": list(ARIMA_ORDER),
            "train_ratio": self._train_ratio,
            "training_period": _format_period_range(
                overall_series,
                0,
                split - 1,
            ),
            "testing_period": _format_period_range(
                overall_series,
                split,
                n - 1,
            ),
            "overall": {
                "mape": overall_metrics.mape,
                "mae": overall_metrics.mae,
                "rmse": overall_metrics.rmse,
                "test_periods": overall_metrics.test_periods,
                "mape_periods": overall_metrics.mape_periods,
            },
            "model_assessment": classify_mape(overall_metrics.mape),
            "accuracy_scope": ACCURACY_SCOPE,
            "real_data_disclaimer": REAL_DATA_DISCLAIMER,
            "barangay_results": barangay_results,
            "skipped_barangays": skipped,
            "note": EVALUATION_NOTE,
        }

        self._cached_result = result
        return result


_evaluation_service: ForecastingEvaluationService | None = None


def get_forecasting_evaluation_service() -> ForecastingEvaluationService:
    """Return the singleton evaluation service (lazy compute on first evaluate())."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = ForecastingEvaluationService()
    return _evaluation_service


def reset_forecasting_evaluation_service() -> None:
    """Clear the singleton (useful for tests)."""
    global _evaluation_service
    _evaluation_service = None


__all__ = [
    "ARIMA_ORDER",
    "DEFAULT_TRAIN_RATIO",
    "MAPE_ACCEPTABLE_MAX",
    "MAPE_EXCELLENT_MAX",
    "MAPE_GOOD_MAX",
    "MIN_TRAINING_PERIODS",
    "ForecastingEvaluationService",
    "MetricResult",
    "chronological_split_index",
    "classify_mape",
    "compute_forecast_metrics",
    "get_forecasting_evaluation_service",
    "reset_forecasting_evaluation_service",
    "walk_forward_backtest",
]
