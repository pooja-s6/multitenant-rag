from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardSummary
from app.services.analytics.summary import summarize

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> DashboardSummary:
    return summarize(db, current)
