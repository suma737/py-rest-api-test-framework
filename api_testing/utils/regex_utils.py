import re

# Name patterns
NAME_PATTERN = r"^[A-Za-z\s'-]{2,}$"  # At least 2 characters, letters, spaces, apostrophes, or hyphens

# Numeric patterns
INTEGER_PATTERN = r"^-?\d+$"  # Integer with optional negative sign
FLOAT_PATTERN = r"^-?\d+(\.\d+)?$"  # Float with optional negative sign

# Date patterns
DATE_MM_DD_YY = r"^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{2}$"  # MM/DD/YY format
DATE_YYYY_MM_DD = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"  # YYYY-MM-DD format

# Time patterns
TIME_24HOUR = r"^(?:[01]\d|2[0-3]):[0-5]\d$"  # 24-hour format
TIME_12HOUR = r"^(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM|am|pm)$"  # 12-hour format

# Email pattern
EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}$"

# UUID pattern
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# Phone number patterns
PHONE_US = r"^(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}$"  # US phone number format

# URL pattern
URL_PATTERN = r"^(?:http(s)?:\\/\\/)?[\w.-]+(?:\\/[\w.-]*)*\\/?$"

# IP address patterns
IPV4_PATTERN = r"^(?:\d{1,3}\.){3}\d{1,3}$"  # IPv4 format
IPV6_PATTERN = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"  # IPv6 format

# Credit card pattern
CREDIT_CARD_PATTERN = r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\\d{3})\\d{11})$"

# Common patterns
ALPHA_PATTERN = r"^[A-Za-z]+$"  # Only letters
ALPHANUMERIC_PATTERN = r"^[A-Za-z0-9]+$"  # Letters and numbers
ALPHANUMERIC_SPECIAL_PATTERN = ALPHANUMERIC_PATTERN  # Fallback to avoid syntax error

# Pattern dictionary for easy access
PATTERNS = {
    'name': NAME_PATTERN,
    'integer': INTEGER_PATTERN,
    'float': FLOAT_PATTERN,
    'date_mm_dd_yy': DATE_MM_DD_YY,
    'date_yyyy_mm_dd': DATE_YYYY_MM_DD,
    'time_24hour': TIME_24HOUR,
    'time_12hour': TIME_12HOUR,
    'email': EMAIL_PATTERN,
    'uuid': UUID_PATTERN,
    'phone_us': PHONE_US,
    'url': URL_PATTERN,
    'ipv4': IPV4_PATTERN,
    'ipv6': IPV6_PATTERN,
    'credit_card': CREDIT_CARD_PATTERN,
    'alpha': ALPHA_PATTERN,
    'alphanumeric': ALPHANUMERIC_PATTERN,
    'alphanumeric_special': ALPHANUMERIC_SPECIAL_PATTERN
}


def validate_pattern(pattern_name: str, value: str) -> bool:
    """
    Validate a value against a named pattern

    Args:
        pattern_name: Name of the pattern (e.g., 'name', 'email')
        value: Value to validate

    Returns:
        bool: True if the value matches the pattern, False otherwise
    """
    if pattern_name not in PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")
    return bool(re.match(PATTERNS[pattern_name], value))


def validate_regex(pattern: str, value: str) -> bool:
    """
    Validate a value against a custom regex pattern

    Args:
        pattern: Custom regex pattern
        value: Value to validate

    Returns:
        bool: True if the value matches the pattern, False otherwise
    """
    return bool(re.match(pattern, value))
