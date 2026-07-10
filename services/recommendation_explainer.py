"""
Explainable AI (XAI) output for barangay recommendations.

Computes defense-ready explanations, confidence labels, recommendation
factors, and historical supporting evidence. The AI Recommendation Score
is always the Random Forest predict_proba() output — never tree votes or
historical completion rates.
"""

import pandas as pd

from services.completion_model_config import HISTORICAL_SUPPORTING_EVIDENCE_LABEL
from services.model_metadata import (
    get_confidence_label,
    get_model_validation_metrics,
    get_top_influencing_features,
)

GRADUATE_LABEL = "Graduate"
MODEL_USED_LABEL = "Random Forest Classifier"
DATASET_LABEL = "Historical Training Dataset (Synthetic)"

SCORE_EXPLANATION = (
    "The AI Recommendation Score represents the estimated probability that a "
    "representative applicant for the selected course will successfully complete "
    "the training if the program is deployed in the selected barangay."
)


def _count_graduates(records: pd.DataFrame) -> int:
    if records.empty:
        return 0
    return int((records["training_outcome"] == GRADUATE_LABEL).sum())


def _completion_rate_percent(graduates: int, total_applicants: int) -> float | None:
    if total_applicants == 0:
        return None
    return round((graduates / total_applicants) * 100, 1)


def _get_barangay_course_records(
    course_records: pd.DataFrame,
    barangay: str,
) -> pd.DataFrame:
    return course_records[course_records["barangay"] == barangay]


def _build_historical_completion_rate(
    course_records: pd.DataFrame,
    barangay: str,
    course: str,
) -> dict | None:
    """Historical completion rate — supporting evidence only."""
    barangay_records = _get_barangay_course_records(course_records, barangay)
    total_applicants = len(barangay_records)

    if total_applicants == 0:
        return None

    graduates = _count_graduates(barangay_records)
    completion_rate = _completion_rate_percent(graduates, total_applicants)

    if completion_rate is None:
        return None

    return {
        "title": "Historical Completion Rate",
        "label": HISTORICAL_SUPPORTING_EVIDENCE_LABEL,
        "completion_rate": completion_rate,
        "graduates": graduates,
        "total_applicants": total_applicants,
        "detail": (
            f"({graduates} graduates out of {total_applicants} {course} applicants in {barangay})"
        ),
    }


def _build_historical_dropout_rate(
    course_records: pd.DataFrame,
    barangay: str,
    course: str,
) -> dict | None:
    """Historical dropout rate — supporting evidence only."""
    barangay_records = _get_barangay_course_records(course_records, barangay)
    total_applicants = len(barangay_records)

    if total_applicants == 0:
        return None

    graduates = _count_graduates(barangay_records)
    dropouts = total_applicants - graduates
    dropout_rate = _completion_rate_percent(dropouts, total_applicants)

    if dropout_rate is None:
        return None

    return {
        "title": "Historical Dropout Rate",
        "label": HISTORICAL_SUPPORTING_EVIDENCE_LABEL,
        "dropout_rate": dropout_rate,
        "dropouts": dropouts,
        "total_applicants": total_applicants,
        "detail": (
            f"({dropouts} dropouts out of {total_applicants} {course} applicants in {barangay})"
        ),
    }


def _build_course_success_rate(
    course_records: pd.DataFrame,
    barangay: str,
    course: str,
) -> dict | None:
    """Course success summary — supporting evidence only."""
    barangay_records = _get_barangay_course_records(course_records, barangay)
    total_applicants = len(barangay_records)

    if total_applicants == 0:
        return None

    graduates = _count_graduates(barangay_records)

    return {
        "title": "Course Success Rate",
        "label": HISTORICAL_SUPPORTING_EVIDENCE_LABEL,
        "course_applied": course,
        "graduates": graduates,
        "total_applicants": total_applicants,
        "detail": (
            f"{graduates} of {total_applicants} {course} applicants successfully "
            f"completed training in {barangay}."
        ),
    }


def _build_recommendation_description(
    course: str,
    barangay: str,
    recommendation_score: float,
    barangays_evaluated: int,
) -> str:
    """
    Concise, defense-ready workflow explanation (150–250 words).

    Describes how the current Random Forest implementation produces the
    AI Recommendation Score without tree-vote or leaf-distribution jargon.
    """
    return (
        f"When an administrator selects a training course ({course}), the system "
        f"builds one representative applicant profile from historical records for "
        f"that course. This profile reflects the typical characteristics of past "
        f"applicants who enrolled in {course}.\n\n"
        f"The same representative profile is evaluated against all "
        f"{barangays_evaluated} barangays. For each barangay, the trained Random "
        f"Forest model predicts the probability that the representative applicant "
        f"would successfully complete the training if the program were deployed in "
        f"that area.\n\n"
        f"The system then compares the predicted completion probabilities of all "
        f"barangays and ranks them from highest to lowest. {barangay} has the "
        f"highest predicted completion probability ({recommendation_score}%), so it "
        f"becomes the recommended priority deployment area for {course}.\n\n"
        f"The AI Recommendation Score is the predicted completion probability "
        f"produced by the Random Forest model. It is not the same as the historical "
        f"completion rate. Historical Participation, Historical Completion, "
        f"Historical Dropout, and Course Success are computed separately from "
        f"historical records and displayed only as supporting evidence. These "
        f"historical statistics are not used to calculate the AI Recommendation "
        f"Score.\n\n"
        f"{SCORE_EXPLANATION}"
    )


