"""
Test that future date validation works correctly in the orchestrator.
"""
from datetime import datetime, timedelta

# Simulate the validation logic from orchestrator
def validate_exa_date(api_date: str) -> datetime | None:
    """
    Validate date from Exa API, rejecting future dates.
    Returns None if date is invalid/future.
    """
    max_future_days = 2  # Allow small buffer for timezone differences
    published_at = None
    
    if api_date:
        try:
            if isinstance(api_date, str):
                # Handle ISO format: "2025-01-15T00:00:00.000Z"
                published_at = datetime.fromisoformat(api_date.replace('Z', '+00:00'))
            else:
                published_at = api_date
            
            # Validate: reject future dates
            if published_at:
                # Make naive for comparison
                if hasattr(published_at, 'tzinfo') and published_at.tzinfo is not None:
                    check_date = published_at.replace(tzinfo=None)
                else:
                    check_date = published_at
                max_valid_date = datetime.utcnow() + timedelta(days=max_future_days)
                if check_date > max_valid_date:
                    print(f"REJECTED future date: {published_at}")
                    return None
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    
    return published_at


def test_future_dates():
    """Test various date scenarios."""
    print("Testing future date validation...")
    print("="*60)
    
    test_cases = [
        # (input, expected_result_description)
        ("2024-11-29T00:00:00.000Z", "PASS - past date"),
        ("2025-01-01T00:00:00.000Z", "PASS - recent past"),
        (datetime.utcnow().isoformat() + "Z", "PASS - today"),
        ((datetime.utcnow() + timedelta(days=1)).isoformat() + "Z", "PASS - tomorrow"),
        ("2026-05-13T19:02:00.000Z", "REJECT - far future (May 2026)"),
        ("2026-09-11T00:00:00.000Z", "REJECT - far future (Sep 2026)"),
        ("2027-01-01T00:00:00.000Z", "REJECT - 2027"),
    ]
    
    for api_date, description in test_cases:
        result = validate_exa_date(api_date)
        status = "✓ OK" if result else "✗ REJECTED"
        print(f"{status}: {description}")
        print(f"   Input: {api_date}")
        print(f"   Result: {result}")
        print()


if __name__ == "__main__":
    test_future_dates()
    
    print("\n" + "="*60)
    print("Validating actual Exa dates from earlier test...")
    
    # These are actual dates Exa returned for market research pages
    exa_dates = [
        "2026-05-13T19:02:00.000Z",  # US aerospace composites market
        "2024-11-29T00:00:00.000Z",  # Global aerospace composites (valid)
    ]
    
    for date in exa_dates:
        result = validate_exa_date(date)
        print(f"Exa date {date} -> {result}")
