from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import logging

from sqlalchemy import delete

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.alert_event import AlertEvent
from app.models.audio_ingestion import AudioIngestion
from app.models.audio_sample import AudioSample
from app.models.notification_delivery import NotificationDelivery

logger = logging.getLogger(__name__)


def run_cleanup() -> None:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.data_retention_days)

    with SessionLocal() as session:
        deliveries_deleted = session.execute(
            delete(NotificationDelivery).where(NotificationDelivery.created_at < cutoff)
        ).rowcount
        alerts_deleted = session.execute(
            delete(AlertEvent).where(AlertEvent.triggered_at < cutoff)
        ).rowcount
        samples_deleted = session.execute(
            delete(AudioSample).where(AudioSample.measured_at < cutoff)
        ).rowcount
        ingestions_deleted = session.execute(
            delete(AudioIngestion).where(AudioIngestion.received_at < cutoff)
        ).rowcount

        session.commit()

    logger.info(
        "Cleanup complete. Deliveries=%s Alerts=%s Samples=%s Ingestions=%s Cutoff=%s",
        deliveries_deleted,
        alerts_deleted,
        samples_deleted,
        ingestions_deleted,
        cutoff.isoformat(),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cleanup()
