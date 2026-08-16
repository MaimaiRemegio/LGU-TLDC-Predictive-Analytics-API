"""
Applicant volume forecasting service — LEGACY / kept as artifact.

This module is no longer called at runtime. ForecastingService is now the
single source of truth for all applicant-volume forecasts, including
POST /predict/applicant-volume.

This file and applicant_forecast_model.pkl are retained temporarily so
existing training scripts and documentation remain intact.
Do NOT remove until confirmed no external dependency exists.

Original function: loaded a pre-trained ARIMA bundle (one model per
available course) and served TLDC-wide or per-course forecasts.
Bundle schema: { "models": dict[str, ARIMAResultsWrapper], ... }
Keys are course names.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "trained_models" / "applicant_forecast_model.pkl"
DATASET_PATH = PROJECT_ROOT / "datasets" / "applicant_volume.csv"

FORECAST_PERIODS = {
    "next_month": 1,
    "next_quarter": 3,
    "next_6_months": 6,
    "next_12_months": 12,
}

PLANNING_PERIOD_LABELS = {
    "next_month": "Next Month",
    "next_quarter": "Next Quarter (3 Months)",
    "next_6_months": "Next 6 Months",
    "next_12_months": "Next 12 Months",
}

HISTORICAL_CHART_MONTHS = 18


class UnknownForecastPeriodError(ValueError):
    """Raised when the requested planning period is not supported."""


class UnknownBarangayError(ValueError):
    """Raised when the requested barangay is not in the trained forecast models."""


class UnknownCourseError(ValueError):
    """Raised when the requested course is not in the trained forecast models."""


class ApplicantForecastService:
    """Serve TLDC-wide applicant volume forecasts from the saved ARIMA bundle."""

    def __init__(self) -> None:
        bundle = joblib.load(MODEL_PATH)
        self._models: dict[tuple[str, str], object] = bundle["models"]
        self._metrics: dict[str, float] = bundle.get("metrics", {})
        self._historical_totals = self._load_historical_totals()
        self._confidence_level = self._compute_confidence_level()

        # Run all 176 ARIMA models once at startup, then serve cached results.
        max_steps = max(FORECAST_PERIODS.values())
        self._full_monthly_forecast = self._aggregate_monthly_forecast(max_steps)
        self._response_cache = self._build_response_cache()

    def _load_historical_totals(self) -> pd.Series:
        """
        Aggregate applicant_volume.csv into total TLDC monthly volume.

        Each row is summed by date to produce organization-wide applicant counts.
        """
        dataset = pd.read_csv(DATASET_PATH, parse_dates=["date"])
        totals = dataset.groupby("date")["applicant_count"].sum().sort_index()
        return totals.asfreq("MS")

    def _validate_forecast_period(self, forecast_period: str) -> int:
        if forecast_period not in FORECAST_PERIODS:
            accepted = ", ".join(FORECAST_PERIODS)
            raise UnknownForecastPeriodError(
                f"Unknown forecast period '{forecast_period}'. Accepted values: {accepted}"
            )
        return FORECAST_PERIODS[forecast_period]

    def _aggregate_monthly_forecast(self, steps: int) -> list[float]:
        """
        Sum ARIMA forecasts across every barangay and course model.

        Each model contributes one monthly prediction; totals represent
        expected TLDC applicant volume for the organization.
        """
        monthly_totals = np.zeros(steps, dtype=float)

        for model in self._models.values():
            predictions = np.asarray(model.forecast(steps=steps), dtype=float)
            monthly_totals[: len(predictions)] += predictions

        return [round(float(value), 1) for value in monthly_totals]

    def _compute_confidence_level(self) -> str:
        """
        Derive confidence from average model error relative to typical volume.

        Uses saved MAE from training compared to mean historical TLDC volume.
        """
        mae = self._metrics.get("mae")
        if mae is None or self._historical_totals.empty:
            return "Medium"

        mean_volume = float(self._historical_totals.mean())
        if mean_volume <= 0:
            return "Medium"

        error_ratio = mae / mean_volume
        if error_ratio < 0.08:
            return "High"
        if error_ratio < 0.15:
            return "Medium"
        return "Low"

    def _build_growth_summary(
        self,
        monthly_forecast: list[float],
        steps: int,
    ) -> dict:
        """
        Compare forecast period total with the immediately previous period
        of the same length from historical TLDC volume.
        """
        forecast_total = round(sum(monthly_forecast), 1)
        historical = self._historical_totals

        if len(historical) >= steps:
            previous_total = round(float(historical.iloc[-steps:].sum()), 1)
        else:
            previous_total = round(float(historical.sum()), 1)

        if previous_total == 0:
            growth_percentage = 0.0
        else:
            growth_percentage = round(
                ((forecast_total - previous_total) / previous_total) * 100,
                1,
            )

        if growth_percentage > 1:
            growth_direction = "growth"
        elif growth_percentage < -1:
            growth_direction = "decline"
        else:
            growth_direction = "stable"

        return {
            "total_predicted_applicants": forecast_total,
            "previous_period_total": previous_total,
            "growth_percentage": growth_percentage,
            "growth_direction": growth_direction,
        }

    def _build_chart_data(self, monthly_forecast: list[float]) -> dict:
        """Prepare historical and forecast series for the line chart."""
        historical = self._historical_totals.iloc[-HISTORICAL_CHART_MONTHS:]
        historical_volume = [
            {
                "period": index.strftime("%b %Y"),
                "applicants": round(float(value), 1),
            }
            for index, value in historical.items()
        ]

        last_date = self._historical_totals.index[-1]
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1),
            periods=len(monthly_forecast),
            freq="MS",
        )

        forecast_volume = [
            {
                "period": future_dates[index].strftime("%b %Y"),
                "applicants": monthly_forecast[index],
            }
            for index in range(len(monthly_forecast))
        ]

        return {
            "historical_volume": historical_volume,
            "forecast_volume": forecast_volume,
        }

    def _build_planning_insights(
        self,
        forecast_period: str,
        monthly_forecast: list[float],
        growth_summary: dict,
    ) -> list[str]:
        """Generate administrator-focused planning insights from forecast output."""
        period_label = PLANNING_PERIOD_LABELS[forecast_period]
        total = growth_summary["total_predicted_applicants"]
        growth = growth_summary["growth_percentage"]
        direction = growth_summary["growth_direction"]
        peak_value = max(monthly_forecast)
        peak_index = monthly_forecast.index(peak_value) + 1

        insights = [
            f"TLDC is projected to receive {total:,.0f} applicants during the {period_label.lower()} planning window.",
        ]

        if direction == "growth":
            insights.append(
                f"Applicant volume is expected to increase by {abs(growth)}% compared with the previous period of the same length."
            )
        elif direction == "decline":
            insights.append(
                f"Applicant volume is expected to decrease by {abs(growth)}% compared with the previous period of the same length."
            )
        else:
            insights.append(
                "Applicant volume is expected to remain stable compared with the previous period of the same length."
            )

        if len(monthly_forecast) > 1:
            insights.append(
                f"Peak demand is projected in month {peak_index} with approximately {peak_value:,.0f} applicants."
            )

        insights.append(
            "Use this forecast to plan instructor allocation, training schedules, and barangay coordination across all TLDC programs."
        )

        return insights

    def _build_response_cache(self) -> dict[str, dict]:
        """
        Pre-build forecast responses for every planning period.

        Avoids re-running 176 ARIMA model forecasts on each API request.
        """
        cache: dict[str, dict] = {}

        for forecast_period, steps in FORECAST_PERIODS.items():
            monthly_forecast = self._full_monthly_forecast[:steps]
            growth_summary = self._build_growth_summary(monthly_forecast, steps)
            chart_data = self._build_chart_data(monthly_forecast)

            cache[forecast_period] = {
                "forecast_period": forecast_period,
                "planning_period_label": PLANNING_PERIOD_LABELS[forecast_period],
                "monthly_forecast": monthly_forecast,
                "confidence_level": self._confidence_level,
                "ai_planning_insights": self._build_planning_insights(
                    forecast_period,
                    monthly_forecast,
                    growth_summary,
                ),
                **growth_summary,
                **chart_data,
            }

        return cache

    def forecast_tldc_total(self, forecast_period: str) -> dict:
        """Return a cached TLDC-wide forecast for the selected planning period."""
        self._validate_forecast_period(forecast_period)
        return self._response_cache[forecast_period]

    def forecast(self, barangay: str, course: str, horizon: str) -> dict:
        """Return a single barangay and course forecast (legacy helper)."""
        steps = self._validate_forecast_period(horizon)
        barangays = sorted({key[0] for key in self._models})
        courses = sorted({key[1] for key in self._models})

        if barangay not in barangays:
            raise UnknownBarangayError(
                f"Unknown barangay '{barangay}'. Accepted values: {', '.join(barangays)}"
            )
        if course not in courses:
            raise UnknownCourseError(
                f"Unknown course '{course}'. Accepted values: {', '.join(courses)}"
            )

        model_key = (barangay, course)
        if model_key not in self._models:
            raise UnknownCourseError(
                f"No forecast model is available for barangay '{barangay}' and course '{course}'."
            )

        model = self._models[model_key]
        predictions = np.asarray(model.forecast(steps=steps))
        rounded_forecast = [round(float(value), 1) for value in predictions]

        return {
            "barangay": barangay,
            "course": course,
            "forecast": rounded_forecast,
        }


_service: ApplicantForecastService | None = None


def get_applicant_forecast_service() -> ApplicantForecastService:
    """Return the singleton forecast service, loading the bundle on first use."""
    global _service

    if _service is None:
        _service = ApplicantForecastService()

    return _service


def forecast_applicant_volume(forecast_period: str) -> dict:
    """Convenience wrapper for TLDC-wide applicant volume forecasting."""
    return get_applicant_forecast_service().forecast_tldc_total(forecast_period)
