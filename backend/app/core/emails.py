import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str | None) -> str | None:
    """Trim + lowercase. Used for every invitation/membership email comparison."""
    if email is None:
        return None
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(_EMAIL_RE.match(email))
