import csv
import io
import re

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "role")
ALLOWED_ROLES = {"admin", "editor", "viewer"}
DEFAULT_ROLE = "viewer"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
MAX_NAME_LENGTH = 100


def validate_user_row(row, seen_emails):
    """Validate one CSV row dict.

    Returns (user_dict_or_None, list_of_error_messages).
    `seen_emails` is a set of lowercase emails already accepted; it is not mutated here.
    """
    errors = []
    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    age_raw = (row.get("age") or "").strip()
    role = (row.get("role") or "").strip().lower()

    if not name:
        errors.append("name is required")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"name exceeds {MAX_NAME_LENGTH} characters")

    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"invalid email format: {email!r}")
    elif email.lower() in seen_emails:
        errors.append(f"duplicate email: {email!r}")

    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 <= age <= 150:
                errors.append(f"age out of range (0-150): {age}")
        except ValueError:
            errors.append(f"age is not an integer: {age_raw!r}")

    if not role:
        role = DEFAULT_ROLE
    elif role not in ALLOWED_ROLES:
        errors.append(
            f"invalid role {role!r}; allowed: {', '.join(sorted(ALLOWED_ROLES))}"
        )

    if errors:
        return None, errors
    return {"name": name, "email": email.lower(), "age": age, "role": role}, []


def import_users_from_reader(reader):
    """Process a csv.DictReader.

    Returns {"valid": [user dicts], "errors": [{"row": n, "errors": [...], "data": {...}}],
             "total": int}.
    Row numbers are 1-based file line numbers (header is line 1, first data row is 2).
    """
    valid, error_report = [], []
    seen_emails = set()
    total = 0

    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        return {
            "valid": [],
            "errors": [
                {
                    "row": 1,
                    "errors": [f"missing required column(s): {', '.join(missing)}"],
                    "data": {},
                }
            ],
            "total": 0,
        }
    reader.fieldnames = fieldnames

    for row in reader:
        total += 1
        line_no = reader.line_num
        # Extra cells beyond the header land under key None; short rows give None values.
        extra = row.pop(None, None)
        user, errors = validate_user_row(row, seen_emails)
        if extra:
            errors.append("row has more fields than the header")
            user = None
        if errors:
            error_report.append({"row": line_no, "errors": errors, "data": dict(row)})
        else:
            seen_emails.add(user["email"])
            valid.append(user)

    return {"valid": valid, "errors": error_report, "total": total}


def import_users_from_csv_text(text):
    """Import users from CSV text."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return import_users_from_reader(csv.DictReader(io.StringIO(text, newline="")))


def import_users_from_csv_file(path, encoding="utf-8-sig"):
    """Import users from a CSV file path."""
    with open(path, newline="", encoding=encoding) as f:
        return import_users_from_reader(csv.DictReader(f))


def format_error_report(result):
    """Render the error report as human-readable text."""
    lines = [
        f"Processed {result['total']} row(s): "
        f"{len(result['valid'])} valid, {len(result['errors'])} invalid"
    ]
    for entry in result["errors"]:
        lines.append(f"  Line {entry['row']}:")
        for msg in entry["errors"]:
            lines.append(f"    - {msg}")
    return "\n".join(lines)
