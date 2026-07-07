from fastapi import APIRouter

from services.dashboard_service import get_dashboard_service

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/summary")
def dashboard_summary():

    service = get_dashboard_service()

    return service.get_summary()