import csv
import io
import re

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "role")
ALLOWED_ROLES = {"admin", "editor", "viewer", "user"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
MAX_NAME_LEN = 100


def validate_user_row(row, seen_emails):
    """Validate one row dict. Returns (clean_user_or_None, list_of_error_strings)."""
    errors = []

    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip().lower()
    age_raw = (row.get("age") or "").strip()
    role = (row.get("role") or "").strip().lower() or "user"

    if not name:
        errors.append("name: required")
    elif len(name) > MAX_NAME_LEN:
        errors.append(f"name: exceeds {MAX_NAME_LEN} characters")

    if not email:
        errors.append("email: required")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format '{email}'")
    elif email in seen_emails:
        errors.append(f"email: duplicate '{email}' (first seen on line {seen_emails[email]})")

    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 150:
                errors.append(f"age: out of range '{age_raw}'")
        except ValueError:
            errors.append(f"age: not an integer '{age_raw}'")

    if role not in ALLOWED_ROLES:
        errors.append(f"role: must be one of {sorted(ALLOWED_ROLES)}, got '{role}'")

    if errors:
        return None, errors
    return {"name": name, "email": email, "age": age, "role": role}, []


def import_users_from_reader(fileobj):
    """Parse a text file-like object of CSV. Returns (valid_users, error_report).

    error_report is a list of {"line": int, "row": dict_or_None, "errors": [str]}.
    Line numbers are file line numbers (header = line 1).
    """
    valid_users = []
    error_report = []
    seen_emails = {}

    reader = csv.DictReader(fileobj)
    if reader.fieldnames is None:
        return [], [{"line": 1, "row": None, "errors": ["file is empty or has no header"]}]

    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return [], [{"line": 1, "row": None,
                     "errors": [f"header: missing required column(s): {', '.join(missing)}"]}]

    try:
        for row in reader:
            line = reader.line_num
            # Malformed rows: extra fields land under key None, short rows have None values.
            if None in row:
                error_report.append({"line": line, "row": dict(row.items() if False else
                                     {k: v for k, v in row.items() if k is not None}),
                                     "errors": ["row: too many fields"]})
                continue
            if all((v is None or not str(v).strip()) for v in row.values()):
                continue  # skip blank rows silently

            user, errors = validate_user_row(row, seen_emails)
            if errors:
                error_report.append({"line": line, "row": dict(row), "errors": errors})
            else:
                seen_emails[user["email"]] = line
                valid_users.append(user)
    except csv.Error as exc:
        error_report.append({"line": reader.line_num, "row": None,
                             "errors": [f"csv: parse error: {exc}"]})

    return valid_users, error_report


def import_users_from_csv(path, encoding="utf-8-sig"):
    """Import users from a CSV file path. Returns (valid_users, error_report)."""
    with open(path, newline="", encoding=encoding) as f:
        return import_users_from_reader(f)


def import_users_from_string(text):
    """Import users from a CSV string. Returns (valid_users, error_report)."""
    return import_users_from_reader(io.StringIO(text, newline=""))


def format_error_report(error_report):
    """Render the error report as human-readable text."""
    if not error_report:
        return "No errors."
    lines = []
    for entry in error_report:
        lines.append(f"Line {entry['line']}:")
        for err in entry["errors"]:
            lines.append(f"  - {err}")
    return "\n".join(lines)
