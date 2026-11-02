import csv
import io
import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row, line_number, seen_ids, seen_emails):
    """Validate a single user row. Returns (cleaned_record or None, list_of_problems)."""
    problems = []

    def clean(key):
        value = row.get(key)
        return value.strip() if isinstance(value, str) else ""

    if None in row:
        problems.append({"line": line_number, "field": None,
                         "message": "row has more fields than the header"})
    if any(v is None for k, v in row.items() if k is not None):
        problems.append({"line": line_number, "field": None,
                         "message": "row has fewer fields than the header"})

    user_id = clean("id")
    name = clean("name")
    email = clean("email")
    age_raw = clean("age")

    # id
    if not user_id:
        problems.append({"line": line_number, "field": "id", "message": "id is required"})
    elif not user_id.isdigit() or int(user_id) <= 0:
        problems.append({"line": line_number, "field": "id",
                         "message": f"id must be a positive integer, got {user_id!r}"})
    elif user_id in seen_ids:
        problems.append({"line": line_number, "field": "id",
                         "message": f"duplicate id {user_id!r} (first seen on line {seen_ids[user_id]})"})

    # name
    if not name:
        problems.append({"line": line_number, "field": "name", "message": "name is required"})
    elif len(name) > 100:
        problems.append({"line": line_number, "field": "name",
                         "message": "name must be at most 100 characters"})

    # email
    if not email:
        problems.append({"line": line_number, "field": "email", "message": "email is required"})
    elif not EMAIL_RE.match(email):
        problems.append({"line": line_number, "field": "email",
                         "message": f"invalid email format: {email!r}"})
    elif email.lower() in seen_emails:
        problems.append({"line": line_number, "field": "email",
                         "message": f"duplicate email {email!r} (first seen on line {seen_emails[email.lower()]})"})

    # age
    age = None
    if not age_raw:
        problems.append({"line": line_number, "field": "age", "message": "age is required"})
    else:
        try:
            age = int(age_raw)
            if not 0 <= age <= 120:
                problems.append({"line": line_number, "field": "age",
                                 "message": f"age must be between 0 and 120, got {age}"})
        except ValueError:
            problems.append({"line": line_number, "field": "age",
                             "message": f"age must be an integer, got {age_raw!r}"})

    if problems:
        return None, problems

    seen_ids[user_id] = line_number
    seen_emails[email.lower()] = line_number
    return {"id": int(user_id), "name": name, "email": email, "age": age}, []


def validate_users_csv(source):
    """
    Validate a CSV of users row by row.

    `source` may be a CSV string, a file path, or an open text file-like object.
    Expected header columns: id, name, email, age.

    Returns (valid_records, problems), where:
      - valid_records is a list of cleaned dicts
      - problems is a list of dicts with keys: line, field, message
    """
    problems = []
    valid_records = []
    handle = None
    opened_here = False

    try:
        if hasattr(source, "read"):
            handle = source
        elif isinstance(source, str) and "\n" not in source and "," not in source:
            handle = open(source, newline="", encoding="utf-8-sig")
            opened_here = True
        elif isinstance(source, str):
            handle = io.StringIO(source)
        else:
            raise TypeError("source must be a CSV string, file path, or file-like object")

        reader = csv.DictReader(handle)
        header = [h.strip().lower() for h in (reader.fieldnames or [])]

        if not header:
            return [], [{"line": 1, "field": None, "message": "CSV is empty or has no header"}]

        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            return [], [{"line": 1, "field": None,
                         "message": f"missing required column(s): {', '.join(missing)}"}]

        reader.fieldnames = header
        seen_ids = {}
        seen_emails = {}

        try:
            for row in reader:
                line_number = reader.line_num
                if not any((v or "").strip() for k, v in row.items() if k is not None):
                    continue  # skip blank lines
                record, row_problems = validate_user_row(row, line_number, seen_ids, seen_emails)
                if record is not None:
                    valid_records.append(record)
                else:
                    problems.extend(row_problems)
        except csv.Error as exc:
            problems.append({"line": reader.line_num, "field": None,
                             "message": f"CSV parsing error: {exc}"})
    finally:
        if opened_here and handle is not None:
            handle.close()

    return valid_records, problems
