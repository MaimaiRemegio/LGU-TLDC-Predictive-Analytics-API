"""
Explainable AI (XAI) output for barangay recommendations.

Every numeric value is computed from historical_training.csv and the
Random Forest prediction response. Unsupported metrics are omitted.
"""

import pandas as pd

GRADUATE_LABEL = "Graduate"
MODEL_USED_LABEL = "Random Forest Classifier"
DATASET_LABEL = "Historical Training Dataset (Synthetic)"


def _count_graduates(records: pd.DataFrame) -> int:
    """Count rows where training_outcome equals Graduate."""
    if records.empty:
        return 0
    return int((records["training_outcome"] == GRADUATE_LABEL).sum())


def _completion_rate_percent(graduates: int, total_applicants: int) -> float | None:
    """
    Compute completion percentage.

    Formula: (graduates / total_applicants) * 100, rounded to one decimal.
    Returns None when there are no applicants to avoid division by zero.
    """
    if total_applicants == 0:
        return None
    return round((graduates / total_applicants) * 100, 1)


def _build_historical_completion_rate(
    historical_data: pd.DataFrame,
    barangay: str,
) -> dict | None:
    """
    Historical Completion Rate for the top recommended barangay.

    Dataset query: all rows in historical_training.csv where barangay matches.
    Graduates = count of training_outcome == Graduate.
    Total applicants = total row count for that barangay.
    """
    barangay_records = historical_data[historical_data["barangay"] == barangay]
    total_applicants = len(barangay_records)

    if total_applicants == 0:
        return None

    graduates = _count_graduates(barangay_records)
    completion_rate = _completion_rate_percent(graduates, total_applicants)

    if completion_rate is None:
        return None

    return {
        "title": "Historical Completion Rate",
        "completion_rate": completion_rate,
        "graduates": graduates,
        "total_applicants": total_applicants,
        "detail": f"({graduates} graduates out of {total_applicants} applicants)",
    }


def _build_course_success_rate(
    course_records: pd.DataFrame,
    barangay: str,
    course: str,
) -> dict | None:
    """
    Course Success Rate for the selected course in the top barangay.

    Dataset query: rows where barangay and course_applied both match.
    Graduates and totals are counted from those filtered records.
    """
    barangay_course_records = course_records[course_records["barangay"] == barangay]
    total_applicants = len(barangay_course_records)

    if total_applicants == 0:
        return None

    graduates = _count_graduates(barangay_course_records)

    return {
        "title": "Course Success Rate",
        "course_applied": course,
        "graduates": graduates,
        "total_applicants": total_applicants,
        "detail": (
            f"{graduates} of {total_applicants} {course} applicants successfully "
            f"completed training in {barangay}."
        ),
    }


def _build_random_forest_evaluation(
    barangay: str,
    course: str,
    recommendations: list[dict],
) -> dict | None:
    """
    Random Forest Evaluation narrative for the recommendation.

    barangays_evaluated = number of barangay classes returned by predict_proba(),
    which equals len(recommendations) from the ranked prediction output.
    """
    barangays_evaluated = len(recommendations)

    if barangays_evaluated == 0:
        return None

    return {
        "title": "Random Forest Evaluation",
        "barangays_evaluated": barangays_evaluated,
        "description": (
            f"The Random Forest model compared historical completion patterns of "
            f"{course} across all barangays. Multiple decision trees evaluated the "
            f"historical training records and ranked {barangay} as the barangay with "
            f"the highest predicted suitability score."
        ),
    }


def _build_ai_decision_summary(
    historical_data: pd.DataFrame,
    course: str,
    barangay: str,
    confidence: float,
    recommendations: list[dict],
) -> dict:
    """
    AI Decision Summary metadata for the dashboard panel.

    training_records = total rows in historical_training.csv.
    barangays_evaluated = unique barangay values present in the dataset.
    course_selected and top_recommended_barangay come from the current request
    and top prediction result.
    prediction_confidence = highest predict_proba score from the model (%).
    """
    return {
        "model_used": MODEL_USED_LABEL,
        "dataset": DATASET_LABEL,
        "training_records": int(len(historical_data)),
        "barangays_evaluated": int(historical_data["barangay"].nunique()),
        "course_selected": course,
        "top_recommended_barangay": barangay,
        "prediction_confidence": confidence,
    }


def _build_evaluation_message(barangays_scored: int) -> str:
    """
    Short evaluation line for the AI Recommendations list.

    Uses the number of barangays scored by predict_proba().
    """
    if barangays_scored == 0:
        return (
            "The system evaluated all available barangays and ranked them based on "
            "predicted training completion probability."
        )

    return (
        f"{barangays_scored} barangays were evaluated by the Random Forest "
        f"recommendation model."
    )


def build_explainable_ai(
    applicant_profile: dict,
    recommendations: list[dict],
    historical_data: pd.DataFrame,
) -> dict | None:
    """
    Build Explainable AI output for the top recommended barangay.

    All statistics correspond to the selected course and the highest-ranked
    barangay from the current Random Forest prediction.
    """
    if not recommendations:
        return None

    top_recommendation = recommendations[0]
    barangay = top_recommendation["barangay"]
    course = applicant_profile["course_applied"]
    confidence = top_recommendation["completion_probability"]

    course_records = historical_data[historical_data["course_applied"] == course]

    historical_completion_rate = _build_historical_completion_rate(
        historical_data,
        barangay,
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
    )
    ai_decision_summary = _build_ai_decision_summary(
        historical_data,
        course,
        barangay,
        confidence,
        recommendations,
    )

    recommendation_reason = {
        "barangay": barangay,
        "course_applied": course,
        "historical_completion_rate": historical_completion_rate,
        "course_success_rate": course_success_rate,
        "random_forest_evaluation": random_forest_evaluation,
        "prediction_confidence": confidence,
    }

    if (
        historical_completion_rate is None
        and course_success_rate is None
        and random_forest_evaluation is None
    ):
        return None

    return {
        "recommendation_reason": recommendation_reason,
        "ai_decision_summary": ai_decision_summary,
        "evaluation_message": _build_evaluation_message(len(recommendations)),
    }


# Backward-compatible alias used by the completion route.
def build_recommendation_reason(
    applicant_profile: dict,
    recommendations: list[dict],
    historical_data: pd.DataFrame,
) -> dict | None:
    """Return Explainable AI payload for the completion API response."""
    return build_explainable_ai(applicant_profile, recommendations, historical_data)
