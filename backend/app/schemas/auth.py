from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.role import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    tenant_id: UUID
    role: Role
    email: EmailStr
    department: str | None = None
