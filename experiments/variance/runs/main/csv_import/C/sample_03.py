import csv
import io
import re

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "phone", "role")
ALLOWED_ROLES = {"admin", "user", "guest"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-().]{6,19}$")


def validate_user_row(row: dict, seen_emails: set) -> tuple[dict, list[str]]:
    """Validate one row. Returns (cleaned_row, list_of_problem_strings)."""
    problems = []
    cleaned = {k: (v or "").strip() for k, v in row.items() if k is not None}

    name = cleaned.get("name", "")
    if not name:
        problems.append("name is required")
    elif len(name) > 100:
        problems.append("name exceeds 100 characters")

    email = cleaned.get("email", "").lower()
    if not email:
        problems.append("email is required")
    elif not EMAIL_RE.match(email):
        problems.append(f"invalid email: {email!r}")
    elif email in seen_emails:
        problems.append(f"duplicate email: {email!r}")
    cleaned["email"] = email

    age = cleaned.get("age", "")
    if age:
        try:
            age_val = int(age)
            if not 0 < age_val < 130:
                problems.append(f"age out of range: {age_val}")
            else:
                cleaned["age"] = age_val
        except ValueError:
            problems.append(f"age is not an integer: {age!r}")
    else:
        cleaned["age"] = None

    phone = cleaned.get("phone", "")
    if phone and not PHONE_RE.match(phone):
        problems.append(f"invalid phone: {phone!r}")

    role = cleaned.get("role", "").lower()
    if role:
        if role not in ALLOWED_ROLES:
            problems.append(f"invalid role: {role!r} (allowed: {sorted(ALLOWED_ROLES)})")
        cleaned["role"] = role
    else:
        cleaned["role"] = "user"

    return cleaned, problems


def import_users_csv(text: str) -> tuple[list[dict], dict[int, list[str]]]:
    """
    Parse and validate users from CSV text.

    Returns (valid_users, errors). `errors` maps the 1-based line number of the
    offending row to a list of problem messages. File-level problems (empty
    input, missing required columns) are keyed by 0 and 1 respectively.
    """
    valid_users: list[dict] = []
    errors: dict[int, list[str]] = {}
    seen_emails: set = set()

    if not isinstance(text, str):
        return [], {0: ["input must be a string"]}

    if text.startswith("\ufeff"):
        text = text[1:]

    if not text.strip():
        return [], {0: ["input is empty or has no header"]}

    reader = csv.DictReader(io.StringIO(text, newline=""))

    try:
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        return [], {1: [f"CSV parse error: {exc}"]}

    if fieldnames is None:
        return [], {0: ["input is empty or has no header"]}

    reader.fieldnames = [(h or "").strip().lower() for h in fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return [], {1: [f"missing required column(s): {', '.join(missing)}"]}

    try:
        for row in reader:
            line = reader.line_num
            row_problems = []

            if None in row:
                row_problems.append("row has more fields than the header")
            if any(v is None for k, v in row.items() if k is not None):
                row_problems.append("row has fewer fields than the header")

            if not row_problems and all(
                not (v or "").strip() for k, v in row.items() if k is not None
            ):
                continue  # skip fully blank lines

            cleaned, problems = validate_user_row(row, seen_emails)
            problems = row_problems + problems

            if problems:
                errors.setdefault(line, []).extend(problems)
            else:
                seen_emails.add(cleaned["email"])
                valid_users.append(cleaned)
    except csv.Error as exc:
        errors.setdefault(reader.line_num, []).append(f"CSV parse error: {exc}")

    return valid_users, errors
