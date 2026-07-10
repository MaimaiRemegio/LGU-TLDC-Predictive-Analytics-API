from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import dashboard
from routes import applicant_forecast, completion
from services.applicant_data_repository import get_applicant_data_repository
from services.applicant_forecast_service import get_applicant_forecast_service
from services.completion_predictor import get_completion_predictor


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_completion_predictor()
    get_applicant_forecast_service()
    get_applicant_data_repository()
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