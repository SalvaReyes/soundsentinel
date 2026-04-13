from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db.session import check_database_connection


def get_liveness_status() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version,
    }


def get_readiness_status() -> dict:
    settings = get_settings()
    try:
        check_database_connection()
        database_status = "ok"
        status = "ready"
    except SQLAlchemyError:
        database_status = "unavailable"
        status = "degraded"

    return {
        "status": status,
        "service": settings.app_name,
        "database": database_status,
    }

