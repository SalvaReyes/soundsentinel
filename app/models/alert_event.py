from datetime import datetime
from datetime import timezone

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("audio_samples.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(255))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    metric_value: Mapped[float] = mapped_column(Float)
    threshold_value: Mapped[float] = mapped_column(Float)
    window_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="open")

    device: Mapped["Device"] = relationship(back_populates="alerts")
    sample: Mapped["AudioSample"] = relationship(back_populates="alerts")
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
    )
