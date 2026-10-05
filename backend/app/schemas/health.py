from typing import Literal

from pydantic import BaseModel


class DependencyCheck(BaseModel):
    ok: bool
    detail: str


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, DependencyCheck]
