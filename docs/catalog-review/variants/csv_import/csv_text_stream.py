"""Parse and validate a users CSV (name, email, age) from a string or text stream.

Standard library only. Errors are reported per row; values are not echoed (PII).
"""

import csv
import io
from typing import Any, TextIO

REQUIRED_COLUMNS = ("name", "email")
MAX_ROWS = 10000
MAX_EMAIL_LENGTH = 254


def import_users(source: str | TextIO, max_rows: int = MAX_ROWS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (valid users, errors); each error is {"row": line number, "errors": [messages]}."""
    reader = csv.DictReader(io.StringIO(source) if isinstance(source, str) else source)
    header = [h.strip().lstrip("﻿").lower() for h in reader.fieldnames or []]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        return [], [{"row": 1, "errors": [f"missing columns: {', '.join(missing)}"]}]
    reader.fieldnames = header
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for count, row in enumerate(reader, 1):
        if count > max_rows:
            errors.append({"row": reader.line_num, "errors": [f"more than {max_rows} rows; stopped"]})
            break
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip().lower()
        age_raw = (row.get("age") or "").strip()
        local, _, domain = email.partition("@")  # no regex: nothing to backtrack on hostile input
        problems = [] if name else ["name is required"]
        if None in row:
            problems.append("too many fields")
        if len(email) > MAX_EMAIL_LENGTH or not local or "." not in domain.strip(".") or "@" in domain or " " in email:
            problems.append("email is invalid")
        elif email in seen:
            problems.append("duplicate email")
        if age_raw and not (age_raw.isdigit() and int(age_raw) <= 150):
            problems.append("age must be a whole number from 0 to 150")
        if problems:
            errors.append({"row": reader.line_num, "errors": problems})
        else:
            seen.add(email)
            valid.append({"name": name, "email": email, "age": int(age_raw) if age_raw else None})
    return valid, errors
