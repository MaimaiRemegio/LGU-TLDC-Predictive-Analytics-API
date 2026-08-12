from services.applicant_data_repository import get_applicant_data_repository
from services.forecasting_service import get_forecasting_service
from services.completion_predictor import recommend_barangays


class DashboardService:

    def __init__(self):
        # Use ForecastingService — the single source of truth for forecasts.
        self.forecast = get_forecasting_service()
        self.applicants = get_applicant_data_repository()

    def get_summary(self):

        applicant_profile = self.applicants.get_applicant_profile_for_course("Cookery NC II")
        ranking = recommend_barangays(applicant_profile)

        best = ranking[0]
        top3 = ranking[:3]

        # ForecastingService._sum_forecast(1) returns the TLDC-wide next-month total.
        forecast_next_month = self.forecast._sum_forecast(1)

        insights = [
            f"{best['barangay']} has the highest predicted completion probability ({best['completion_probability']}%).",
            f"Expected applicants next month: {forecast_next_month}.",
            f"{len([b for b in ranking if b['completion_probability'] >= 80])} barangays have predicted completion probabilities above 80%.",
            f"Recommended priority areas: {', '.join([b['barangay'] for b in top3])}."
        ]

        return {
            "best_barangay": best["barangay"],
            "completion_probability": best["completion_probability"],
            "forecast_next_month": forecast_next_month,
            "top_barangays": ranking[:5],
            "ai_status": "Online",
            "insights": insights,
        }


dashboard_service = DashboardService()


def get_dashboard_service():
    return dashboard_service
