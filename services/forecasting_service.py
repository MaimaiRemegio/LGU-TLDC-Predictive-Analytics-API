"""
Applicant volume forecasting service (barangay-level ARIMA).

Independent from the Barangay Recommendation module.

Data source:
  datasets/applicant_volume_history.csv
  (application_date, barangay, course_applied)

Pipeline:
  1. Load event-level registrations from the forecasting repository.
  2. Aggregate by day, week, and month.
  3. Fit one ARIMA model per barangay on the matching frequency.
  4. Serve next-week / next-month / next-quarter forecasts.

historical_training.csv is never used here.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from services.forecasting_repository import (
    ForecastingRepository,
    get_forecasting_repository,
)
from services.forecasting_statistics import (
    ForecastingStatistics,
    get_forecasting_statistics,
)

ARIMA_ORDER = (1, 1, 1)

# Horizon in periods for each forecast window / series frequency.
FORECAST_CONFIG = {
    "next_week": {"frequency": "W", "steps": 1, "chart_history": 26},
    "next_month": {"frequency": "M", "steps": 1, "chart_history": 18},
    "next_quarter": {"frequency": "M", "steps": 3, "chart_history": 18},
}

TREND_STABLE_THRESHOLD_PERCENT = 5.0
RECENT_PERIODS_FOR_TREND = 3


class ForecastingService:
    """Train and serve per-barangay ARIMA applicant-volume forecasts."""

    def __init__(
        self,
        repository: ForecastingRepository | None = None,
        statistics: ForecastingStatistics | None = None,
    ) -> None:
        self._repository = repository or get_forecasting_repository()
        self._statistics = statistics or get_forecasting_statistics()

        # Separate ARIMA models/series for weekly and monthly frequencies.
        self._weekly_models: dict[str, object] = {}
        self._monthly_models: dict[str, object] = {}
        self._weekly_series: dict[str, pd.Series] = {}
        self._monthly_series: dict[str, pd.Series] = {}
        self._weekly_forecast: dict[str, list[float]] = {}
        self._monthly_forecast: dict[str, list[float]] = {}
        self._barangay_registration_counts = (
            self._repository.get_barangay_registration_counts()
        )
        self._cached_distributions: dict | None = None
        self._cached_barangay_forecasts: dict[str, list[dict]] = {}

        self._fit_barangay_models()

    def _fit_series_models(
        self,
        frequency: str,
        steps: int,
    ) -> tuple[dict[str, pd.Series], dict[str, object], dict[str, list[float]]]:
        """Fit one ARIMA model per barangay for a given aggregation frequency."""
        series_map: dict[str, pd.Series] = {}
        model_map: dict[str, object] = {}
        forecast_map: dict[str, list[float]] = {}

        for barangay in self._repository.get_available_barangays():
            series = self._repository.get_barangay_series(barangay, frequency=frequency)
            series_map[barangay] = series

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = ARIMA(series, order=ARIMA_ORDER).fit()

            model_map[barangay] = fitted
            predictions = np.asarray(fitted.forecast(steps=steps), dtype=float)
            forecast_map[barangay] = [
                max(0.0, round(float(value), 1)) for value in predictions
            ]

        return series_map, model_map, forecast_map

    def _fit_barangay_models(self) -> None:
        """
        Aggregate registrations and fit ARIMA models.

        - Weekly series -> next-week forecasts
        - Monthly series -> next-month and next-quarter forecasts
        """
        self._weekly_series, self._weekly_models, self._weekly_forecast = (
            self._fit_series_models(frequency="W", steps=1)
        )
        self._monthly_series, self._monthly_models, self._monthly_forecast = (
            self._fit_series_models(frequency="M", steps=3)
        )

    def _sum_weekly_forecast(self) -> float:
        return round(sum(values[0] for values in self._weekly_forecast.values()), 1)

    def _sum_monthly_forecast(self, months: int) -> float:
        total = 0.0
        for predictions in self._monthly_forecast.values():
            total += sum(predictions[:months])
        return round(total, 1)

    def _compute_trend(self, series: pd.Series, forecasted_value: float) -> str:
        """Compare the forecast with the recent historical average."""
        recent = series.iloc[-RECENT_PERIODS_FOR_TREND:]
        recent_average = float(recent.mean()) if len(recent) else 0.0

        if recent_average <= 0:
            return "Increasing" if forecasted_value > 0 else "Stable"

        change_percent = ((forecasted_value - recent_average) / recent_average) * 100
        if change_percent > TREND_STABLE_THRESHOLD_PERCENT:
            return "Increasing"
        if change_percent < -TREND_STABLE_THRESHOLD_PERCENT:
            return "Decreasing"
        return "Stable"

    def _compute_growth_percentage(
        self,
        series: pd.Series,
        forecasted_value: float,
    ) -> float:
        """Return percent change of the forecast versus the recent historical average."""
        recent = series.iloc[-RECENT_PERIODS_FOR_TREND:]
        recent_average = float(recent.mean()) if len(recent) else 0.0
        if recent_average <= 0:
            return 0.0
        return round(((forecasted_value - recent_average) / recent_average) * 100, 1)

    def _get_distributions(self) -> dict:
        """Return cached organization-wide descriptive distributions."""
        if self._cached_distributions is None:
            self._cached_distributions = (
                self._statistics.get_organization_distributions()
            )
        return self._cached_distributions

    def get_summary(self, barangay_forecasts: list[dict] | None = None) -> dict:
        """Return overall TLDC forecast totals and dashboard KPI helpers."""
        next_week = self._sum_weekly_forecast()
        next_month = self._sum_monthly_forecast(1)
        next_quarter = self._sum_monthly_forecast(3)

        monthly_history = self._repository.get_tldc_series("M")
        weekly_history = self._repository.get_tldc_series("W")
        forecasts = barangay_forecasts or self.get_barangay_forecasts(
            period="next_month"
        )
        distributions = self._get_distributions()

        previous_month = float(monthly_history.iloc[-1]) if len(monthly_history) else 0.0
        previous_quarter = (
            float(monthly_history.iloc[-3:].sum())
            if len(monthly_history) >= 3
            else float(monthly_history.sum())
        )
        previous_week = float(weekly_history.iloc[-1]) if len(weekly_history) else 0.0

        highest_forecasted = forecasts[0] if forecasts else None
        highest_growth = (
            max(forecasts, key=lambda item: item["growth_percentage"])
            if forecasts
            else None
        )

        return {
            "expected_applicants_next_week": next_week,
            "expected_applicants_next_month": next_month,
            "expected_applicants_next_quarter": next_quarter,
            "previous_week_total": round(previous_week, 1),
            "previous_month_total": round(previous_month, 1),
            "previous_quarter_total": round(previous_quarter, 1),
            "total_historical_applicants": (
                self._repository.get_registration_event_count()
            ),
            "highest_forecasted_barangay": (
                highest_forecasted["barangay"] if highest_forecasted else None
            ),
            "highest_forecasted_count": (
                highest_forecasted["forecast_next_month"] if highest_forecasted else 0.0
            ),
            "highest_growth_barangay": (
                highest_growth["barangay"] if highest_growth else None
            ),
            "highest_growth_percentage": (
                highest_growth["growth_percentage"] if highest_growth else 0.0
            ),
            "most_popular_course": distributions.get("most_popular_course"),
            "barangays_modeled": len(self._monthly_models),
            "model": "ARIMA",
            "arima_order": list(ARIMA_ORDER),
            "data_source": "datasets/applicant_volume_history.csv",
            "aggregation": {
                "next_week": "weekly registration counts",
                "next_month": "monthly registration counts",
                "next_quarter": "sum of next 3 monthly forecasts",
            },
            "note": (
                "Forecasts are produced from chronological applicant registrations. "
                "Events are aggregated by week or month before ARIMA is fitted. "
                "Demographic profile panels use a separate descriptive source and "
                "are never used by ARIMA."
            ),
        }

    def get_barangay_forecasts(self, period: str = "next_month") -> list[dict]:
        """Return every barangay forecast ranked by predicted applicants."""
        if period not in FORECAST_CONFIG:
            raise ValueError(
                "Unsupported period. Use next_week, next_month, or next_quarter."
            )

        cached = self._cached_barangay_forecasts.get(period)
        if cached is not None:
            return cached

        results: list[dict] = []

        for barangay in self._repository.get_available_barangays():
            next_week = self._weekly_forecast[barangay][0]
            next_month = self._monthly_forecast[barangay][0]
            next_quarter = round(sum(self._monthly_forecast[barangay][:3]), 1)
            historical_applicants = self._barangay_registration_counts.get(barangay, 0)

            if period == "next_week":
                forecasted = next_week
                trend_series = self._weekly_series[barangay]
                current_count = (
                    int(round(float(trend_series.iloc[-1])))
                    if len(trend_series)
                    else 0
                )
                comparison_value = next_week
            else:
                forecasted = next_month if period == "next_month" else next_quarter
                trend_series = self._monthly_series[barangay]
                current_count = (
                    int(round(float(trend_series.iloc[-1])))
                    if len(trend_series)
                    else 0
                )
                comparison_value = next_month

            growth_percentage = self._compute_growth_percentage(
                trend_series,
                comparison_value,
            )

            results.append(
                {
                    "barangay": barangay,
                    "historical_applicants": historical_applicants,
                    "current_applicant_count": current_count,
                    "forecasted_applicant_count": forecasted,
                    "forecast_next_week": next_week,
                    "forecast_next_month": next_month,
                    "forecast_next_quarter": next_quarter,
                    "trend": self._compute_trend(trend_series, comparison_value),
                    "growth_percentage": growth_percentage,
                    "period": period,
                }
            )

        results.sort(key=lambda item: item["forecasted_applicant_count"], reverse=True)
        self._cached_barangay_forecasts[period] = results
        return results

    def get_insights(
        self,
        period: str = "next_month",
        barangay_forecasts: list[dict] | None = None,
    ) -> list[str]:
        """Generate short administrator-facing planning insights."""
        barangays = barangay_forecasts or self.get_barangay_forecasts(period=period)
        distributions = self._get_distributions()

        if not barangays:
            return ["No forecasting data is available yet."]

        highest = barangays[0]
        lowest = barangays[-1]
        fastest = max(barangays, key=lambda item: item["growth_percentage"])

        insights = [
            (
                f"{highest['barangay']} has the highest projected applicant volume "
                f"({highest['forecasted_applicant_count']:,.0f}) for the selected period."
            ),
            (
                f"{fastest['barangay']} is the fastest growing barangay "
                f"({fastest['growth_percentage']:+.1f}% versus recent history)."
            ),
            (
                f"{lowest['barangay']} has the lowest projected applicant volume "
                f"({lowest['forecasted_applicant_count']:,.0f})."
            ),
        ]

        if distributions.get("most_popular_course"):
            insights.append(
                f"The most popular course historically is {distributions['most_popular_course']}."
            )
        if distributions.get("most_common_employment_status"):
            insights.append(
                "The most common employment status among historical applicants is "
                f"{distributions['most_common_employment_status']}."
            )
        if distributions.get("most_common_educational_attainment"):
            insights.append(
                "The most common educational attainment among historical applicants is "
                f"{distributions['most_common_educational_attainment']}."
            )

        return insights

    def get_dashboard(self, period: str = "next_month") -> dict:
        """
        Return a single payload for the forecasting analytics dashboard.

        Used by the frontend for automatic first-load rendering.
        """
        if period not in FORECAST_CONFIG:
            raise ValueError(
                "Unsupported period. Use next_week, next_month, or next_quarter."
            )

        barangays = self.get_barangay_forecasts(period=period)
        monthly_forecasts = (
            barangays
            if period == "next_month"
            else self.get_barangay_forecasts(period="next_month")
        )
        selected_barangay = barangays[0]["barangay"] if barangays else None
        summary = self.get_summary(barangay_forecasts=monthly_forecasts)

        return {
            "period": period,
            "summary": summary,
            "barangays": barangays,
            "charts": self.get_charts(
                barangay_forecasts=monthly_forecasts,
                summary=summary,
            ),
            "insights": self.get_insights(
                period=period,
                barangay_forecasts=barangays,
            ),
            "selected_barangay": selected_barangay,
            "selected_profile": (
                self.get_barangay_profile(selected_barangay)
                if selected_barangay
                else None
            ),
        }

    def get_barangay_detail(self, barangay: str) -> dict:
        """Return forecast detail and registration-based profile for one barangay."""
        self._repository.validate_barangay(barangay)

        next_week = self._weekly_forecast[barangay][0]
        monthly_predictions = self._monthly_forecast[barangay]
        next_month = monthly_predictions[0]
        next_quarter = round(sum(monthly_predictions[:3]), 1)
        monthly_series = self._monthly_series[barangay]

        historical_volume = [
            {
                "period": index.strftime("%b %Y"),
                "applicants": round(float(value), 1),
            }
            for index, value in monthly_series.iloc[-18:].items()
        ]

        last_date = monthly_series.index[-1]
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1),
            periods=3,
            freq="MS",
        )
        forecast_volume = [
            {
                "period": future_dates[index].strftime("%b %Y"),
                "applicants": monthly_predictions[index],
            }
            for index in range(3)
        ]

        return {
            "barangay": barangay,
            "current_applicant_count": self._repository.get_current_applicant_count(
                barangay,
                frequency="M",
            ),
            "forecast_next_week": next_week,
            "forecast_next_month": next_month,
            "forecast_next_quarter": next_quarter,
            "trend": self._compute_trend(monthly_series, next_month),
            "monthly_forecast": monthly_predictions,
            "historical_volume": historical_volume,
            "forecast_volume": forecast_volume,
            "profile": self._statistics.get_barangay_profile(barangay),
        }

    def get_charts(
        self,
        barangay_forecasts: list[dict] | None = None,
        summary: dict | None = None,
    ) -> dict:
        """Return chart-ready JSON series for the forecasting dashboard."""
        forecasts = barangay_forecasts or self.get_barangay_forecasts(
            period="next_month"
        )
        monthly_history = self._repository.get_tldc_series("M")
        weekly_history = self._repository.get_tldc_series("W")
        summary_payload = summary or self.get_summary(barangay_forecasts=forecasts)

        historical_trend = [
            {
                "period": index.strftime("%b %Y"),
                "applicants": round(float(value), 1),
            }
            for index, value in monthly_history.iloc[-18:].items()
        ]

        weekly_trend = [
            {
                "period": index.strftime("%Y-%m-%d"),
                "applicants": round(float(value), 1),
            }
            for index, value in weekly_history.iloc[-26:].items()
        ]

        last_date = monthly_history.index[-1]
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1),
            periods=3,
            freq="MS",
        )
        org_monthly = [
            round(
                sum(predictions[month_index] for predictions in self._monthly_forecast.values()),
                1,
            )
            for month_index in range(3)
        ]
        forecast_curve = [
            {
                "period": future_dates[index].strftime("%b %Y"),
                "applicants": org_monthly[index],
            }
            for index in range(3)
        ]

        top_barangays = [
            {
                "barangay": item["barangay"],
                "forecasted_applicant_count": item["forecasted_applicant_count"],
                "trend": item["trend"],
            }
            for item in forecasts[:10]
        ]

        distributions = self._get_distributions()

        return {
            "applicant_trend_over_time": historical_trend,
            "weekly_applicant_trend": weekly_trend,
            "forecast_curve": forecast_curve,
            "top_barangays": top_barangays,
            "summary_points": [
                {
                    "label": "Next Week",
                    "applicants": summary_payload["expected_applicants_next_week"],
                },
                {
                    "label": "Next Month",
                    "applicants": summary_payload["expected_applicants_next_month"],
                },
                {
                    "label": "Next Quarter",
                    "applicants": summary_payload["expected_applicants_next_quarter"],
                },
            ],
            "employment_distribution": distributions.get("employment_distribution", []),
            "education_distribution": distributions.get("education_distribution", []),
            "course_distribution": distributions.get("course_distribution", []),
            "sex_distribution": distributions.get("sex_distribution", []),
            "age_distribution": distributions.get("age_distribution", []),
            "learner_classification_distribution": distributions.get(
                "learner_classification_distribution",
                [],
            ),
            "barangay_distribution": distributions.get("barangay_distribution", []),
        }

    def get_barangay_profile(self, barangay: str) -> dict:
        """Return historical registration analytics for one barangay."""
        return self._statistics.get_barangay_profile(barangay)


_service: ForecastingService | None = None


def get_forecasting_service() -> ForecastingService:
    """Return the singleton forecasting service, fitting models on first use."""
    global _service

    if _service is None:
        _service = ForecastingService()

    return _service


def reset_forecasting_service() -> None:
    """Clear the singleton so the next call reloads data and refits models."""
    global _service
    _service = None


__all__ = [
    "ForecastingService",
    "get_forecasting_service",
    "reset_forecasting_service",
]
