"""Date utilities."""

from datetime import datetime, timezone


def calculate_days_until_expiration(expiration_date: datetime) -> int:
    """Calculate the number of days until the expiration date.

    Args:
        expiration_date (datetime):
            The expiration date to calculate against.

    Returns:
        int: The number of days until the expiration date.
    """
    now: datetime = datetime.now(timezone.utc)
    exp_date: datetime = expiration_date
    if exp_date.tzinfo is None:
        exp_date = exp_date.replace(tzinfo=timezone.utc)
    return (exp_date - now).days
