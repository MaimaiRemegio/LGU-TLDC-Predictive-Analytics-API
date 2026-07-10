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





class HistoricalSupportingEvidence(BaseModel):

    label: str = Field(

        default="Historical Supporting Evidence",

        description="Identifies these values as historical supporting evidence only.",

    )

    historical_participation_percentage: float

    historical_completion_percentage: float

    historical_dropout_percentage: float

    historical_applicant_count: int





class BarangayRecommendation(BaseModel):

    barangay: str = Field(..., examples=["Busay"])

    completion_probability: float = Field(

        ...,

        description=(

            "Predicted probability of successful training completion for a "

            "representative applicant deployed in this barangay, as a percentage "

            "(P(Graduate | barangay, course, profile) from the Random Forest)."

        ),

        examples=[84.6],

    )

    confidence_level: str = Field(

        ...,

        description="Confidence label derived from the predicted completion probability.",

        examples=["High Confidence"],

    )

    data_reliability: str = Field(

        ...,

        description=(

            "Indicates whether enough historical records exist for this barangay. "

            "Barangays with fewer than 20 applicants are marked as limited data."

        ),

        examples=["Reliable"],

    )

    historical_participation_percentage: float = Field(

        ...,

        description="Share of historical applicants for the selected course from this barangay.",

        examples=[5.6],

    )

    historical_applicants: int = Field(

        ...,

        description="Total historical applicants from this barangay for the selected course.",

        examples=[34],

    )

    historical_supporting_evidence: HistoricalSupportingEvidence | None = None





class HistoricalCompletionRate(BaseModel):

    title: str

    label: str = "Historical Supporting Evidence"

    completion_rate: float

    graduates: int

    total_applicants: int

    detail: str





class HistoricalDropoutRate(BaseModel):

    title: str

    label: str = "Historical Supporting Evidence"

    dropout_rate: float

    dropouts: int

    total_applicants: int

    detail: str





class CourseSuccessRate(BaseModel):

    title: str

    label: str = "Historical Supporting Evidence"

    course_applied: str

    graduates: int

    total_applicants: int

    detail: str





class RandomForestEvaluation(BaseModel):

    title: str

    barangay: str

    course_applied: str

    barangays_evaluated: int

    recommendation_score: float

    confidence_level: str

    recommendation_factors: list[str]

    defense_summary: str

    description: str





class ModelValidationMetrics(BaseModel):

    accuracy: float | None = None

    precision: float | None = None

    recall: float | None = None

    f1_score: float | None = None

    roc_auc: float | None = None

    confusion_matrix: list[list[int]] | None = None

    class_labels: list[str] | None = None





class RecommendationReason(BaseModel):

    barangay: str

    course_applied: str

    historical_completion_rate: HistoricalCompletionRate | None = None

    historical_dropout_rate: HistoricalDropoutRate | None = None

    course_success_rate: CourseSuccessRate | None = None

    random_forest_evaluation: RandomForestEvaluation | None = None

    prediction_confidence: float

    confidence_level: str

    recommendation_factors: list[str]

    defense_summary: str





class AIDecisionSummary(BaseModel):

    model_used: str

    dataset: str

    training_records: int

    barangays_evaluated: int

    course_selected: str

    top_recommended_barangay: str

    prediction_confidence: float

    confidence_level: str

    recommendation_factors: list[str]

    defense_summary: str

    model_validation: ModelValidationMetrics | None = None





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





def _build_barangay_recommendation(

    recommendation: dict,

    participation_by_barangay: dict[str, dict],

    supporting_evidence_by_barangay: dict[str, dict],

) -> BarangayRecommendation:

    barangay = recommendation["barangay"]

    participation = participation_by_barangay.get(

        barangay,

        {"historical_applicants": 0, "historical_participation_percentage": 0.0, "data_reliability": "Limited historical data"},

    )

    supporting_evidence = supporting_evidence_by_barangay.get(barangay)



    return BarangayRecommendation(

        barangay=barangay,

        completion_probability=recommendation["completion_probability"],

        confidence_level=recommendation["confidence_level"],

        data_reliability=participation["data_reliability"],

        historical_participation_percentage=participation["historical_participation_percentage"],

        historical_applicants=participation["historical_applicants"],

        historical_supporting_evidence=(

            HistoricalSupportingEvidence(**supporting_evidence)

            if supporting_evidence is not None

            else None

        ),

    )





@router.post(

    "/completion",

    response_model=BarangayRecommendationResponse,

    summary="Recommend barangays for a training program",

    response_description="All barangays ranked by predicted training-completion probability for the auto-loaded applicant profile.",

)

def recommend_barangays_by_completion(

    request: CourseRecommendationRequest,

) -> BarangayRecommendationResponse:

    """

    Load a matching synthetic applicant profile for the selected course, score

    that profile against every barangay, and return barangays ranked by the

    predicted probability of successful training completion.

    """

    try:

        repository = get_applicant_data_repository()

        applicant_profile = repository.get_applicant_profile_for_course(request.course_applied)

        workforce_profile = repository.get_course_workforce_profile(request.course_applied)

        participation_by_barangay = repository.get_barangay_participation_for_course(

            request.course_applied

        )

        supporting_evidence_by_barangay = (

            repository.get_barangay_historical_supporting_evidence_for_course(

                request.course_applied

            )

        )

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

            _build_barangay_recommendation(

                recommendation,

                participation_by_barangay,

                supporting_evidence_by_barangay,

            )

            for recommendation in recommendations

        ],

        explainable_ai=(

            ExplainableAI(**explainable_ai)

            if explainable_ai is not None

            else None

        ),

    )

