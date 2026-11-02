import csv
import io
import re

REQUIRED_FIELDS = ("name", "email")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def validate_user_row(row):
    """Return (cleaned_user, errors) for a single CSV row dict."""
    errors = []
    cleaned = {}

    for key, value in row.items():
        if key is None:
            continue
        cleaned[key.strip().lower()] = (value or "").strip()

    if None in row:
        errors.append("too many fields in row")

    for field in REQUIRED_FIELDS:
        if not cleaned.get(field):
            errors.append(f"missing required field: {field}")

    email = cleaned.get("email", "")
    if email and not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email}")

    age = cleaned.get("age", "")
    if age:
        if not age.isdigit():
            errors.append(f"invalid age: {age}")
        else:
            age_value = int(age)
            if age_value < 0 or age_value > 150:
                errors.append(f"age out of range: {age_value}")
            else:
                cleaned["age"] = age_value

    return cleaned, errors


def import_users_csv(text):
    """
    Parse CSV text and validate each user row.

    Returns (valid_users, errors) where:
      - valid_users is a list of cleaned user dicts
      - errors is a dict mapping row number (1-based data row, header excluded)
        to a list of error messages
    """
    valid_users = []
    errors = {}

    if text is None or not text.strip():
        errors[0] = ["empty CSV input"]
        return valid_users, errors

    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        errors[0] = ["missing header row"]
        return valid_users, errors

    headers = [h.strip().lower() for h in reader.fieldnames if h is not None]
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        errors[0] = [f"missing required column: {f}" for f in missing]
        return valid_users, errors

    seen_emails = {}
    for row_number, row in enumerate(reader, start=1):
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue  # skip blank rows

        cleaned, row_errors = validate_user_row(row)

        email_key = cleaned.get("email", "").lower()
        if email_key and not row_errors:
            if email_key in seen_emails:
                row_errors.append(
                    f"duplicate email (first seen in row {seen_emails[email_key]})"
                )
            else:
                seen_emails[email_key] = row_number

        if row_errors:
            errors[row_number] = row_errors
        else:
            valid_users.append(cleaned)

    return valid_users, errors
