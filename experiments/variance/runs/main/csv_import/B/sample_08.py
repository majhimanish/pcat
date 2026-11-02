import csv
import io
import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
REQUIRED_FIELDS = ("name", "email")


def validate_user_row(row, seen_emails):
    """Return (clean_user, errors) for a single CSV row dict."""
    errors = []
    clean = {}

    # Normalize: strip whitespace, treat missing values as empty strings.
    values = {}
    for key, val in row.items():
        if key is None:
            continue
        values[key.strip().lower()] = (val or "").strip()

    if None in row and row[None]:
        errors.append("too many columns")

    for field in REQUIRED_FIELDS:
        if not values.get(field):
            errors.append(f"missing {field}")

    name = values.get("name", "")
    email = values.get("email", "").lower()

    if email:
        if not EMAIL_RE.match(email):
            errors.append("invalid email")
        elif email in seen_emails:
            errors.append("duplicate email")

    age_raw = values.get("age", "")
    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 <= age <= 150:
                errors.append("age out of range")
        except ValueError:
            errors.append("invalid age")

    if errors:
        return None, errors

    clean = {"name": name, "email": email}
    if age is not None:
        clean["age"] = age
    for key, val in values.items():
        if key not in clean and key not in ("name", "email", "age"):
            clean[key] = val
    return clean, []


def import_users_csv(text):
    """
    Parse CSV text and validate each user row.

    Returns (valid_users, errors) where:
      - valid_users is a list of cleaned user dicts
      - errors is a dict mapping row number (1-based data row, header excluded;
        the file line is row + 1) to a list of error messages.
    """
    valid_users = []
    errors = {}

    if text is None or not text.strip():
        errors[0] = ["empty input"]
        return valid_users, errors

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    headers = [h.strip().lower() for h in (reader.fieldnames or []) if h]
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        errors[0] = [f"missing required column(s): {', '.join(missing)}"]
        return valid_users, errors

    seen_emails = set()
    row_num = 0
    for row in reader:
        row_num += 1
        # Skip fully blank rows.
        if not any((v or "").strip() for k, v in row.items() if k is not None) and not row.get(None):
            continue
        user, row_errors = validate_user_row(row, seen_emails)
        if row_errors:
            errors[row_num] = row_errors
        else:
            seen_emails.add(user["email"])
            valid_users.append(user)

    return valid_users, errors
