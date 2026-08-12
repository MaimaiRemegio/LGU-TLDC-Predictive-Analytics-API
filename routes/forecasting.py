"""
REST API routes for the TLDC Applicant Volume Forecasting module.

Independent from Barangay Recommendation endpoints.

Forecast filters
----------------
period : next_week | next_month | next_quarter
course : specific course name | omit for TLDC-wide (all courses)

next_week note
--------------
next_week is an estimated weekly equivalent (next_month ÷ 4.33).
The source dataset is monthly only; no weekly ARIMA is fitted.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.forecasting_repository import (
    BarangayNotFoundError,
    CourseNotFoundError,
)
from services.forecasting_evaluation import get_forecasting_evaluation_service
from services.forecasting_service import get_forecasting_service

router = APIRouter(prefix="/forecast", tags=["Applicant Volume Forecasting"])


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class SummaryPoint(BaseModel):
    label: str
    applicants: float


class VolumePoint(BaseModel):
    period: str
    applicants: float


class DistributionItem(BaseModel):
    label: str
    count: int
    percentage: float


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class ForecastSummaryResponse(BaseModel):
    expected_applicants_next_week: float
    expected_applicants_next_month: float
    expected_applicants_next_quarter: float
    previous_week_total: float
    previous_month_total: float
    previous_quarter_total: float
    total_historical_applicants: int
    highest_forecasted_course: str | None
    highest_forecasted_count: float
    highest_growth_course: str | None
    highest_growth_percentage: float
    most_popular_course: str | None
    courses_modeled: int
    model: str
    arima_order: list[int]
    data_source: str
    aggregation: dict[str, str]
    note: str


# ---------------------------------------------------------------------------
# Course forecasts
# ---------------------------------------------------------------------------

class CourseForecastItem(BaseModel):
    course: str
    historical_total_applicants: int
    current_applicant_count: int
    forecasted_applicant_count: float
    forecast_next_week: float
    forecast_next_month: float
    forecast_next_quarter: float
    trend: Literal["Increasing", "Stable", "Decreasing"]
    growth_percentage: float
    period: str


class CourseForecastListResponse(BaseModel):
    period: str
    course_filter: str | None
    courses: list[CourseForecastItem]


class CourseDetailResponse(BaseModel):
    course: str
    current_applicant_count: int
    forecast_next_week: float
    forecast_next_month: float
    forecast_next_quarter: float
    trend: Literal["Increasing", "Stable", "Decreasing"]
    monthly_forecast: list[float]
    historical_volume: list[VolumePoint]
    forecast_volume: list[VolumePoint]
    note: str


# ---------------------------------------------------------------------------
# Charts / dashboard
# ---------------------------------------------------------------------------

class TopCourseChartItem(BaseModel):
    course: str
    forecasted_applicant_count: float
    trend: str


class ForecastChartsResponse(BaseModel):
    applicant_trend_over_time: list[VolumePoint]
    weekly_applicant_trend: list[VolumePoint]
    forecast_curve: list[VolumePoint]
    top_courses: list[TopCourseChartItem]
    summary_points: list[SummaryPoint]
    employment_distribution: list[DistributionItem]
    education_distribution: list[DistributionItem]
    course_distribution: list[DistributionItem]
    sex_distribution: list[DistributionItem]
    age_distribution: list[DistributionItem]
    learner_classification_distribution: list[DistributionItem]
    barangay_distribution: list[DistributionItem]


class ForecastDashboardResponse(BaseModel):
    period: str
    course_filter: str | None
    summary: ForecastSummaryResponse
    courses: list[CourseForecastItem]
    charts: ForecastChartsResponse
    insights: list[str]


# ---------------------------------------------------------------------------
# Barangay profile (descriptive only — NOT ARIMA)
# ---------------------------------------------------------------------------

class BarangayProfileResponse(BaseModel):
    barangay: str
    total_applicants: int
    registration_event_count: int = 0
    male_count: int
    female_count: int
    average_age: float | None = None
    sex_distribution: list[DistributionItem]
    age_distribution: list[DistributionItem]
    educational_attainment_distribution: list[DistributionItem]
    employment_status_distribution: list[DistributionItem]
    learner_classification_distribution: list[DistributionItem]
    most_applied_course: str | None
    course_distribution: list[DistributionItem]
    desired_career_distribution: list[DistributionItem]
    current_skill_distribution: list[DistributionItem]
    note: str


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class OverallEvaluationMetrics(BaseModel):
    mape: float | None
    mae: float | None
    rmse: float | None
    test_periods: int
    mape_periods: int = 0


class CourseEvaluationItem(BaseModel):
    course: str
    mape: float | None
    mae: float | None
    rmse: float | None
    test_periods: int


class SkippedCourseItem(BaseModel):
    course: str
    reason: str


class ForecastEvaluationResponse(BaseModel):
    data_source: str
    dataset_type: str
    evaluation_method: str
    frequency: str
    arima_order: list[int]
    train_ratio: float
    training_period: str
    testing_period: str
    overall: OverallEvaluationMetrics
    model_assessment: str
    accuracy_scope: str
    real_data_disclaimer: str
    course_results: list[CourseEvaluationItem]
    skipped_courses: list[SkippedCourseItem] = []
    note: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=ForecastDashboardResponse,
    summary="Full forecasting dashboard payload",
)
def get_forecast_dashboard(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
        description="Forecast horizon.",
    ),
    course: str | None = Query(
        default=None,
        description="Filter by course. Omit for TLDC-wide (all courses summed).",
    ),
) -> ForecastDashboardResponse:
    """Return summary, course rankings, charts, and insights."""
    service = get_forecasting_service()
    try:
        payload = service.get_dashboard(period=period, course=course)
    except (ValueError, CourseNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ForecastDashboardResponse(**payload)


@router.get(
    "/summary",
    response_model=ForecastSummaryResponse,
    summary="Overall applicant volume forecast summary",
)
def get_forecast_summary(
    course: str | None = Query(
        default=None,
        description="Filter by course. Omit for TLDC-wide.",
    ),
) -> ForecastSummaryResponse:
    """Return expected applicants for next week (est.), next month, and next quarter."""
    service = get_forecasting_service()
    try:
        return ForecastSummaryResponse(**service.get_summary(course=course))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/courses",
    response_model=CourseForecastListResponse,
    summary="Forecast by course",
)
def get_forecast_by_course(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
        description="Forecast horizon used for ranking courses.",
    ),
    course: str | None = Query(
        default=None,
        description="Filter to a single course. Omit for all courses.",
    ),
) -> CourseForecastListResponse:
    """Return all courses (or one course) ranked by forecasted applicant volume."""
    service = get_forecasting_service()
    try:
        items = service.get_course_forecasts(period=period, course=course)
    except (ValueError, CourseNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CourseForecastListResponse(
        period=period,
        course_filter=course,
        courses=[CourseForecastItem(**item) for item in items],
    )


@router.get(
    "/course/{course_name}",
    response_model=CourseDetailResponse,
    summary="Forecast detail for one course",
)
def get_course_forecast_detail(course_name: str) -> CourseDetailResponse:
    """Return forecast detail and historical series for one course."""
    service = get_forecasting_service()
    try:
        detail = service.get_course_detail(course_name)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CourseDetailResponse(**detail)


@router.get(
    "/charts",
    response_model=ForecastChartsResponse,
    summary="Chart-ready forecasting datasets",
)
def get_forecast_charts(
    course: str | None = Query(
        default=None,
        description="Filter by course. Omit for TLDC-wide.",
    ),
) -> ForecastChartsResponse:
    """Return JSON series for trend, forecast curve, top courses, and distributions."""
    service = get_forecasting_service()
    try:
        return ForecastChartsResponse(**service.get_charts(course=course))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/insights",
    response_model=list[str],
    summary="Administrator forecasting insights",
)
def get_forecast_insights(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
    ),
    course: str | None = Query(
        default=None,
        description="Filter by course. Omit for TLDC-wide.",
    ),
) -> list[str]:
    """Return short planning insights for administrators."""
    service = get_forecasting_service()
    try:
        return service.get_insights(period=period, course=course)
    except (ValueError, CourseNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/profile/{barangay}",
    response_model=BarangayProfileResponse,
    summary="Historical barangay applicant profile (descriptive only)",
)
def get_barangay_profile(barangay: str) -> BarangayProfileResponse:
    """
    Return historical demographic analytics for one barangay.

    This endpoint is descriptive only and does NOT use ARIMA forecasting.
    """
    service = get_forecasting_service()
    try:
        profile = service.get_barangay_profile(barangay)
    except BarangayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BarangayProfileResponse(**profile)


@router.get(
    "/evaluation",
    response_model=ForecastEvaluationResponse,
    summary="ARIMA chronological backtesting evaluation",
)
def get_forecast_evaluation() -> ForecastEvaluationResponse:
    """
    Return MAPE, MAE, and RMSE from chronological walk-forward backtesting.

    Metrics are computed per course on the synthetic monthly dataset.
    """
    service = get_forecasting_evaluation_service()
    payload = service.evaluate()
    return ForecastEvaluationResponse(**payload)
