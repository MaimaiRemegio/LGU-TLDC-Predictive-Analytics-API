from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import dashboard
from routes import applicant_forecast, completion, forecasting
from services.applicant_data_repository import get_applicant_data_repository
from services.completion_predictor import get_completion_predictor
from services.forecasting_service import get_forecasting_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Single forecasting pipeline warm-up.
    # ForecastingService fits all ARIMA models and is shared by every
    # forecast endpoint including POST /predict/applicant-volume.
    get_completion_predictor()
    get_applicant_data_repository()
    get_forecasting_service()
    yield

app = FastAPI(
    title="LGU-TLDC Predictive Analytics API",
    description=(
        "AI Prediction API for LGU-TLDC. Includes AI-powered barangay recommendation "
        "and applicant volume forecasting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(completion.router)
app.include_router(applicant_forecast.router)
app.include_router(forecasting.router)
app.include_router(dashboard.router)

@app.get("/")
def home():
    return {
        "status": "running",
        "service": "LGU-TLDC Predictive Analytics API",
        "message": "LGU-TLDC Predictive Analytics API is running.",
        "version": "1.0.0",
        "model": "Random Forest",
        "deployment": "Vercel"
    }