def generate_ai_summary(
    course: str,
    barangay: str,
    completion_probability: float,
    barangays_evaluated: int,
) -> str:
    """Return a short defense-ready summary of the AI recommendation."""
    return (
        f"The representative applicant profile for {course} was evaluated across "
        f"all {barangays_evaluated} barangays. The Random Forest predicted the "
        f"probability of successful completion for each barangay. {barangay} "
        f"obtained the highest predicted completion probability of "
        f"{completion_probability}% and is recommended as the priority deployment "
        f"area. Historical statistics are supporting evidence only and are not "
        f"used to calculate the AI Recommendation Score."
    )


def _build_random_forest_evaluation(
    barangay: str,
    course: str,
    recommendations: list[dict],
    top_recommendation: dict,
    recommendation_factors: list[str],
) -> dict | None:
    """Describe how the AI Recommendation Score is produced."""
    barangays_evaluated = len(recommendations)

    if barangays_evaluated == 0:
        return None

    recommendation_score = float(top_recommendation.get("completion_probability", 0))
    confidence_level = top_recommendation.get(
        "confidence_level",
        get_confidence_label(recommendation_score),
    )

    return {
        "title": "How the AI Calculates the Recommendation",
        "barangay": barangay,
        "course_applied": course,
        "barangays_evaluated": barangays_evaluated,
        "recommendation_score": recommendation_score,
        "confidence_level": confidence_level,
        "recommendation_factors": recommendation_factors,
        "defense_summary": generate_ai_summary(
            course,
            barangay,
            recommendation_score,
            barangays_evaluated,
        ),
        "description": _build_recommendation_description(
            course,
            barangay,
            recommendation_score,
            barangays_evaluated,
        ),
    }


def _build_ai_decision_summary(
    historical_data: pd.DataFrame,
    course: str,
    barangay: str,
    completion_probability: float,
    confidence_level: str,
    recommendation_factors: list[str],
) -> dict:
    """AI Decision Summary metadata for the dashboard panel."""
    model_validation = get_model_validation_metrics()

    summary = {
        "model_used": MODEL_USED_LABEL,
        "dataset": DATASET_LABEL,
        "training_records": int(len(historical_data)),
        "barangays_evaluated": int(historical_data["barangay"].nunique()),
        "course_selected": course,
        "top_recommended_barangay": barangay,
        "prediction_confidence": completion_probability,
        "confidence_level": confidence_level,
        "recommendation_factors": recommendation_factors,
        "defense_summary": generate_ai_summary(
            course,
            barangay,
            completion_probability,
            int(historical_data["barangay"].nunique()),
        ),
    }

    if model_validation is not None:
        summary["model_validation"] = {
            "accuracy": model_validation.get("accuracy"),
            "precision": model_validation.get("precision"),
            "recall": model_validation.get("recall"),
            "f1_score": model_validation.get("f1_score"),
            "roc_auc": model_validation.get("roc_auc"),
            "confusion_matrix": model_validation.get("confusion_matrix"),
            "class_labels": model_validation.get("class_labels"),
        }

    return summary


def _build_evaluation_message(barangays_scored: int) -> str:
    if barangays_scored == 0:
        return (
            "The system evaluated all available barangays and ranked them by "
            "predicted completion probability."
        )

    return (
        f"{barangays_scored} barangays were evaluated by the Random Forest model "
        f"and ranked by predicted completion probability."
    )


def build_explainable_ai(
    applicant_profile: dict,
    recommendations: list[dict],
    historical_data: pd.DataFrame,
) -> dict | None:
    """Build Explainable AI output for the top recommended barangay."""
    if not recommendations:
        return None

    top_recommendation = recommendations[0]
    barangay = top_recommendation["barangay"]
    course = applicant_profile["course_applied"]
    completion_probability = top_recommendation["completion_probability"]
    confidence_level = top_recommendation.get(
        "confidence_level",
        get_confidence_label(completion_probability),
    )
    recommendation_factors = get_top_influencing_features(limit=5)

    course_records = historical_data[historical_data["course_applied"] == course]

    historical_completion_rate = _build_historical_completion_rate(
        course_records,
        barangay,
        course,
    )
    historical_dropout_rate = _build_historical_dropout_rate(
        course_records,
        barangay,
        course,
    )
    course_success_rate = _build_course_success_rate(
        course_records,
        barangay,
        course,
    )
    random_forest_evaluation = _build_random_forest_evaluation(
        barangay,
        course,
        recommendations,
        top_recommendation,
        recommendation_factors,
    )
    ai_decision_summary = _build_ai_decision_summary(
        historical_data,
        course,
        barangay,
        completion_probability,
        confidence_level,
        recommendation_factors,
    )

    recommendation_reason = {
        "barangay": barangay,
        "course_applied": course,
        "historical_completion_rate": historical_completion_rate,
        "historical_dropout_rate": historical_dropout_rate,
        "course_success_rate": course_success_rate,
        "random_forest_evaluation": random_forest_evaluation,
        "prediction_confidence": completion_probability,
        "confidence_level": confidence_level,
        "recommendation_factors": recommendation_factors,
        "defense_summary": generate_ai_summary(
            course,
            barangay,
            completion_probability,
            len(recommendations),
        ),
    }

    if (
        historical_completion_rate is None
        and historical_dropout_rate is None
        and course_success_rate is None
        and random_forest_evaluation is None
    ):
        return None

    return {
        "recommendation_reason": recommendation_reason,
        "ai_decision_summary": ai_decision_summary,
        "evaluation_message": _build_evaluation_message(len(recommendations)),
    }


def build_recommendation_reason(
    applicant_profile: dict,
    recommendations: list[dict],
    historical_data: pd.DataFrame,
) -> dict | None:
    """Return Explainable AI payload for the completion API response."""
    return build_explainable_ai(applicant_profile, recommendations, historical_data)
