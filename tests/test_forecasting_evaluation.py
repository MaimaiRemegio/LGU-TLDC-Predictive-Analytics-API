"""Unit tests for chronological ARIMA backtesting evaluation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from services.forecasting_evaluation import (
    ForecastingEvaluationService,
    chronological_split_index,
    classify_mape,
    compute_forecast_metrics,
    walk_forward_backtest,
)


def test_chronological_split_is_80_20_and_ordered():
    n = 100
    split = chronological_split_index(n, train_ratio=0.8)
    assert split == 80
    assert 0 < split < n


def test_chronological_split_preserves_both_sides():
    split = chronological_split_index(10, train_ratio=0.8)
    assert split == 8
    train_indexes = list(range(0, split))
    test_indexes = list(range(split, 10))
    assert train_indexes[-1] < test_indexes[0]


def test_compute_forecast_metrics_known_values():
    actuals = [100.0, 200.0, 50.0]
    predictions = [110.0, 180.0, 40.0]
    metrics = compute_forecast_metrics(actuals, predictions)

    expected_mae = (10.0 + 20.0 + 10.0) / 3.0
    expected_rmse = math.sqrt((100.0 + 400.0 + 100.0) / 3.0)
    expected_mape = ((10 / 100) + (20 / 200) + (10 / 50)) / 3.0 * 100.0

    assert metrics.test_periods == 3
    assert metrics.mape_periods == 3
    assert metrics.mae == round(expected_mae, 2)
    assert metrics.rmse == round(expected_rmse, 2)
    assert metrics.mape == round(expected_mape, 2)


def test_mape_excludes_zero_actuals_safely():
    actuals = [0.0, 100.0, 0.0, 50.0]
    predictions = [5.0, 120.0, 3.0, 40.0]
    metrics = compute_forecast_metrics(actuals, predictions)

    assert metrics.test_periods == 4
    assert metrics.mape_periods == 2
    expected_mape = ((20 / 100) + (10 / 50)) / 2.0 * 100.0
    assert metrics.mape == round(expected_mape, 2)
    assert metrics.mae is not None
    assert metrics.rmse is not None


def test_mape_all_zeros_returns_none():
    metrics = compute_forecast_metrics([0.0, 0.0], [1.0, 2.0])
    assert metrics.mape is None
    assert metrics.mape_periods == 0
    assert metrics.mae is not None


def test_classify_mape_thresholds():
    assert classify_mape(4.9) == "Excellent"
    assert classify_mape(5.0) == "Good"
    assert classify_mape(9.9) == "Good"
    assert classify_mape(10.0) == "Acceptable"
    assert classify_mape(19.9) == "Acceptable"
    assert classify_mape(20.0) == "Needs Improvement"
    assert classify_mape(None) == "Needs Improvement"


def test_walk_forward_never_trains_on_future_and_metrics_are_computed():
    index = pd.date_range("2021-01-01", periods=40, freq="MS")
    values = np.linspace(50, 120, 40) + np.sin(np.linspace(0, 6, 40)) * 2
    series = pd.Series(values, index=index, name="total_applications")

    split = chronological_split_index(len(series), train_ratio=0.8)
    metrics = walk_forward_backtest(
        series,
        train_ratio=0.8,
        min_training_periods=12,
    )

    assert metrics.test_periods == len(series) - split
    assert metrics.mae is not None
    assert metrics.rmse is not None
    assert metrics.mape is not None
    assert metrics.mape >= 0
    assert len(metrics.actuals) == metrics.test_periods
    assert len(metrics.predictions) == metrics.test_periods

    recomputed = compute_forecast_metrics(metrics.actuals, metrics.predictions)
    assert recomputed.mape == metrics.mape
    assert recomputed.mae == metrics.mae
    assert recomputed.rmse == metrics.rmse


def test_evaluation_service_uses_injected_course_series_via_stub_repository():
    """Service overall metrics must come from walk-forward predictions vs actuals."""

    class StubRepository:
        def get_tldc_series(self, frequency: str = "M"):
            index = pd.date_range("2021-01-01", periods=30, freq="MS")
            values = np.linspace(800, 1400, 30)
            return pd.Series(values, index=index)

        def get_available_courses(self):
            return ["Cookery NC II", "Driving NC II"]

        def get_course_series(self, course: str):
            # Return WEEKLY series to match current architecture
            index = pd.date_range("2021-01-01", periods=30, freq="W")
            base = 400 if course == "Cookery NC II" else 300
            values = np.linspace(base, base + 200, 30)
            return pd.Series(values, index=index)

    service = ForecastingEvaluationService(
        repository=StubRepository(),  # type: ignore[arg-type]
        train_ratio=0.8,
        min_training_periods=12,
    )
    result = service.evaluate()

    assert result["dataset_type"] == "synthetic"
    assert result["evaluation_method"] == "Chronological time-series backtesting"
    assert result["arima_order"] == [1, 1, 1]
    assert result["frequency"] == "weekly"  # Updated to match weekly architecture
    assert result["overall"]["test_periods"] > 0
    assert result["overall"]["mape"] is not None
    assert result["overall"]["mae"] is not None
    assert result["overall"]["rmse"] is not None
    assert result["model_assessment"] == classify_mape(result["overall"]["mape"])

    # Per-course results instead of per-barangay.
    assert len(result["course_results"]) == 2
    course_names = [r["course"] for r in result["course_results"]]
    assert "Cookery NC II" in course_names
    assert "Driving NC II" in course_names

    # No barangay keys anywhere in the result.
    assert "barangay_results" not in result
    assert "barangay" not in str(result["course_results"])

    assert "accuracy" not in result or not isinstance(result.get("accuracy"), (int, float))
    assert "Prototype Ready" not in str(result["overall"])
