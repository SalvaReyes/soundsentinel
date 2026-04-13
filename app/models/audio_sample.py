from datetime import datetime
from datetime import timezone

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AudioSample(Base):
    __tablename__ = "audio_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestion_id: Mapped[int] = mapped_column(ForeignKey("audio_ingestions.id"), unique=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    duration_seconds: Mapped[float] = mapped_column(Float)
    sample_rate_hz: Mapped[int] = mapped_column(Integer)
    channel_count: Mapped[int] = mapped_column(Integer)
    rms_amplitude: Mapped[float] = mapped_column(Float)
    peak_amplitude: Mapped[float] = mapped_column(Float)
    normalized_rms: Mapped[float] = mapped_column(Float)
    normalized_peak: Mapped[float] = mapped_column(Float)

    device: Mapped["Device"] = relationship(back_populates="samples")
    ingestion: Mapped["AudioIngestion"] = relationship(back_populates="sample")
    alerts: Mapped[list["AlertEvent"]] = relationship(
        back_populates="sample",
        cascade="all, delete-orphan",
    )
