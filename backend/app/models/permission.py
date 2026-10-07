import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.access import AccessLevel
from app.models.base import Base


def _enum_values(choices: type[Enum]) -> list[str]:
    return [item.value for item in choices]


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    access_level: Mapped[AccessLevel] = mapped_column(
        Enum(AccessLevel, name="access_level", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship(back_populates="permission")
