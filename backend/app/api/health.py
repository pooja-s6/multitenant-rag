from fastapi import APIRouter, Response, status

from app.schemas.health import LiveResponse, ReadyResponse
from app.services import health as health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return health_service.liveness()


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response) -> ReadyResponse:
    result = health_service.readiness()
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
