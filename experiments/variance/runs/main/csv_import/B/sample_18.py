import csv
import io
import re

REQUIRED_FIELDS = ["name", "email"]
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def validate_user_row(row):
    """Return (cleaned_user, list_of_error_messages) for a single CSV row dict."""
    errors = []
    cleaned = {}

    for key, value in row.items():
        if key is None:
            continue
        cleaned[key.strip().lower()] = (value or "").strip()

    if None in row and row[None]:
        errors.append("too many columns")

    for field in REQUIRED_FIELDS:
        if not cleaned.get(field):
            errors.append(f"missing {field}")

    email = cleaned.get("email", "")
    if email and not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email}")

    age = cleaned.get("age", "")
    if age:
        try:
            age_val = int(age)
            if not 0 < age_val < 150:
                errors.append(f"age out of range: {age}")
            else:
                cleaned["age"] = age_val
        except ValueError:
            errors.append(f"invalid age: {age}")

    return cleaned, errors


def import_users_csv(text):
    """
    Parse CSV text and validate each user row.

    Returns (valid_users, errors) where:
      - valid_users is a list of cleaned user dicts
      - errors is a dict mapping row number (1-based data row; header excluded,
        file line numbers are row + 1) to a list of error messages
    """
    valid_users = []
    errors = {}

    if text is None or not text.strip():
        return valid_users, {0: ["empty input"]}

    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        return valid_users, {0: ["missing header"]}

    headers = [h.strip().lower() for h in reader.fieldnames if h]
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        return valid_users, {0: [f"missing required column(s): {', '.join(missing)}"]}

    seen_emails = {}
    try:
        for row_num, row in enumerate(reader, start=1):
            if not any((v or "").strip() for k, v in row.items() if k is not None):
                continue  # skip blank rows

            cleaned, row_errors = validate_user_row(row)

            email_key = cleaned.get("email", "").lower()
            if email_key and not row_errors:
                if email_key in seen_emails:
                    row_errors.append(
                        f"duplicate email (first seen in row {seen_emails[email_key]})"
                    )
                else:
                    seen_emails[email_key] = row_num

            if row_errors:
                errors[row_num] = row_errors
            else:
                valid_users.append(cleaned)
    except csv.Error as exc:
        errors[reader.line_num] = [f"malformed CSV: {exc}"]

    return valid_users, errors
