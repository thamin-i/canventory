"""Background service for checking expiring items and sending notifications."""

import logging
import typing as t
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from sqlalchemy import select

from app.core.config import SETTINGS
from app.core.database import ASYNC_SESSION_MAKER
from app.core.models import ExpirationStatus, FoodItem
from app.services.email_notifications import (
    send_expiration_emails_to_all_subscribers,
)

LOGGER = logging.getLogger(__name__)


async def get_expiring_items() -> t.Dict[str, t.Any]:
    """Get all items that are expiring or expired.

    Returns:
        Dict[str, Any]:
            A dictionary containing lists of expiring items
            categorized by their expiration status.
    """
    async with ASYNC_SESSION_MAKER() as session:
        items: t.Sequence[FoodItem] = (
            (await session.execute(select(FoodItem))).scalars().all()
        )
        expired: t.List[t.Dict[str, t.Any]] = []
        critical: t.List[t.Dict[str, t.Any]] = []
        warning: t.List[t.Dict[str, t.Any]] = []

        for item in items:
            status: ExpirationStatus = item.get_expiration_status(
                SETTINGS.expiration_warning_days,
                SETTINGS.expiration_critical_days,
            )

            item_info: t.Dict[str, t.Any] = {
                "id": item.id,
                "name": item.name,
                "quantity": item.quantity,
                "category": item.category,
                "expiration_date": item.expiration_date.isoformat(),
            }

            match status:
                case ExpirationStatus.EXPIRED:
                    expired.append(item_info)
                case ExpirationStatus.CRITICAL:
                    critical.append(item_info)
                case ExpirationStatus.WARNING:
                    warning.append(item_info)

        return {
            "expired": expired,
            "critical": critical,
            "warning": warning,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


async def send_email_notification(
    subject: str,
    body: str,
    to_email: str,
) -> bool:
    """Send email notification (if SMTP is configured).

    Args:
        subject (str): The email subject.
        body (str): The email body.
        to_email (str): The recipient email address.

    Returns:
        bool: True if email was sent, False otherwise.
    """
    if not SETTINGS.smtp_enabled:
        LOGGER.debug("SMTP not enabled, skipping email notification")
        return False

    message: MIMEMultipart = MIMEMultipart()
    message["From"] = SETTINGS.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    await aiosmtplib.send(
        message,
        hostname=SETTINGS.smtp_host,
        port=SETTINGS.smtp_port,
        sender=SETTINGS.smtp_from_email if SETTINGS.smtp_from_email else None,
        recipients=[to_email],
        username=SETTINGS.smtp_user if SETTINGS.smtp_user else None,
        password=SETTINGS.smtp_password if SETTINGS.smtp_password else None,
        start_tls=SETTINGS.smtp_port == 587,
        use_tls=SETTINGS.smtp_port == 465,
        timeout=10,
    )
    LOGGER.info("Email notification sent to %s", to_email)
    return True


def format_expiration_report(expiring_data: t.Dict[str, t.Any]) -> str:
    """Format expiration data into a readable report.

    Args:
        expiring_data (Dict[str, Any]): The expiring items data.

    Returns:
        str: The formatted expiration report.
    """
    lines: t.List[str] = [
        "=" * 50,
        "CANVENTORY EXPIRATION REPORT",
        f"Generated: {expiring_data['checked_at']}",
        "=" * 50,
        "",
    ]

    if expiring_data["expired"]:
        lines.append("🚨 EXPIRED ITEMS:")
        lines.append("-" * 30)
        for item in expiring_data["expired"]:
            lines.append(
                f"  • {item['name']} (x{item['quantity']}) - "
                f"Expired: {item['expiration_date']}"
            )
        lines.append("")

    if expiring_data["critical"]:
        lines.append(
            "⚠️ CRITICAL - Expiring within "
            f"{SETTINGS.expiration_critical_days} days:"
        )
        lines.append("-" * 30)
        for item in expiring_data["critical"]:
            lines.append(
                f"  • {item['name']} (x{item['quantity']}) - "
                f"Expires: {item['expiration_date']}"
            )
        lines.append("")

    if expiring_data["warning"]:
        lines.append(
            "📋 WARNING - Expiring within "
            f"{SETTINGS.expiration_warning_days} days:"
        )
        lines.append("-" * 30)
        for item in expiring_data["warning"]:
            lines.append(
                f"  • {item['name']} (x{item['quantity']}) - "
                f"Expires: {item['expiration_date']}"
            )
        lines.append("")

    if not any(
        [
            expiring_data["expired"],
            expiring_data["critical"],
            expiring_data["warning"],
        ]
    ):
        lines.append("✅ All items are fresh! No expiration alerts.")

    return "\n".join(lines)


async def check_expiring_items_task() -> None:
    """Background task to check for expiring items and send notifications."""
    LOGGER.info("Running expiration check...")

    try:
        expiring_data: t.Dict[str, t.Any] = await get_expiring_items()
        report: str = format_expiration_report(expiring_data)

        LOGGER.info("\n%s", report)

        has_alerts: bool = any(
            [
                expiring_data["expired"],
                expiring_data["critical"],
                expiring_data["warning"],
            ]
        )

        if has_alerts:
            if SETTINGS.smtp_enabled:
                email_count: int = (
                    await send_expiration_emails_to_all_subscribers(
                        expiring_data
                    )
                )
                if email_count > 0:
                    LOGGER.info("Sent %d expiration alert emails", email_count)

    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Error in expiration check task")
