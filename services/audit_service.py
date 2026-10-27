"""Audit service — record significant system events."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.audit_log import AuditLog
import logging

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    action: str,
    user_id: int = None,
    entity_type: str = None,
    entity_id: int = None,
    details: str = None
):
    """
    Write an audit log entry.
    This should be called within the same transaction as the action.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        # Don't flush here — let the caller's transaction handle it
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")


def get_recent_logs(db: Session, limit: int = 100):
    """Fetch recent audit logs ordered by newest first."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
