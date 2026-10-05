from fastapi import APIRouter

from app.api.errors import not_ready

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary() -> None:
    raise not_ready("Dashboard metrics", "phase 8")
