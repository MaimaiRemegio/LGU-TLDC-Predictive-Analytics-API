from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.forecasting_service import (
    UnknownCourseError,
    UnknownForecastPeriodError,
    forecast_applicant_volume,
)

router = APIRouter(prefix="/predict", tags=["Applicant Volume Forecast"])


class VolumePoint(BaseModel):
    period: str
    applicants: float


class ApplicantForecastRequest(BaseModel):
    forecast_period: Literal[
        "next_month",
        "next_quarter",
        "next_6_months",
        "next_12_months",
    ] = Field(..., examples=["next_quarter"])

    course: str | None = Field(
        default=None,
        description=(
            "Optional course filter. "
            "Omit or pass null for TLDC-wide forecast (all courses summed)."
        ),
        examples=["Cookery NC II"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"forecast_period": "next_quarter"},
                {"forecast_period": "next_month", "course": "Cookery NC II"},
            ]
        }
    }


class ApplicantForecastResponse(BaseModel):
    forecast_period: str
    planning_period_label: str
    course: str | None
    total_predicted_applicants: float
    previous_period_total: float
    growth_percentage: float
    growth_direction: Literal["growth", "decline", "stable"]
    confidence_level: str
    monthly_forecast: list[float]
    historical_volume: list[VolumePoint]
    forecast_volume: list[VolumePoint]
    ai_planning_insights: list[str]


@router.post(
    "/applicant-volume",
    response_model=ApplicantForecastResponse,
    summary="Forecast total TLDC applicant volume (optionally filtered by course)",
)
def predict_applicant_volume(
    request: ApplicantForecastRequest,
) -> ApplicantForecastResponse:
    """
    Return a TLDC-wide or per-course ARIMA applicant volume forecast.

    - Omit `course` (or pass null) for the organisation-wide total.
    - Pass a course name to forecast that specific course only.
    """
    try:
        result = forecast_applicant_volume(
            request.forecast_period, course=request.course
        )
    except UnknownForecastPeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownCourseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApplicantForecastResponse(**result)
