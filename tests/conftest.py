import os

import pytest
from fastapi.testclient import TestClient

os.environ["SOUNDSENTINEL_DATABASE_URL_OVERRIDE"] = "sqlite+pysqlite:///./test_soundsentinel.db"
os.environ["SOUNDSENTINEL_ALERT_COOLDOWN_SECONDS"] = "0"
os.environ["SOUNDSENTINEL_TELEGRAM_BOT_TOKEN"] = ""
os.environ["SOUNDSENTINEL_TELEGRAM_CHAT_ID"] = ""

from app.db.session import SessionLocal
from app.db.session import initialize_database
from app.main import app
from app.models.alert_event import AlertEvent
from app.models.audio_ingestion import AudioIngestion
from app.models.audio_sample import AudioSample
from app.models.device import Device
from app.models.notification_delivery import NotificationDelivery

initialize_database()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_database() -> None:
    with SessionLocal() as session:
        session.query(NotificationDelivery).delete()
        session.query(AlertEvent).delete()
        session.query(AudioSample).delete()
        session.query(AudioIngestion).delete()
        session.query(Device).delete()
        session.commit()
