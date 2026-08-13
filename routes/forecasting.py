"""
REST API routes for the TLDC Applicant Volume Forecasting module.

Independent from Barangay Recommendation endpoints.

Forecast filters
----------------
period : next_week | next_month | next_quarter
course : specific course name | omit for TLDC-wide (all courses)

Data Ingestion
--------------
POST /forecast/ingest-data - Ingest daily applicant volumes from Laravel
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

from services.forecasting_repository import (
    BarangayNotFoundError,
    CourseNotFoundError,
    get_forecasting_repository,
)
from services.forecasting_evaluation import get_forecasting_evaluation_service
from services.forecasting_service import get_forecasting_service

router = APIRouter(prefix="/forecast", tags=["Applicant Volume Forecasting"])


# ---------------------------------------------------------------------------
# Data Ingestion Models
# ---------------------------------------------------------------------------

class DailyVolumeRecord(BaseModel):
    date: str = Field(..., description="Application date in YYYY-MM-DD format")
    course: str = Field(..., description="Course name")
    applicant_count: int = Field(..., ge=0, description="Number of applicants")
    
    @validator('date')
    def validate_date(cls, v):
        from datetime import datetime
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class DateRange(BaseModel):
    start_date: str
    end_date: str


class DataIngestionRequest(BaseModel):
    source: str = Field(..., description="Data source identifier")
    data_version: str = Field(default="1.0", description="API version")
    sync_type: Literal["full", "incremental"] = Field(..., description="Sync mode")
    date_range: DateRange
    daily_volumes: list[DailyVolumeRecord]
    manual_retrain: bool = Field(default=False, description="Force retraining")


class DataIngestionResponse(BaseModel):
    status: str
    message: str
    records_received: int
    records_stored: int
    date_range: DateRange
    sync_type: str
    retraining_triggered: bool
    retraining_reason: str | None
    retraining_result: dict | None


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

@router.post(
    "/ingest-data",
    response_model=DataIngestionResponse,
    summary="Ingest daily applicant volume data",
)
def ingest_data(request: DataIngestionRequest) -> DataIngestionResponse:
    """
    Ingest daily applicant volume data from Laravel.
    
    Validates, stores, and optionally retrains ARIMA models based on data criteria.
    
    Retraining occurs when:
    - Sufficient new/changed data exists (>= 30 new days), OR
    - Manual retraining is requested
    """
    try:
        # Validate courses
        repository = get_forecasting_repository()
        valid_courses = set(repository.get_available_courses())
        
        validation_errors = []
        valid_records = []
        
        for idx, record in enumerate(request.daily_volumes):
            if record.course not in valid_courses:
                validation_errors.append({
                    "field": f"daily_volumes[{idx}].course",
                    "error": f"Unknown course '{record.course}'"
                })
            else:
                valid_records.append(record.dict())
        
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Validation failed",
                    "errors": validation_errors,
                    "records_received": len(request.daily_volumes),
                    "records_valid": len(valid_records)
                }
            )
        
        # Get last training time to calculate new data
        service = get_forecasting_service()
        last_training = service._last_training_time
        
        # Store data
        metrics = repository.upsert_daily_volumes(
            valid_records,
            sync_type=request.sync_type
        )
        
        # Calculate new data count
        if request.sync_type == "incremental" and last_training:
            new_data_count = repository.get_new_data_count(
                last_training.strftime('%Y-%m-%d')
            )
        else:
            # Full sync always has "new" data
            new_data_count = 999
        
        # Check if retraining is needed
        should_retrain, reason = service._should_retrain(
            new_data_count=new_data_count,
            manual_trigger=request.manual_retrain
        )
        
        retraining_result = None
        if should_retrain:
            # Perform retraining synchronously
            retraining_result = service.retrain_models(
                manual_trigger=request.manual_retrain
            )
        
        return DataIngestionResponse(
            status="completed",
            message="Data ingestion completed successfully",
            records_received=len(request.daily_volumes),
            records_stored=metrics["total_records"],
            date_range=request.date_range,
            sync_type=request.sync_type,
            retraining_triggered=should_retrain,
            retraining_reason=reason if should_retrain else None,
            retraining_result=retraining_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"Data ingestion failed: {str(e)}"
            }
        )


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
