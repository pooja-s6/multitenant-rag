from fastapi import APIRouter

from app.api.errors import not_ready

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query")
def query() -> None:
    raise not_ready("RAG", "phase 5")
