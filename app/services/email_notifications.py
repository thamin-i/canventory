"""Email notification service for sending expiration alerts."""

import logging
import typing as t
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import SETTINGS
from app.core.database import ASYNC_SESSION_MAKER
from app.core.models import HomeMembership, User

LOGGER = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
EMAIL_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> bool:
    """Send an email to a single recipient.

    Args:
        to_email (str): Recipient email address.
        subject (str): Email subject.
        body (str): Plain text email body.
        html_body (str | None): Optional HTML email body.

    Returns:
        bool: True if email was sent successfully, False otherwise.
    """
    if not SETTINGS.smtp_enabled:
        LOGGER.debug("SMTP not enabled, skipping email")
        return False

    if not to_email:
        LOGGER.warning("No recipient email provided")
        return False

    try:
        message: MIMEMultipart = MIMEMultipart("alternative")
        message["From"] = SETTINGS.smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))

        if html_body is not None:
            message.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            message,
            hostname=SETTINGS.smtp_host,
            port=SETTINGS.smtp_port,
            username=SETTINGS.smtp_user if SETTINGS.smtp_user else None,
            password=SETTINGS.smtp_password if SETTINGS.smtp_password else None,
            use_tls=SETTINGS.smtp_port == 465,
            start_tls=SETTINGS.smtp_port == 587,
            timeout=10,
        )
        LOGGER.info("Email sent to %s", to_email)
        return True

    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Failed to send email to %s", to_email)
        return False


def render_template(template_name: str, **context: t.Any) -> str:
    """Render a Jinja2 email template with the given context.

    Args:
        template_name (str): The name of the template file.
        **context: Context variables for rendering the template.

    Returns:
        str: The rendered template as a string.
    """
    return EMAIL_ENV.get_template(template_name).render(**context)


def format_expiration_html_email(
    expiring_data: t.Dict[str, t.Any],
    username: str,
    home_name: str | None = None,
) -> str:
    """Format expiration data into an HTML email.

    Args:
        expiring_data (t.Dict[str, t.Any]):
            Expiration data categorized by severity.
        username (str):
            The username of the recipient.
        home_name (str | None):
            The name of the home (optional).

    Returns:
        str: The rendered HTML email as a string.
    """
    return render_template(
        "emails/expiration_alert.html",
        username=username,
        home_name=home_name,
        expired=expiring_data.get("expired", []),
        critical=expiring_data.get("critical", []),
        warning=expiring_data.get("warning", []),
        critical_days=SETTINGS.expiration_critical_days,
        warning_days=SETTINGS.expiration_warning_days,
        app_url=SETTINGS.app_url,
    )


def format_expiration_text_email(
    expiring_data: t.Dict[str, t.Any],
    username: str,
    home_name: str | None = None,
) -> str:
    """Format expiration data into a plain text email.

    Args:
        expiring_data (t.Dict[str, t.Any]):
            Expiration data categorized by severity.
        username (str):
            The username of the recipient.
        home_name (str | None):
            The name of the home (optional).

    Returns:
        str: The rendered plain text email as a string.
    """
    return render_template(
        "emails/expiration_alert.txt",
        username=username,
        home_name=home_name,
        expired=expiring_data.get("expired", []),
        critical=expiring_data.get("critical", []),
        warning=expiring_data.get("warning", []),
        critical_days=SETTINGS.expiration_critical_days,
        warning_days=SETTINGS.expiration_warning_days,
        app_url=SETTINGS.app_url,
    )


