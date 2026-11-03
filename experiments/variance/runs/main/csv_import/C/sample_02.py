import csv
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age",)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


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

    return cleaned, problems


def parse_users_csv(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict], list[dict[str, Any]]]:
    """
    Parse and validate a users CSV.

    Returns (good_rows, errors). Each error is a dict:
        {"line": <1-based file line number>, "row": <raw row dict>, "errors": [messages]}
    File-level problems (missing file, empty file, missing columns) are reported
    as a single error with line 0 / row None.
    """
    good_rows: list[dict] = []
    errors: list[dict[str, Any]] = []
    seen_emails: set = set()

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return [], [{"line": 0, "row": None, "errors": ["file is empty or has no header"]}]

            reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
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
                    row_problems = []

                    if None in row:
                        row_problems.append("row has more fields than the header")
                    if any(v is None for k, v in row.items() if k is not None):
                        row_problems.append("row has fewer fields than the header")

                    if all(not (v or "").strip() for k, v in row.items() if k is not None) and not row_problems:
                        continue  # skip fully blank lines

                    cleaned, problems = validate_user_row(row, seen_emails)
                    problems = row_problems + problems

                    if problems:
                        errors.append({"line": line, "row": dict(row), "errors": problems})
                    else:
                        seen_emails.add(cleaned["email"])
                        good_rows.append(cleaned)
            except csv.Error as exc:
                errors.append({"line": reader.line_num, "row": None, "errors": [f"CSV parse error: {exc}"]})
    except FileNotFoundError:
        return [], [{"line": 0, "row": None, "errors": [f"file not found: {path}"]}]
    except UnicodeDecodeError as exc:
        return good_rows, errors + [{"line": 0, "row": None, "errors": [f"encoding error: {exc}"]}]
    except OSError as exc:
        return [], [{"line": 0, "row": None, "errors": [f"cannot read file: {exc}"]}]

    return good_rows, errors
