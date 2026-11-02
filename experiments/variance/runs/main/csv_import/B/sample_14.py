import csv
import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row: dict[str, str], seen_ids: set[str], seen_emails: set[str]) -> list[str]:
    """Return a list of problem descriptions for a single user row (empty if valid)."""
    problems: list[str] = []

    user_id = (row.get("id") or "").strip()
    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    age_raw = (row.get("age") or "").strip()

    if not user_id:
        problems.append("id is missing")
    elif not user_id.isdigit():
        problems.append(f"id '{user_id}' is not a positive integer")
    elif user_id in seen_ids:
        problems.append(f"duplicate id '{user_id}'")

    if not name:
        problems.append("name is missing")
    elif len(name) > 100:
        problems.append("name exceeds 100 characters")

    if not email:
        problems.append("email is missing")
    elif not EMAIL_RE.match(email):
        problems.append(f"email '{email}' is not a valid address")
    elif email.lower() in seen_emails:
        problems.append(f"duplicate email '{email}'")

    if not age_raw:
        problems.append("age is missing")
    else:
        try:
            age = int(age_raw)
            if not 0 < age < 130:
                problems.append(f"age {age} is out of range (1-129)")
        except ValueError:
            problems.append(f"age '{age_raw}' is not an integer")

    return problems


def validate_users_csv(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate a CSV of users row by row.

    Returns (valid_records, problems), where:
      - valid_records is a list of cleaned row dicts (id, name, email, age as int)
      - problems is a list of dicts: {"line": int, "row": dict | None, "errors": [str, ...]}
        File-level problems (e.g. missing columns) use line 0 / 1 and row None.
    """
    valid_records: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return [], [{"line": 0, "row": None, "errors": ["file is empty or has no header"]}]

            headers = {h.strip().lower() for h in reader.fieldnames if h}
            missing = [c for c in REQUIRED_COLUMNS if c not in headers]
            if missing:
                return [], [{
                    "line": 1,
                    "row": None,
                    "errors": [f"missing required column(s): {', '.join(missing)}"],
                }]

            reader.fieldnames = [h.strip().lower() if h else h for h in reader.fieldnames]

            for row in reader:
                line = reader.line_num
                errors: list[str] = []

                if None in row:
                    errors.append("row has more fields than the header")
                if any(v is None for k, v in row.items() if k is not None):
                    errors.append("row has fewer fields than the header")

                clean_input = {k: v for k, v in row.items() if k is not None}
                errors.extend(validate_user_row(clean_input, seen_ids, seen_emails))

                if errors:
                    problems.append({"line": line, "row": clean_input, "errors": errors})
                    continue

                record = {
                    "id": clean_input["id"].strip(),
                    "name": clean_input["name"].strip(),
                    "email": clean_input["email"].strip(),
                    "age": int(clean_input["age"].strip()),
                }
                seen_ids.add(record["id"])
                seen_emails.add(record["email"].lower())
                valid_records.append(record)

    except FileNotFoundError:
        return [], [{"line": 0, "row": None, "errors": [f"file not found: {path}"]}]
    except UnicodeDecodeError as exc:
        return valid_records, problems + [{
            "line": 0,
            "row": None,
            "errors": [f"could not decode file with encoding '{encoding}': {exc}"],
        }]
    except csv.Error as exc:
        return valid_records, problems + [{
            "line": 0,
            "row": None,
            "errors": [f"CSV parsing error: {exc}"],
        }]

    return valid_records, problems
