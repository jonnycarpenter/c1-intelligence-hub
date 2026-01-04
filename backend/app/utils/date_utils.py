"""Date utility functions."""

from datetime import datetime, timedelta
from typing import Optional, Tuple


def get_date_range(
    days: Optional[int] = 14,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Tuple[datetime, datetime]:
    """
    Calculate date range for filtering.
    
    Args:
        days: Number of days to look back (default 14)
        date_from: Start date in YYYY-MM-DD format (overrides days)
        date_to: End date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Tuple of (start_date, end_date) as datetime objects
    """
    end_date = datetime.now()
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            pass
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            start_date = end_date - timedelta(days=days or 14)
    else:
        start_date = end_date - timedelta(days=days or 14)
    
    return start_date, end_date


def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    Parse various date string formats.
    
    Args:
        date_str: Date string in various formats
    
    Returns:
        datetime object or None if parsing fails
    """
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def format_date_for_display(dt: datetime) -> str:
    """Format datetime for user display."""
    return dt.strftime("%B %d, %Y")


def format_date_for_api(dt: datetime) -> str:
    """Format datetime for API requests."""
    return dt.strftime("%Y-%m-%d")
