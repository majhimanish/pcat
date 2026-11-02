import csv
import re
from datetime import datetime

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
REQUIRED_COLUMNS = ["id", "name", "email"]
VALID_ROLES = {"admin", "user", "guest"}


def validate_row(row, line_number, seen_ids, seen_emails):
    """Validate a single CSV row (dict). Returns (cleaned_record_or_None, list_of_problems)."""
    problems = []

    def problem(field, message):
        problems.append({"line": line_number, "field": field, "message": message})

    # Normalize: strip whitespace, treat None (short rows) as empty
    clean = {k: (v or "").strip() for k, v in row.items() if k is not None}

    # Extra values beyond header columns are stored under key None by DictReader
    if None in row and row[None]:
        problem(None, "row has more fields than the header")

    # id
    user_id = clean.get("id", "")
    if not user_id:
        problem("id", "missing id")
    elif not user_id.isdigit() or int(user_id) <= 0:
        problem("id", f"id must be a positive integer, got '{user_id}'")
    elif user_id in seen_ids:
        problem("id", f"duplicate id '{user_id}' (first seen on line {seen_ids[user_id]})")

    # name
    name = clean.get("name", "")
    if not name:
        problem("name", "missing name")
    elif len(name) > 100:
        problem("name", "name longer than 100 characters")

    # email
    email = clean.get("email", "")
    if not email:
        problem("email", "missing email")
    elif not EMAIL_RE.match(email):
        problem("email", f"invalid email '{email}'")
    elif email.lower() in seen_emails:
        problem("email", f"duplicate email '{email}' (first seen on line {seen_emails[email.lower()]})")

    # age (optional)
    age = clean.get("age", "")
    if age:
        if not age.isdigit() or not (0 < int(age) < 150):
            problem("age", f"age must be an integer between 1 and 149, got '{age}'")

    # role (optional)
    role = clean.get("role", "")
    if role and role.lower() not in VALID_ROLES:
        problem("role", f"role must be one of {sorted(VALID_ROLES)}, got '{role}'")

    # signup_date (optional, YYYY-MM-DD, not in the future)
    signup = clean.get("signup_date", "")
    if signup:
        try:
            parsed = datetime.strptime(signup, "%Y-%m-%d")
            if parsed > datetime.now():
                problem("signup_date", f"signup_date is in the future: '{signup}'")
        except ValueError:
            problem("signup_date", f"signup_date must be YYYY-MM-DD, got '{signup}'")

    if problems:
        return None, problems

    record = dict(clean)
    record["id"] = int(user_id)
    if age:
        record["age"] = int(age)
    if role:
        record["role"] = role.lower()
    return record, []


def validate_users_csv(path, encoding="utf-8-sig"):
    """
    Validate a CSV file of users row by row.

    Returns (valid_records, problems) where:
      - valid_records is a list of cleaned dicts for rows that passed every check
      - problems is a list of dicts: {"line": int, "field": str|None, "message": str}
    Line numbers are 1-based and count the header as line 1.
    """
    valid_records = []
    problems = []
    seen_ids = {}
    seen_emails = {}

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return [], [{"line": 1, "field": None, "message": "file is empty or has no header"}]

            header = [h.strip().lower() for h in reader.fieldnames]
            reader.fieldnames = header

            missing = [c for c in REQUIRED_COLUMNS if c not in header]
            if missing:
                return [], [{"line": 1, "field": None,
                             "message": f"missing required column(s): {', '.join(missing)}"}]

            dupes = {h for h in header if header.count(h) > 1}
            if dupes:
                problems.append({"line": 1, "field": None,
                                 "message": f"duplicate column name(s): {', '.join(sorted(dupes))}"})

            try:
                for row in reader:
                    line_number = reader.line_num
                    # Skip fully blank rows
                    if not any((v or "").strip() for k, v in row.items() if k is not None):
                        continue

                    record, row_problems = validate_row(row, line_number, seen_ids, seen_emails)

                    if record is not None:
                        seen_ids[str(record["id"])] = line_number
                        seen_emails[record["email"].lower()] = line_number
                        valid_records.append(record)
                    else:
                        problems.extend(row_problems)
            except csv.Error as e:
                problems.append({"line": reader.line_num, "field": None,
                                 "message": f"CSV parse error: {e}"})

    except FileNotFoundError:
        return [], [{"line": 0, "field": None, "message": f"file not found: {path}"}]
    except UnicodeDecodeError as e:
        return [], [{"line": 0, "field": None, "message": f"could not decode file as {encoding}: {e}"}]

    return valid_records, problems