async def get_users_with_email_notifications() -> t.List[User]:
    """Get all users who have email notifications enabled.

    Returns:
        t.List[User]: List of users with email notifications enabled.
    """
    async with ASYNC_SESSION_MAKER() as session:
        users: t.Sequence[User] = (
            (
                await session.execute(
                    select(User).where(
                        User.email_notifications_enabled.is_(True),
                        User.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(users)


async def get_home_members_with_email_notifications(
    home_id: int,
) -> t.List[User]:
    """Get all members of a home who have email notifications enabled.

    Args:
        home_id (int): The ID of the home.

    Returns:
        t.List[User]: List of users with email notifications enabled.
    """
    async with ASYNC_SESSION_MAKER() as session:
        memberships: t.Sequence[HomeMembership] = (
            (
                await session.execute(
                    select(HomeMembership)
                    .options(selectinload(HomeMembership.user))
                    .where(HomeMembership.home_id == home_id)
                )
            )
            .scalars()
            .all()
        )

        return [
            m.user
            for m in memberships
            if m.user.email_notifications_enabled and m.user.is_active
        ]


async def send_expiration_email_to_user(
    user: User,
    expiring_data: t.Dict[str, t.Any],
    home_name: str | None = None,
) -> bool:
    """Send expiration alert email to a specific user.

    Args:
        user (User):
            The user to send the email to.
        expiring_data (t.Dict[str, t.Any]):
            Expiration data categorized by severity.
        home_name (str | None):
            The name of the home for the email context.

    Returns:
        bool: True if email was sent, False otherwise.
    """
    if not user.email_notifications_enabled:
        return False

    if not user.email:
        LOGGER.warning("User %s has no email address", user.username)
        return False

    has_alerts: bool = any(
        [
            expiring_data.get("expired", []),
            expiring_data.get("critical", []),
            expiring_data.get("warning", []),
        ]
    )

    if not has_alerts:
        return False

    # Determine subject based on severity
    home_suffix = f" - {home_name}" if home_name else ""
    subject: str = f"📋 [Canventory] Expiration reminder{home_suffix}"
    if expiring_data.get("expired"):
        subject = f"⚠️ [Canventory] Items have expired!{home_suffix}"
    elif expiring_data.get("critical"):
        subject = f"🚨 [Canventory] Items expiring soon!{home_suffix}"

    text_body: str = format_expiration_text_email(
        expiring_data, user.username, home_name
    )
    html_body: str = format_expiration_html_email(
        expiring_data, user.username, home_name
    )

    return await send_email(
        to_email=user.email,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )


async def send_expiration_emails_to_home_members(
    home_id: int,
    expiring_data: t.Dict[str, t.Any],
) -> int:
    """Send expiration emails to all members
        of a home with notifications enabled.

    Args:
        home_id (int): The ID of the home.
        expiring_data (t.Dict[str, t.Any]):
            Expiration data categorized by severity.

    Returns:
        int: Number of emails sent.
    """
    if not SETTINGS.smtp_enabled:
        LOGGER.debug("SMTP not enabled, skipping email notifications")
        return 0

    users: t.List[User] = await get_home_members_with_email_notifications(
        home_id
    )
    home_name: str = expiring_data.get("home_name", f"Home {home_id}")
    sent_count: int = 0

    for user in users:
        if await send_expiration_email_to_user(user, expiring_data, home_name):
            sent_count += 1

    if sent_count > 0:
        LOGGER.info(
            "Sent expiration emails to %d members of home '%s'",
            sent_count,
            home_name,
        )

    return sent_count


async def send_expiration_emails_to_all_subscribers(
    expiring_data: t.Dict[str, t.Any],
) -> int:
    """Send expiration emails to all users with email notifications enabled.

    This is a legacy function kept for backward compatibility.

    Args:
        expiring_data (t.Dict[str, t.Any]):
            Expiration data categorized by severity.

    Returns:
        int: Number of emails sent.
    """
    if not SETTINGS.smtp_enabled:
        LOGGER.debug("SMTP not enabled, skipping email notifications")
        return 0

    users: t.List[User] = await get_users_with_email_notifications()
    sent_count: int = 0

    for user in users:
        if await send_expiration_email_to_user(user, expiring_data):
            sent_count += 1

    if sent_count > 0:
        LOGGER.info("Sent expiration emails to %d users", sent_count)

    return sent_count


async def send_test_email(user: User) -> bool:
    """Send a test email to verify email notifications are working.

    Args:
        user (User):
            The user to send the test email to.

    Returns:
        bool: True if email was sent successfully, False otherwise.
    """
    if not user.email:
        return False

    subject: str = "✅ [Canventory] Test Email"
    text_body: str = render_template(
        "emails/test_email.txt",
        username=user.username,
        app_url=SETTINGS.app_url,
    )
    html_body: str = render_template(
        "emails/test_email.html",
        username=user.username,
        app_url=SETTINGS.app_url,
    )

    return await send_email(
        to_email=user.email,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )
