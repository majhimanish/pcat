import csv
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "phone", "role")
VALID_ROLES = {"admin", "editor", "viewer", "user"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().\-]{6,19}$")


def validate_row(row: dict[str, str], seen_emails: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate and normalize a single row. Returns (clean_row, problems)."""
    problems: list[str] = []
    clean: dict[str, Any] = {}

    name = (row.get("name") or "").strip()
    if not name:
        problems.append("name is required")
    elif len(name) > 100:
        problems.append("name exceeds 100 characters")
    clean["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        problems.append("email is required")
    elif not EMAIL_RE.match(email):
        problems.append(f"invalid email: {email!r}")
    elif email in seen_emails:
        problems.append(f"duplicate email: {email!r}")
    clean["email"] = email

    age_raw = (row.get("age") or "").strip()
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 130:
                problems.append(f"age out of range: {age}")
            else:
                clean["age"] = age
        except ValueError:
            problems.append(f"age is not an integer: {age_raw!r}")

    phone = (row.get("phone") or "").strip()
    if phone:
        if PHONE_RE.match(phone):
            clean["phone"] = phone
        else:
            problems.append(f"invalid phone: {phone!r}")

    role = (row.get("role") or "").strip().lower()
    if role:
        if role in VALID_ROLES:
            clean["role"] = role
        else:
            problems.append(f"invalid role: {role!r} (allowed: {', '.join(sorted(VALID_ROLES))})")

    return (None if problems else clean), problems


def import_users(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse a users CSV and validate every row.

    Returns (good_rows, errors) where each error is
    {"line": <file line number>, "row": <raw row>, "errors": [<messages>]}.
    A file-level problem (missing header/required columns) is reported as a
    single error with line 1 and no rows are imported.
    """
    good: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: set[str] = set()

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return [], [{"line": 1, "row": None, "errors": ["file is empty or has no header"]}]

            reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                return [], [{
                    "line": 1,
                    "row": None,
                    "errors": [f"missing required column(s): {', '.join(missing)}"],
                }]

            try:
                for row in reader:
                    line = reader.line_num
                    # Rows with extra fields land under key None; short rows have None values.
                    row_problems: list[str] = []
                    if None in row:
                        row_problems.append("row has more fields than the header")
                    if any(v is None for k, v in row.items() if k is not None):
                        row_problems.append("row has fewer fields than the header")

                    if all(not (v or "").strip() for k, v in row.items() if k is not None) and not row_problems:
                        continue  # skip fully blank lines

                    clean, problems = validate_row(
                        {k: v for k, v in row.items() if k is not None}, seen_emails
                    )
                    problems = row_problems + problems

                    if problems:
                        errors.append({
                            "line": line,
                            "row": {k: v for k, v in row.items() if k is not None},
                            "errors": problems,
                        })
                    else:
                        seen_emails.add(clean["email"])
                        good.append(clean)
            except csv.Error as exc:
                errors.append({"line": reader.line_num, "row": None, "errors": [f"CSV parse error: {exc}"]})
    except FileNotFoundError:
        return [], [{"line": 0, "row": None, "errors": [f"file not found: {path}"]}]
    except UnicodeDecodeError as exc:
        return [], [{"line": 0, "row": None, "errors": [f"cannot decode file as {encoding}: {exc}"]}]

    return good, errors
