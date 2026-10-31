"""
Notification service — in-app notifications and optional email delivery.
SMTP email is only enabled when SMTP_* environment variables are configured.
Fails silently with a log line when not configured.
"""
import os
import smtplib
import logging
from datetime import datetime, timezone
from typing import List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from models.notification import Notification
from models.user import User
from models.organization import Organization
from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM, SMTP_TLS
)

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    """Check if SMTP is fully configured."""
    return all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM])


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send an email via SMTP.
    Returns True on success, False on failure (logs error).
    Fails silently if SMTP is not configured.
    """
    if not _smtp_configured():
        logger.debug("SMTP not configured; skipping email send.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send email to {to_email}: {e}")
        return False


def create_notification(
    db: Session,
    title: str,
    message: str,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    send_email_now: bool = False
) -> Notification:
    """
    Create an in-app notification.
    Optionally send email if SMTP is configured and target has email.
    """
    notif = Notification(
        user_id=user_id,
        organization_id=organization_id,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notif)
    db.flush()

    # Send email if requested and SMTP configured
    if send_email_now and _smtp_configured():
        target_email = None
        if user_id:
            user = db.get(User, user_id)
            if user:
                # Users don't have email field yet; could add to model
                pass
        elif organization_id:
            org = db.get(Organization, organization_id)
            if org and org.contact_number:
                # Could parse email from contact or add email field
                pass

        if target_email:
            send_email(target_email, title, message)

    return notif


def get_notifications_for_user(
    db: Session,
    user_id: int,
    organization_id: Optional[int] = None,
    unread_only: bool = False,
    limit: int = 50
) -> List[Notification]:
    """Get notifications for a user (personal + organization-level)."""
    q = db.query(Notification).filter(
        (Notification.user_id == user_id) |
        (Notification.organization_id == organization_id)
    )
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa
    return q.order_by(Notification.created_at.desc()).limit(limit).all()


def get_unread_count(
    db: Session,
    user_id: int,
    organization_id: Optional[int] = None
) -> int:
    """Get count of unread notifications for user."""
    return db.query(Notification).filter(
        (Notification.user_id == user_id) |
        (Notification.organization_id == organization_id),
        Notification.is_read == False  # noqa
    ).count()


def mark_as_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a notification as read (only if owned by user or user's org)."""
    notif = db.get(Notification, notification_id)
    if not notif:
        return False
    if notif.user_id != user_id and notif.organization_id != user_id:
        # Check if user's org matches
        user = db.get(User, user_id)
        if not user or notif.organization_id != user.organization_id:
            return False
    notif.is_read = True
    return True


def mark_all_as_read(db: Session, user_id: int, organization_id: Optional[int] = None) -> int:
    """Mark all notifications as read for user/org."""
    q = db.query(Notification).filter(
        (Notification.user_id == user_id) |
        (Notification.organization_id == organization_id),
        Notification.is_read == False  # noqa
    )
    count = q.count()
    q.update({Notification.is_read: True})
    return count


def notify_escalation(
    db: Session,
    request_id: int,
    blood_bank_ids: List[int],
    user_id: Optional[int] = None
) -> int:
    """
    Create escalation notifications for blood banks.
    Returns number of notifications created.
    """
    from models.emergency_request import EmergencyRequest
    req = db.get(EmergencyRequest, request_id)
    if not req:
        return 0

    count = 0
    for bank_id in blood_bank_ids:
        notif = Notification(
            organization_id=bank_id,
            title=f"🚨 ESCALATED: {req.urgency.title()} Request Overdue",
            message=(
                f"Emergency request {req.reference} ({req.blood_group} "
                f"{req.component}, {req.units_requested} units) from "
                f"{req.hospital.name if req.hospital else 'Unknown Hospital'} "
                f"has exceeded its SLA. Please review and respond urgently."
            ),
            is_read=False,
        )
        db.add(notif)
        count += 1

    if count > 0:
        db.flush()

    return count