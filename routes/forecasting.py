"""
REST API routes for the Applicant Volume Forecasting module.

Independent from Barangay Recommendation endpoints.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.forecasting_repository import BarangayNotFoundError
from services.forecasting_evaluation import get_forecasting_evaluation_service
from services.forecasting_service import get_forecasting_service

router = APIRouter(prefix="/forecast", tags=["Applicant Volume Forecasting"])


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


class ForecastSummaryResponse(BaseModel):
    expected_applicants_next_week: float
    expected_applicants_next_month: float
    expected_applicants_next_quarter: float
    previous_week_total: float
    previous_month_total: float
    previous_quarter_total: float
    total_historical_applicants: int
    highest_forecasted_barangay: str | None
    highest_forecasted_count: float
    highest_growth_barangay: str | None
    highest_growth_percentage: float
    most_popular_course: str | None
    barangays_modeled: int
    model: str
    arima_order: list[int]
    data_source: str
    aggregation: dict[str, str]
    note: str


class BarangayForecastItem(BaseModel):
    barangay: str
    historical_applicants: int
    current_applicant_count: int
    forecasted_applicant_count: float
    forecast_next_week: float
    forecast_next_month: float
    forecast_next_quarter: float
    trend: Literal["Increasing", "Stable", "Decreasing"]
    growth_percentage: float
    period: str


class BarangayForecastListResponse(BaseModel):
    period: str
    barangays: list[BarangayForecastItem]


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


class TopBarangayChartItem(BaseModel):
    barangay: str
    forecasted_applicant_count: float
    trend: str


class BarangayDetailResponse(BaseModel):
    barangay: str
    current_applicant_count: int
    forecast_next_week: float
    forecast_next_month: float
    forecast_next_quarter: float
    trend: Literal["Increasing", "Stable", "Decreasing"]
    monthly_forecast: list[float]
    historical_volume: list[VolumePoint]
    forecast_volume: list[VolumePoint]
    profile: BarangayProfileResponse


class ForecastChartsResponse(BaseModel):
    applicant_trend_over_time: list[VolumePoint]
    weekly_applicant_trend: list[VolumePoint]
    forecast_curve: list[VolumePoint]
    top_barangays: list[TopBarangayChartItem]
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
    summary: ForecastSummaryResponse
    barangays: list[BarangayForecastItem]
    charts: ForecastChartsResponse
    insights: list[str]
    selected_barangay: str | None
    selected_profile: BarangayProfileResponse | None


@router.get(
    "/dashboard",
    response_model=ForecastDashboardResponse,
    summary="Full forecasting dashboard payload",
)
def get_forecast_dashboard(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
        description="Forecast horizon used for ranking and insights.",
    ),
) -> ForecastDashboardResponse:
    """Return summary, barangay rankings, charts, insights, and default profile."""
    service = get_forecasting_service()
    try:
        payload = service.get_dashboard(period=period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ForecastDashboardResponse(**payload)


@router.get(
    "/summary",
    response_model=ForecastSummaryResponse,
    summary="Overall applicant volume forecast",
)
def get_forecast_summary() -> ForecastSummaryResponse:
    """Return expected applicants for next week, next month, and next quarter."""
    service = get_forecasting_service()
    return ForecastSummaryResponse(**service.get_summary())


@router.get(
    "/barangays",
    response_model=BarangayForecastListResponse,
    summary="Forecast by barangay",
)
def get_forecast_by_barangay(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
        description="Forecast horizon used for ranking barangays.",
    ),
) -> BarangayForecastListResponse:
    """Return every barangay ranked by forecasted applicant volume."""
    service = get_forecasting_service()
    try:
        barangays = service.get_barangay_forecasts(period=period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BarangayForecastListResponse(
        period=period,
        barangays=[BarangayForecastItem(**item) for item in barangays],
    )


@router.get(
    "/barangay/{barangay}",
    response_model=BarangayDetailResponse,
    summary="Forecast detail for one barangay",
)
def get_barangay_forecast(barangay: str) -> BarangayDetailResponse:
    """Return forecast detail, trend series, and historical profile for one barangay."""
    service = get_forecasting_service()
    try:
        detail = service.get_barangay_detail(barangay)
    except BarangayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BarangayDetailResponse(**detail)


@router.get(
    "/charts",
    response_model=ForecastChartsResponse,
    summary="Chart-ready forecasting datasets",
)
def get_forecast_charts() -> ForecastChartsResponse:
    """Return JSON series for trend, forecast curve, top barangays, and distributions."""
    service = get_forecasting_service()
    return ForecastChartsResponse(**service.get_charts())


@router.get(
    "/profile/{barangay}",
    response_model=BarangayProfileResponse,
    summary="Historical barangay applicant profile",
)
def get_barangay_profile(barangay: str) -> BarangayProfileResponse:
    """Return historical demographic analytics for one barangay."""
    service = get_forecasting_service()
    try:
        profile = service.get_barangay_profile(barangay)
    except BarangayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BarangayProfileResponse(**profile)


@router.get(
    "/insights",
    response_model=list[str],
    summary="Administrator forecasting insights",
)
def get_forecast_insights(
    period: Literal["next_week", "next_month", "next_quarter"] = Query(
        default="next_month",
    ),
) -> list[str]:
    """Return short automatic planning insights for administrators."""
    service = get_forecasting_service()
    try:
        return service.get_insights(period=period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class OverallEvaluationMetrics(BaseModel):
    mape: float | None
    mae: float | None
    rmse: float | None
    test_periods: int
    mape_periods: int = 0


class BarangayEvaluationItem(BaseModel):
    barangay: str
    mape: float | None
    mae: float | None
    rmse: float | None
    test_periods: int


class SkippedBarangayItem(BaseModel):
    barangay: str
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
    barangay_results: list[BarangayEvaluationItem]
    skipped_barangays: list[SkippedBarangayItem] = []
    note: str


@router.get(
    "/evaluation",
    response_model=ForecastEvaluationResponse,
    summary="ARIMA chronological backtesting evaluation",
)
def get_forecast_evaluation() -> ForecastEvaluationResponse:
    """
    Return MAPE, MAE, and RMSE from chronological walk-forward backtesting.

    Metrics are computed from actual predictions versus held-out historical
    weekly applicant volumes on the synthetic registration dataset.
    """
    service = get_forecasting_evaluation_service()
    payload = service.evaluate()
    return ForecastEvaluationResponse(**payload)
