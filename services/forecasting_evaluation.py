"""
Chronological time-series backtesting for Applicant Volume Forecasting.

Evaluates one ARIMA model per course using walk-forward backtesting.
Independent from the Barangay Recommendation / Random Forest module.

Data source: datasets/applicant_volume.csv via ForecastingRepository.
historical_training.csv is never read here.
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
EVALUATION_FREQUENCY = "W"      # Weekly — matches the ARIMA training series.

MAPE_EXCELLENT_MAX = 5.0
MAPE_GOOD_MAX = 10.0
MAPE_ACCEPTABLE_MAX = 20.0

EVALUATION_NOTE = (
    "This model was evaluated using synthetic historical applicant data aggregated "
    "to weekly totals.  Accuracy results demonstrate prototype forecasting performance "
    "only.  Once real TLDC applicant records become available, the model must be "
    "retrained and re-evaluated using actual historical data."
)
ACCURACY_SCOPE = "Model accuracy on synthetic weekly course-level data"
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


def chronological_split_index(
    n: int,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
) -> int:
    """Return the first test index for a chronological train/test split."""
    if n < 2:
        raise ValueError("Series must contain at least 2 periods for backtesting.")
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1 (exclusive).")
    split = int(np.floor(n * train_ratio))
    return max(1, min(split, n - 1))


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
    Compute MAE, RMSE, and MAPE.

    MAPE excludes periods where actual == 0 to avoid division by zero.
    """
    y = np.asarray(actuals, dtype=float)
    yhat = np.asarray(predictions, dtype=float)

    if y.shape != yhat.shape:
        raise ValueError("actuals and predictions must have the same shape.")
    if len(y) == 0:
        return MetricResult(
            mape=None, mae=None, rmse=None,
            test_periods=0, mape_periods=0,
            actuals=[], predictions=[],
        )

    errors = y - yhat
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    positive_mask = y > 0
    mape_periods = int(positive_mask.sum())
    mape = (
        None
        if mape_periods == 0
        else float(
            np.mean(np.abs(errors[positive_mask] / y[positive_mask])) * 100.0
        )
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
        pred = float(np.asarray(fitted.forecast(steps=1), dtype=float)[0])
    return max(0.0, pred)


def walk_forward_backtest(
    series: pd.Series,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    min_training_periods: int = MIN_TRAINING_PERIODS,
) -> MetricResult:
    """Expanding-window one-step-ahead backtest on a chronological series."""
    if series is None or series.empty:
        return compute_forecast_metrics([], [])

    values = series.astype(float)
    n = len(values)
    split = chronological_split_index(n, train_ratio=train_ratio)

    if split < min_training_periods:
        return compute_forecast_metrics([], [])

    actuals: list[float] = []
    predictions: list[float] = []

    for t in range(split, n):
        train = values.iloc[:t]
        if len(train) < min_training_periods:
            continue
        actuals.append(float(values.iloc[t]))
        predictions.append(_fit_one_step_forecast(train))

    return compute_forecast_metrics(actuals, predictions)


def _format_period_range(series: pd.Series, start: int, end: int) -> str:
    if series.empty or start > end or start < 0 or end >= len(series):
        return "N/A"
    s = pd.Timestamp(series.index[start]).strftime("%Y-%m-%d")
    e = pd.Timestamp(series.index[end]).strftime("%Y-%m-%d")
    return f"{s} to {e}"


class ForecastingEvaluationService:
    """Run and cache chronological ARIMA backtesting results per course."""

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
        """Return overall and per-course backtesting metrics."""
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

        course_results: list[dict] = []
        skipped: list[dict] = []

        for course in self._repository.get_available_courses():
            series = self._repository.get_course_series(course)
            course_split = chronological_split_index(
                len(series), train_ratio=self._train_ratio
            )
            if course_split < self._min_training_periods:
                skipped.append(
                    {
                        "course": course,
                        "reason": (
                            f"Insufficient training history "
                            f"({course_split} < {self._min_training_periods} weeks)."
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
                        "course": course,
                        "reason": "No successful walk-forward forecasts were produced.",
                    }
                )
                continue

            course_results.append(
                {
                    "course": course,
                    "mape": metrics.mape,
                    "mae": metrics.mae,
                    "rmse": metrics.rmse,
                    "test_periods": metrics.test_periods,
                }
            )

        course_results.sort(
            key=lambda x: (x["mape"] is None, x["mape"] if x["mape"] is not None else float("inf"))
        )

        result = {
            "data_source": "datasets/applicant_volume.csv",
            "dataset_type": "synthetic",
            "evaluation_method": "Chronological time-series backtesting",
            "frequency": "weekly",
            "arima_order": list(ARIMA_ORDER),
            "train_ratio": self._train_ratio,
            "training_period": _format_period_range(overall_series, 0, split - 1),
            "testing_period": _format_period_range(overall_series, split, n - 1),
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
            "course_results": course_results,
            "skipped_courses": skipped,
            "note": EVALUATION_NOTE,
        }

        self._cached_result = result
        return result


_evaluation_service: ForecastingEvaluationService | None = None


def get_forecasting_evaluation_service() -> ForecastingEvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = ForecastingEvaluationService()
    return _evaluation_service


def reset_forecasting_evaluation_service() -> None:
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
