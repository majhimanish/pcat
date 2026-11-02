import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = ("name", "email")


def validate_user_row(row):
    """Return (cleaned_user, errors) for a single CSV row dict."""
    errors = []
    cleaned = {k: (v or "").strip() for k, v in row.items() if k is not None}

    for field in REQUIRED_FIELDS:
        if not cleaned.get(field):
            errors.append(f"missing required field: {field}")

    email = cleaned.get("email", "")
    if email and not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email}")

    age = cleaned.get("age", "")
    if age:
        if not age.isdigit() or not (0 < int(age) < 150):
            errors.append(f"invalid age: {age}")
        else:
            cleaned["age"] = int(age)

    if None in row and any((x or "").strip() for x in (row[None] or [])):
        errors.append("too many columns")

    return cleaned, errors


def import_users_csv(text):
    """Parse CSV text and validate each user row.

    Returns (valid_users, errors) where valid_users is a list of dicts and
    errors maps row number (1-based data row; header is row 0) to a list of
    error messages. Duplicate emails (case-insensitive) are flagged.
    """
    valid_users = []
    errors = {}

    if not text or not text.strip():
        return valid_users, {0: ["empty input"]}

    if text.startswith("\ufeff"):
        text = text[1:]

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return valid_users, {0: ["missing header"]}
    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]

    missing = [f for f in REQUIRED_FIELDS if f not in reader.fieldnames]
    if missing:
        return valid_users, {0: [f"missing header column: {', '.join(missing)}"]}

    seen_emails = {}
    row_num = 0
    try:
        for row in reader:
            row_num += 1
            if not any((v or "").strip() for k, v in row.items() if k is not None):
                continue  # skip blank lines
            user, row_errors = validate_user_row(row)

            email_key = user.get("email", "").lower()
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
                valid_users.append(user)
    except csv.Error as exc:
        errors[row_num + 1] = [f"malformed CSV: {exc}"]

    return valid_users, errors
