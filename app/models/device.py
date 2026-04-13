from datetime import datetime
from datetime import timezone

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    ingestions: Mapped[list["AudioIngestion"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    samples: Mapped[list["AudioSample"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["AlertEvent"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
