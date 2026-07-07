from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.applicant_data_repository import CourseNotFoundError, get_applicant_data_repository
from services.completion_predictor import UnknownCategoryError, recommend_barangays
from services.recommendation_explainer import build_recommendation_reason

router = APIRouter(prefix="/predict", tags=["Barangay Recommendation"])


class CourseRecommendationRequest(BaseModel):
    course_applied: str = Field(..., examples=["Cookery NC II"])

    model_config = {
        "json_schema_extra": {
            "examples": [{"course_applied": "Cookery NC II"}]
        }
    }


class BarangayRecommendation(BaseModel):
    barangay: str = Field(..., examples=["Busay"])
    completion_probability: float = Field(
        ...,
        description="Predicted suitability probability for this barangay, as a percentage.",
        examples=[92.4],
    )


class HistoricalCompletionRate(BaseModel):
    title: str
    completion_rate: float
    graduates: int
    total_applicants: int
    detail: str


class CourseSuccessRate(BaseModel):
    title: str
    course_applied: str
    graduates: int
    total_applicants: int
    detail: str


class RandomForestEvaluation(BaseModel):
    title: str
    barangays_evaluated: int
    description: str


class RecommendationReason(BaseModel):
    barangay: str
    course_applied: str
    historical_completion_rate: HistoricalCompletionRate | None = None
    course_success_rate: CourseSuccessRate | None = None
    random_forest_evaluation: RandomForestEvaluation | None = None
    prediction_confidence: float


class AIDecisionSummary(BaseModel):
    model_used: str
    dataset: str
    training_records: int
    barangays_evaluated: int
    course_selected: str
    top_recommended_barangay: str
    prediction_confidence: float


class ExplainableAI(BaseModel):
    recommendation_reason: RecommendationReason
    ai_decision_summary: AIDecisionSummary
    evaluation_message: str


class WorkforceDistributionItem(BaseModel):
    label: str
    count: int
    percentage: float


class CourseWorkforceProfile(BaseModel):
    course_applied: str
    total_historical_applicants: int
    historical_graduates: int
    historical_completion_rate: float
    most_common_skills: list[WorkforceDistributionItem]
    most_common_educational_attainment: list[WorkforceDistributionItem]
    employment_status_distribution: list[WorkforceDistributionItem]
    most_common_desired_careers: list[WorkforceDistributionItem]
    learner_classification_distribution: list[WorkforceDistributionItem]


class BarangayRecommendationResponse(BaseModel):
    course_applied: str
    applicant_profile: dict
    course_workforce_profile: CourseWorkforceProfile
    recommended_barangays: list[BarangayRecommendation]
    explainable_ai: ExplainableAI | None = None


@router.post(
    "/completion",
    response_model=BarangayRecommendationResponse,
    summary="Recommend barangays for a training program",
    response_description="All barangays ranked by predicted suitability for the auto-loaded applicant profile.",
)
def recommend_barangays_by_completion(
    request: CourseRecommendationRequest,
) -> BarangayRecommendationResponse:
    """
    Load a matching synthetic applicant profile for the selected course,
    predict barangay suitability probabilities, and return ranked recommendations.
    """
    try:
        repository = get_applicant_data_repository()
        applicant_profile = repository.get_applicant_profile_for_course(request.course_applied)
        workforce_profile = repository.get_course_workforce_profile(request.course_applied)
        recommendations = recommend_barangays(applicant_profile)
        explainable_ai = build_recommendation_reason(
            applicant_profile,
            recommendations,
            repository.get_historical_data(),
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownCategoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BarangayRecommendationResponse(
        course_applied=request.course_applied,
        applicant_profile=applicant_profile,
        course_workforce_profile=CourseWorkforceProfile(**workforce_profile),
        recommended_barangays=[
            BarangayRecommendation(**recommendation)
            for recommendation in recommendations
        ],
        explainable_ai=(
            ExplainableAI(**explainable_ai)
            if explainable_ai is not None
            else None
        ),
    )
