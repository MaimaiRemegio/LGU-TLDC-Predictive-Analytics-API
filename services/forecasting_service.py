"""
Applicant volume forecasting service — course-level ARIMA on weekly data.

Independent from the Barangay Recommendation / Random Forest module.

Data source
-----------
datasets/applicant_volume.csv
  Columns: date, course, applicant_count  (DAILY observations)

The repository aggregates daily → weekly before returning series to this
service.  ARIMA(1,1,1) is then fitted on weekly totals per course.

Forecast horizons
-----------------
  next_week   = ARIMA step 1  (1 week ahead)
  next_month  = sum of ARIMA steps 1-4  (≈ 4 weeks)
  next_quarter= sum of ARIMA steps 1-13 (≈ 13 weeks / 1 quarter)

These are genuine weekly ARIMA forecasts, not estimates derived by
dividing a monthly forecast by 4.33.

Model choice rationale
----------------------
  ARIMA(1,1,1) on weekly aggregated data is the simplest defensible model
  for an undergraduate capstone.  It captures trend (d=1), short-term
  autocorrelation (p=1), and moving-average smoothing (q=1).
  SARIMA with seasonal period 7 (daily) or 52 (weekly) would capture the
  annual seasonal pattern more precisely but adds parameter complexity that
  is not required for a capstone demonstration.  The weekly aggregation
  already smooths most of the day-of-week variation.

Growth / trend comparison rules
--------------------------------
All growth_percentage and trend comparisons use MATCHING time scales:

  next_week   : forecast_week_1       vs  recent_weekly_avg  (last 4 weeks)
  next_month  : sum(steps 1-4)/ 4     vs  recent_weekly_avg
  next_quarter: sum(steps 1-13)/13    vs  recent_weekly_avg

Barangay is NOT a forecasting dimension.
historical_training.csv is never used by ARIMA.

This service is the SINGLE SOURCE OF TRUTH for applicant-volume forecasting.
It backs /forecast/* endpoints AND POST /predict/applicant-volume.
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

FORECAST_PERIODS = ("next_week", "next_month", "next_quarter")

# Number of weekly ARIMA steps per horizon.
STEPS_NEXT_WEEK = 1
STEPS_NEXT_MONTH = 4        # ≈ 4 weeks in a month
STEPS_NEXT_QUARTER = 13     # ≈ 13 weeks in a quarter
STEPS_NEXT_6_MONTHS = 26    # for /predict/applicant-volume
STEPS_NEXT_12_MONTHS = 52   # for /predict/applicant-volume

# Total steps to pre-compute at startup (covers the longest horizon).
STEPS_PRECOMPUTE = STEPS_NEXT_12_MONTHS

# Number of recent weeks used for the trend/growth baseline.
RECENT_PERIODS_FOR_TREND = 4   # last 4 weeks ≈ last month
TREND_STABLE_THRESHOLD_PERCENT = 5.0


# ---------------------------------------------------------------------------
# Exception classes (also exported for route error handling)
# ---------------------------------------------------------------------------

class UnknownForecastPeriodError(ValueError):
    """Raised when the requested planning period is not supported."""


class UnknownCourseError(ValueError):
    """Raised when the requested course is not in the trained forecast models."""


class ForecastingService:
    """Fit and serve per-course weekly ARIMA applicant-volume forecasts."""

    def __init__(
        self,
        repository: ForecastingRepository | None = None,
        statistics: ForecastingStatistics | None = None,
    ) -> None:
        self._repository = repository or get_forecasting_repository()
        self._statistics = statistics or get_forecasting_statistics()

        # Weekly series and pre-computed forecasts per course.
        self._weekly_series: dict[str, pd.Series] = {}
        self._weekly_models: dict[str, object] = {}
        # _weekly_forecast[course] = list of STEPS_PRECOMPUTE weekly values
        self._weekly_forecast: dict[str, list[float]] = {}

        self._cached_distributions: dict | None = None
        self._cached_course_forecasts: dict[str, list[dict]] = {}

        self._fit_course_models()

    # ------------------------------------------------------------------
    # Model fitting
    # ------------------------------------------------------------------

    def _fit_course_models(self) -> None:
        """
        Fit one ARIMA(1,1,1) model per available course on the weekly series.

        Pre-compute STEPS_PRECOMPUTE (52) weekly forecasts so all horizon
        requests (next_week … next_12_months) can be served from cache.
        """
        for course in self._repository.get_available_courses():
            series = self._repository.get_course_series(course)
            self._weekly_series[course] = series

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = ARIMA(series, order=ARIMA_ORDER).fit()

            self._weekly_models[course] = fitted
            preds = np.asarray(
                fitted.forecast(steps=STEPS_PRECOMPUTE), dtype=float
            )
            self._weekly_forecast[course] = [
                max(0.0, round(float(v), 2)) for v in preds
            ]

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def _sum_weekly_steps(
        self,
        steps: int,
        course: str | None = None,
    ) -> float:
        """Sum the first `steps` weekly forecasts, across courses or for one."""
        if course is not None:
            return round(sum(self._weekly_forecast[course][:steps]), 1)
        return round(
            sum(
                sum(preds[:steps])
                for preds in self._weekly_forecast.values()
            ),
            1,
        )

    def _get_next_week(self, course: str | None = None) -> float:
        return self._sum_weekly_steps(STEPS_NEXT_WEEK, course=course)

    def _get_next_month(self, course: str | None = None) -> float:
        return self._sum_weekly_steps(STEPS_NEXT_MONTH, course=course)

    def _get_next_quarter(self, course: str | None = None) -> float:
        return self._sum_weekly_steps(STEPS_NEXT_QUARTER, course=course)

    # ------------------------------------------------------------------
    # Growth and trend helpers
    # ------------------------------------------------------------------

    def _recent_weekly_avg(self, series: pd.Series) -> float:
        """Mean of the most recent RECENT_PERIODS_FOR_TREND weeks."""
        recent = series.iloc[-RECENT_PERIODS_FOR_TREND:]
        return float(recent.mean()) if len(recent) else 0.0

    def _comparable_forecast_value(
        self,
        period: str,
        weekly_preds: list[float],
    ) -> float:
        """
        Return the forecast expressed in WEEKLY-average units for comparison.

        next_week   → step 1 (1 week, already in weekly units)
        next_month  → sum(steps 1-4) / 4 (weekly average over ~1 month)
        next_quarter→ sum(steps 1-13) / 13 (weekly average over ~1 quarter)

        The baseline is also a weekly average (last 4 weeks), so both sides
        are in the same unit and the growth percentage is meaningful.
        """
        if period == "next_month":
            return sum(weekly_preds[:STEPS_NEXT_MONTH]) / STEPS_NEXT_MONTH
        if period == "next_quarter":
            return sum(weekly_preds[:STEPS_NEXT_QUARTER]) / STEPS_NEXT_QUARTER
        # next_week: step 1 directly
        return float(weekly_preds[0])

    def _growth_and_trend(
        self,
        series: pd.Series,
        period: str,
        weekly_preds: list[float],
    ) -> tuple[float, str]:
        """
        Return (growth_percentage, trend_label) with matching time scales.

        Baseline: mean of last RECENT_PERIODS_FOR_TREND weeks (weekly unit).
        Forecast: weekly-average equivalent for the period (weekly unit).
        """
        baseline = self._recent_weekly_avg(series)
        if baseline <= 0:
            fv = self._comparable_forecast_value(period, weekly_preds)
            return 0.0, ("Increasing" if fv > 0 else "Stable")

        fv = self._comparable_forecast_value(period, weekly_preds)
        pct = round(((fv - baseline) / baseline) * 100, 1)

        if pct > TREND_STABLE_THRESHOLD_PERCENT:
            label = "Increasing"
        elif pct < -TREND_STABLE_THRESHOLD_PERCENT:
            label = "Decreasing"
        else:
            label = "Stable"

        return pct, label

    def _get_distributions(self) -> dict:
        if self._cached_distributions is None:
            self._cached_distributions = (
                self._statistics.get_organization_distributions()
            )
        return self._cached_distributions

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_summary(
        self,
        course_forecasts: list[dict] | None = None,
        course: str | None = None,
    ) -> dict:
        """
        Return TLDC-wide (or per-course) forecast KPIs.

        course_forecasts must be the same list passed to get_insights() so
        that highest_growth_* fields are derived from identical data.
        """
        next_week = self._get_next_week(course=course)
        next_month = self._get_next_month(course=course)
        next_quarter = self._get_next_quarter(course=course)

        # Historical baselines from weekly series for previous_* fields.
        if course:
            weekly_hist = self._weekly_series[course]
        else:
            weekly_hist = self._repository.get_tldc_series("W")

        forecasts = course_forecasts or self.get_course_forecasts(
            period="next_month", course=course
        )
        distributions = self._get_distributions()

        previous_week = (
            float(weekly_hist.iloc[-1]) if len(weekly_hist) else 0.0
        )
        previous_month = round(
            float(weekly_hist.iloc[-STEPS_NEXT_MONTH:].sum())
            if len(weekly_hist) >= STEPS_NEXT_MONTH
            else float(weekly_hist.sum()),
            1,
        )
        previous_quarter = round(
            float(weekly_hist.iloc[-STEPS_NEXT_QUARTER:].sum())
            if len(weekly_hist) >= STEPS_NEXT_QUARTER
            else float(weekly_hist.sum()),
            1,
        )

        highest = forecasts[0] if forecasts else None
        highest_growth = (
            max(forecasts, key=lambda x: x["growth_percentage"])
            if forecasts
            else None
        )

        return {
            "expected_applicants_next_week": next_week,
            "expected_applicants_next_month": next_month,
            "expected_applicants_next_quarter": next_quarter,
            "previous_week_total": round(previous_week, 1),
            "previous_month_total": previous_month,
            "previous_quarter_total": previous_quarter,
            "total_historical_applicants": (
                self._repository.get_total_historical_applicants()
            ),
            "highest_forecasted_course": (
                highest["course"] if highest else None
            ),
            "highest_forecasted_count": (
                highest["forecast_next_month"] if highest else 0.0
            ),
            "highest_growth_course": (
                highest_growth["course"] if highest_growth else None
            ),
            "highest_growth_percentage": (
                highest_growth["growth_percentage"] if highest_growth else 0.0
            ),
            "most_popular_course": distributions.get("most_popular_course"),
            "courses_modeled": len(self._weekly_models),
            "model": "ARIMA",
            "arima_order": list(ARIMA_ORDER),
            "data_source": "datasets/applicant_volume.csv",
            "aggregation": {
                "next_week": "ARIMA(1,1,1) weekly step 1 (genuine weekly forecast)",
                "next_month": "sum of ARIMA weekly steps 1-4 (~4 weeks)",
                "next_quarter": "sum of ARIMA weekly steps 1-13 (~13 weeks)",
            },
            "note": (
                "Forecasts are produced by fitting ARIMA(1,1,1) on weekly-aggregated "
                "applicant counts.  next_week is a genuine one-step weekly forecast.  "
                "next_month and next_quarter are multi-step horizon sums."
            ),
        }

    def get_course_forecasts(
        self,
        period: str = "next_month",
        course: str | None = None,
    ) -> list[dict]:
        """
        Return course forecasts ranked by forecasted applicant count.

        course=None → all available courses.
        course=str  → list containing only that course.
        """
        if period not in FORECAST_PERIODS:
            raise ValueError(
                f"Unsupported period '{period}'. Use: {', '.join(FORECAST_PERIODS)}"
            )

        cache_key = f"{period}__{course or '__all__'}"
        if cache_key in self._cached_course_forecasts:
            return self._cached_course_forecasts[cache_key]

        courses = (
            [course] if course else self._repository.get_available_courses()
        )
        results: list[dict] = []

        for c in courses:
            series = self._weekly_series[c]
            preds = self._weekly_forecast[c]

            fw = round(float(preds[0]), 1)
            fm = round(sum(preds[:STEPS_NEXT_MONTH]), 1)
            fq = round(sum(preds[:STEPS_NEXT_QUARTER]), 1)
            historical_total = self._repository.get_course_total_historical(c)
            current_count = int(round(float(series.iloc[-1]))) if len(series) else 0

            if period == "next_week":
                forecasted = fw
            elif period == "next_quarter":
                forecasted = fq
            else:
                forecasted = fm

            growth_pct, trend_label = self._growth_and_trend(series, period, preds)

            results.append(
                {
                    "course": c,
                    "historical_total_applicants": historical_total,
                    "current_applicant_count": current_count,
                    "forecasted_applicant_count": forecasted,
                    "forecast_next_week": fw,
                    "forecast_next_month": fm,
                    "forecast_next_quarter": fq,
                    "trend": trend_label,
                    "growth_percentage": growth_pct,
                    "period": period,
                }
            )

        results.sort(key=lambda x: x["forecasted_applicant_count"], reverse=True)
        self._cached_course_forecasts[cache_key] = results
        return results

    def get_insights(
        self,
        period: str = "next_month",
        course_forecasts: list[dict] | None = None,
        course: str | None = None,
    ) -> list[str]:
        """Generate administrator-facing planning insights."""
        items = course_forecasts or self.get_course_forecasts(
            period=period, course=course
        )
        distributions = self._get_distributions()

        if not items:
            return ["No forecasting data is available yet."]

        highest = items[0]
        fastest = max(items, key=lambda x: x["growth_percentage"])
        insights: list[str] = []

        if course:
            insights.append(
                f"Course '{course}' is projected to receive "
                f"{highest['forecasted_applicant_count']:,.0f} applicants "
                "for the selected period."
            )
        else:
            insights.append(
                f"{highest['course']} has the highest projected applicant volume "
                f"({highest['forecasted_applicant_count']:,.0f}) for the selected period."
            )
            insights.append(
                f"{fastest['course']} is the fastest growing course "
                f"({fastest['growth_percentage']:+.1f}% versus recent weekly average)."
            )
            if len(items) > 1:
                lowest = items[-1]
                insights.append(
                    f"{lowest['course']} has the lowest projected applicant volume "
                    f"({lowest['forecasted_applicant_count']:,.0f})."
                )

        if distributions.get("most_popular_course"):
            insights.append(
                f"The most popular course historically is "
                f"{distributions['most_popular_course']}."
            )

        return insights

    def get_dashboard(
        self,
        period: str = "next_month",
        course: str | None = None,
    ) -> dict:
        """Return a single payload for the forecasting analytics dashboard."""
        if period not in FORECAST_PERIODS:
            raise ValueError(
                f"Unsupported period '{period}'. Use: {', '.join(FORECAST_PERIODS)}"
            )

        course_items = self.get_course_forecasts(period=period, course=course)
        summary = self.get_summary(course_forecasts=course_items, course=course)

        # Charts always use monthly aggregation for the historical trend line.
        monthly_items = (
            course_items
            if period == "next_month"
            else self.get_course_forecasts(period="next_month", course=course)
        )

        return {
            "period": period,
            "course_filter": course,
            "summary": summary,
            "courses": course_items,
            "charts": self.get_charts(
                course_forecasts=monthly_items,
                summary=summary,
                course=course,
            ),
            "insights": self.get_insights(
                period=period,
                course_forecasts=course_items,
                course=course,
            ),
        }

    def get_course_detail(self, course: str) -> dict:
        """Return forecast detail for one specific course."""
        self._repository.validate_course(course)

        preds = self._weekly_forecast[course]
        series = self._weekly_series[course]

        fw = round(float(preds[0]), 1)
        fm = round(sum(preds[:STEPS_NEXT_MONTH]), 1)
        fq = round(sum(preds[:STEPS_NEXT_QUARTER]), 1)

        # Historical volume: use monthly aggregation for charts.
        monthly_series = self._repository.get_course_monthly_series(course)
        historical_volume = [
            {
                "period": str(idx.strftime("%b %Y")),
                "applicants": round(float(v), 1),
            }
            for idx, v in monthly_series.iloc[-18:].items()
        ]

        # Forecast curve: show next 3 monthly-equivalent windows.
        last_date = monthly_series.index[-1]
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1), periods=3, freq="MS"
        )
        # Bucket weekly preds into 3 months of ~4 weeks each.
        monthly_preds_3 = [
            round(sum(preds[i * STEPS_NEXT_MONTH:(i + 1) * STEPS_NEXT_MONTH]), 1)
            for i in range(3)
        ]
        forecast_volume = [
            {
                "period": str(future_dates[i].strftime("%b %Y")),
                "applicants": monthly_preds_3[i],
            }
            for i in range(3)
        ]

        _, trend_label = self._growth_and_trend(series, "next_week", preds)

        return {
            "course": course,
            "current_applicant_count": int(round(float(series.iloc[-1]))),
            "forecast_next_week": fw,
            "forecast_next_month": fm,
            "forecast_next_quarter": fq,
            "trend": trend_label,
            "monthly_forecast": monthly_preds_3,
            "historical_volume": historical_volume,
            "forecast_volume": forecast_volume,
            "note": (
                "Forecasts are from ARIMA(1,1,1) fitted on weekly applicant counts. "
                "next_week = step 1; next_month ≈ 4 weekly steps; "
                "next_quarter ≈ 13 weekly steps."
            ),
        }

    def get_charts(
        self,
        course_forecasts: list[dict] | None = None,
        summary: dict | None = None,
        course: str | None = None,
    ) -> dict:
        """
        Return chart-ready JSON series for the forecasting dashboard.

        Historical trends use monthly aggregated data for readability.
        Forecast curve shows next 3 monthly-equivalent windows.
        Distributions remain organisation-level.
        """
        forecasts = course_forecasts or self.get_course_forecasts(
            period="next_month", course=course
        )
        summary_payload = summary or self.get_summary(
            course_forecasts=forecasts, course=course
        )

        # Monthly history for the trend-over-time chart.
        if course:
            monthly_history = self._repository.get_course_monthly_series(course)
        else:
            monthly_history = self._repository.get_tldc_series("M")

        historical_trend = [
            {
                "period": str(idx.strftime("%b %Y")),
                "applicants": round(float(v), 1),
            }
            for idx, v in monthly_history.iloc[-18:].items()
        ]

        # Weekly history for the weekly chart.
        if course:
            weekly_history = self._weekly_series[course]
        else:
            weekly_history = self._repository.get_tldc_series("W")

        weekly_trend = [
            {
                "period": str(idx.strftime("%Y-%m-%d")),
                "applicants": round(float(v), 1),
            }
            for idx, v in weekly_history.iloc[-26:].items()
        ]

        # Forecast curve: next 3 monthly-equivalent windows.
        last_date = monthly_history.index[-1]
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1), periods=3, freq="MS"
        )

        if course:
            curve = [
                round(
                    sum(
                        self._weekly_forecast[course][
                            i * STEPS_NEXT_MONTH:(i + 1) * STEPS_NEXT_MONTH
                        ]
                    ),
                    1,
                )
                for i in range(3)
            ]
        else:
            curve = [
                round(
                    sum(
                        sum(
                            self._weekly_forecast[c][
                                i * STEPS_NEXT_MONTH:(i + 1) * STEPS_NEXT_MONTH
                            ]
                        )
                        for c in self._weekly_forecast
                    ),
                    1,
                )
                for i in range(3)
            ]

        forecast_curve = [
            {
                "period": str(future_dates[i].strftime("%b %Y")),
                "applicants": curve[i],
            }
            for i in range(3)
        ]

        top_courses = [
            {
                "course": item["course"],
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
            "top_courses": top_courses,
            "summary_points": [
                {
                    "label": "Next Week",
                    "applicants": summary_payload["expected_applicants_next_week"],
                },
                {
                    "label": "Next Month (~4 weeks)",
                    "applicants": summary_payload["expected_applicants_next_month"],
                },
                {
                    "label": "Next Quarter (~13 weeks)",
                    "applicants": summary_payload["expected_applicants_next_quarter"],
                },
            ],
            "employment_distribution": distributions.get("employment_distribution", []),
            "education_distribution": distributions.get("education_distribution", []),
            "course_distribution": distributions.get("course_distribution", []),
            "sex_distribution": distributions.get("sex_distribution", []),
            "age_distribution": distributions.get("age_distribution", []),
            "learner_classification_distribution": distributions.get(
                "learner_classification_distribution", []
            ),
            "barangay_distribution": distributions.get("barangay_distribution", []),
        }

    def get_barangay_profile(self, barangay: str) -> dict:
        """Return historical demographic profile for one barangay (descriptive only)."""
        return self._statistics.get_barangay_profile(barangay)

    # ------------------------------------------------------------------
    # /predict/applicant-volume adapter
    # ------------------------------------------------------------------

    _PREDICT_PERIODS: dict[str, int] = {
        "next_month": STEPS_NEXT_MONTH,
        "next_quarter": STEPS_NEXT_QUARTER,
        "next_6_months": STEPS_NEXT_6_MONTHS,
        "next_12_months": STEPS_NEXT_12_MONTHS,
    }
    _PREDICT_LABELS: dict[str, str] = {
        "next_month": "Next Month (~4 weeks)",
        "next_quarter": "Next Quarter (~13 weeks)",
        "next_6_months": "Next 6 Months (~26 weeks)",
        "next_12_months": "Next 12 Months (~52 weeks)",
    }
    _HISTORICAL_CHART_MONTHS: int = 18

    def forecast_applicant_volume(
        self,
        forecast_period: str,
        course: str | None = None,
    ) -> dict:
        """
        Return a response compatible with POST /predict/applicant-volume.

        Uses weekly ARIMA forecasts.  The `monthly_forecast` field in the
        response now contains MONTHLY-EQUIVALENT totals (each = sum of ~4
        or ~13 weekly steps depending on the horizon), so the field name is
        slightly misleading but is preserved for Laravel compatibility.
        """
        if forecast_period not in self._PREDICT_PERIODS:
            accepted = ", ".join(self._PREDICT_PERIODS)
            raise UnknownForecastPeriodError(
                f"Unknown forecast period '{forecast_period}'. Accepted: {accepted}"
            )
        if course is not None and course not in self._weekly_forecast:
            accepted = ", ".join(sorted(self._weekly_forecast))
            raise UnknownCourseError(
                f"Unknown course '{course}'. Accepted: {accepted}"
            )

        steps = self._PREDICT_PERIODS[forecast_period]

        # Build per-course or TLDC-wide weekly forecast list.
        if course is None:
            weekly_preds = [
                round(
                    sum(self._weekly_forecast[c][i] for c in self._weekly_forecast),
                    1,
                )
                for i in range(steps)
            ]
            hist_series = self._repository.get_tldc_series("W")
            hist_monthly = self._repository.get_tldc_series("M")
        else:
            weekly_preds = self._weekly_forecast[course][:steps]
            hist_series = self._weekly_series[course]
            hist_monthly = self._repository.get_course_monthly_series(course)

        forecast_total = round(sum(weekly_preds), 1)

        # Previous period total: same number of weeks from history tail.
        if len(hist_series) >= steps:
            previous_total = round(float(hist_series.iloc[-steps:].sum()), 1)
        else:
            previous_total = round(float(hist_series.sum()), 1)

        growth_pct = (
            0.0
            if previous_total == 0
            else round(((forecast_total - previous_total) / previous_total) * 100, 1)
        )
        direction = (
            "growth" if growth_pct > 1 else "decline" if growth_pct < -1 else "stable"
        )

        # Historical chart data: last 18 months.
        history_slice = hist_monthly.iloc[-self._HISTORICAL_CHART_MONTHS:]
        historical_volume = [
            {
                "period": str(idx.strftime("%b %Y")),
                "applicants": round(float(v), 1),
            }
            for idx, v in history_slice.items()
        ]

        # Forecast volume: bucket weekly preds into monthly-equivalent windows.
        last_date = hist_monthly.index[-1]
        # Steps per month-equivalent depends on horizon.
        steps_per_bucket = STEPS_NEXT_MONTH  # always 4 weeks per "month"
        n_buckets = max(1, steps // steps_per_bucket)
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1), periods=n_buckets, freq="MS"
        )
        monthly_buckets = [
            round(sum(weekly_preds[i * steps_per_bucket:(i + 1) * steps_per_bucket]), 1)
            for i in range(n_buckets)
        ]
        forecast_volume = [
            {
                "period": str(future_dates[i].strftime("%b %Y")),
                "applicants": monthly_buckets[i],
            }
            for i in range(n_buckets)
        ]

        # Insights.
        label = self._PREDICT_LABELS[forecast_period]
        subject = f"course '{course}'" if course else "TLDC"
        insights: list[str] = [
            f"{subject} is projected to receive {forecast_total:,.0f} applicants "
            f"during the {label.lower()} planning window.",
        ]
        if direction == "growth":
            insights.append(
                f"Applicant volume is expected to increase by {abs(growth_pct)}% "
                "compared with the equivalent previous period."
            )
        elif direction == "decline":
            insights.append(
                f"Applicant volume is expected to decrease by {abs(growth_pct)}% "
                "compared with the equivalent previous period."
            )
        else:
            insights.append(
                "Applicant volume is expected to remain stable compared with "
                "the equivalent previous period."
            )
        if len(weekly_preds) > 1:
            peak_val = max(weekly_preds)
            peak_idx = weekly_preds.index(peak_val) + 1
            insights.append(
                f"Peak weekly demand is projected in week {peak_idx} with "
                f"approximately {peak_val:,.0f} applicants."
            )
        insights.append(
            "Use this forecast to plan instructor allocation, training "
            "schedules, and coordination across all TLDC programs."
        )

        # Confidence.
        try:
            from services.forecasting_evaluation import get_forecasting_evaluation_service
            ev = get_forecasting_evaluation_service().evaluate()
            raw_mae = ev["overall"].get("mae") or 0.0
        except Exception:
            raw_mae = 0.0
        hist_mean = float(self._repository.get_tldc_series("W").mean()) or 1.0
        ratio = raw_mae / hist_mean
        confidence_level = (
            "High" if ratio < 0.08 else "Medium" if ratio < 0.15 else "Low"
        )

        return {
            "forecast_period": forecast_period,
            "planning_period_label": label,
            "course": course,
            "total_predicted_applicants": forecast_total,
            "previous_period_total": previous_total,
            "growth_percentage": growth_pct,
            "growth_direction": direction,
            "confidence_level": confidence_level,
            "monthly_forecast": monthly_buckets,
            "historical_volume": historical_volume,
            "forecast_volume": forecast_volume,
            "ai_planning_insights": insights,
        }


# ---------------------------------------------------------------------------
# Module-level convenience wrapper
# ---------------------------------------------------------------------------

def forecast_applicant_volume(
    forecast_period: str,
    course: str | None = None,
) -> dict:
    """Convenience wrapper for POST /predict/applicant-volume."""
    return get_forecasting_service().forecast_applicant_volume(
        forecast_period, course=course
    )


_service: ForecastingService | None = None


def get_forecasting_service() -> ForecastingService:
    """Return the singleton forecasting service."""
    global _service
    if _service is None:
        _service = ForecastingService()
    return _service


def reset_forecasting_service() -> None:
    """Clear the singleton (useful for tests)."""
    global _service
    _service = None


__all__ = [
    "ForecastingService",
    "UnknownForecastPeriodError",
    "UnknownCourseError",
    "forecast_applicant_volume",
    "get_forecasting_service",
    "reset_forecasting_service",
]
