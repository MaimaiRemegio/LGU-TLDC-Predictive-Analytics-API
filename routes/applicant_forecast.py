from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.applicant_forecast_service import (
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

    model_config = {
        "json_schema_extra": {
            "examples": [{"forecast_period": "next_quarter"}]
        }
    }


class ApplicantForecastResponse(BaseModel):
    forecast_period: str
    planning_period_label: str
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
    summary="Forecast total TLDC applicant volume",
)
def predict_applicant_volume(request: ApplicantForecastRequest) -> ApplicantForecastResponse:
    try:
        result = forecast_applicant_volume(request.forecast_period)
    except UnknownForecastPeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApplicantForecastResponse(**result)
