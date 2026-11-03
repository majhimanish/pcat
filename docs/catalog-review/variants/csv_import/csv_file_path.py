"""Parse and validate a users CSV file (name, email, age), streaming it from disk.

Standard library only. Errors are reported per row; values are not echoed (PII).
"""

import csv
import os
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
MAX_ROWS = 10000
MAX_EMAIL_LENGTH = 254


def import_users_file(path: str | os.PathLike, max_rows: int = MAX_ROWS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (valid users, errors); each error is {"row": line number, "errors": [messages]}."""
    with open(path, newline="", encoding="utf-8-sig") as handle:  # utf-8-sig drops an Excel BOM
        return _import_rows(csv.DictReader(handle), max_rows)


def _import_rows(reader: csv.DictReader, max_rows: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
