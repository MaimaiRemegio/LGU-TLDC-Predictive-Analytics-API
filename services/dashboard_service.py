from services.applicant_data_repository import get_applicant_data_repository
from services.applicant_forecast_service import get_applicant_forecast_service
from services.completion_predictor import recommend_barangays


class DashboardService:

    def __init__(self):
        self.forecast = get_applicant_forecast_service()
        self.applicants = get_applicant_data_repository()

    def _extract_next_month_forecast(self, forecast_result) -> float:
        """Extract the first monthly forecast value from the forecast service response."""
        if isinstance(forecast_result, dict):
            forecast_values = forecast_result.get("forecast", [])
            if not forecast_values:
                raise ValueError("Forecast service returned no forecast values.")
            return forecast_values[0]

        if isinstance(forecast_result, list):
            if not forecast_result:
                raise ValueError("Forecast service returned an empty forecast list.")
            return forecast_result[0]

        raise ValueError("Unsupported forecast response format.")

    def get_summary(self):

        applicant_profile = self.applicants.get_applicant_profile_for_course("Cookery NC II")
        ranking = recommend_barangays(applicant_profile)

        best = ranking[0]
        top3 = ranking[:3]

        forecast_result = self.forecast.forecast_tldc_total("next_month")
        forecast_next_month = forecast_result["monthly_forecast"][0]

        insights = [
            f"{best['barangay']} has the highest predicted suitability ({best['completion_probability']}%).",
            f"Expected applicants next month: {forecast_next_month}.",
            f"{len([b for b in ranking if b['completion_probability'] >= 10])} barangays have suitability probabilities above 10%.",
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
