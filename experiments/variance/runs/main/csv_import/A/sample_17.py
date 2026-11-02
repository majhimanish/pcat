import csv
import io
import re
from datetime import datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate a single user row dict.

    Returns a tuple (cleaned_row, errors) where cleaned_row is a dict with
    normalized values (or None if invalid) and errors is a list of strings.
    """
    errors = []
    cleaned = {}

    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if value is None or not str(value).strip():
            errors.append(f"missing required field '{field}'")
    if errors:
        return None, errors

    raw_id = row["id"].strip()
    if not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"invalid id '{raw_id}': must be a positive integer")
    else:
        cleaned["id"] = int(raw_id)

    name = row["name"].strip()
    if len(name) < 2 or len(name) > 100:
        errors.append("invalid name: must be 2-100 characters")
    else:
        cleaned["name"] = name

    email = row["email"].strip().lower()
    if not EMAIL_RE.match(email):
        errors.append(f"invalid email '{email}'")
    else:
        cleaned["email"] = email

    raw_age = row["age"].strip()
    try:
        age = int(raw_age)
        if not 0 <= age <= 120:
            raise ValueError
        cleaned["age"] = age
    except ValueError:
        errors.append(f"invalid age '{raw_age}': must be an integer 0-120")

    signup = (row.get("signup_date") or "").strip()
    if signup:
        try:
            cleaned["signup_date"] = datetime.strptime(signup, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"invalid signup_date '{signup}': expected YYYY-MM-DD")

    if errors:
        return None, errors
    return cleaned, []


def parse_users_csv(source):
    """Parse and validate a CSV of users.

    Args:
        source: a CSV string, or a path to a CSV file.

    Returns:
        (valid_rows, errors) where valid_rows is a list of cleaned dicts and
        errors is a list of dicts: {"row": <line number>, "errors": [...]}.
        Line numbers are 1-based and count the header as line 1.
    """
    if "\n" in source or "," in source:
        stream = io.StringIO(source)
        close = False
    else:
        stream = open(source, newline="", encoding="utf-8-sig")
        close = True

    valid_rows = []
    row_errors = []
    seen_ids = set()
    seen_emails = set()

    try:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            return [], [{"row": 1, "errors": ["empty file or missing header"]}]

        headers = {h.strip().lower() for h in reader.fieldnames if h}
        missing = [f for f in REQUIRED_FIELDS if f not in headers]
        if missing:
            return [], [{"row": 1, "errors": [f"missing columns: {', '.join(missing)}"]}]

        for line_no, raw in enumerate(reader, start=2):
            row = {
                (k or "").strip().lower(): (v if v is not None else "")
                for k, v in raw.items()
                if k is not None
            }

            if not any(str(v).strip() for v in row.values()):
                continue  # skip blank lines

            if None in raw:
                row_errors.append(
                    {"row": line_no, "errors": ["too many columns in row"]}
                )
                continue

            cleaned, errors = validate_user_row(row)

            if cleaned is not None:
                if cleaned["id"] in seen_ids:
                    errors.append(f"duplicate id {cleaned['id']}")
                if cleaned["email"] in seen_emails:
                    errors.append(f"duplicate email '{cleaned['email']}'")

            if errors:
                row_errors.append({"row": line_no, "errors": errors})
            else:
                seen_ids.add(cleaned["id"])
                seen_emails.add(cleaned["email"])
                valid_rows.append(cleaned)
    finally:
        if close:
            stream.close()

    return valid_rows, row_errors
