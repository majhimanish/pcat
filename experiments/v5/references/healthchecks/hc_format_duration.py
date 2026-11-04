def format_duration(duration: timedelta) -> str:
    remaining_seconds = int(duration.total_seconds())

    result = []

    for unit in (WEEK, DAY, HOUR, MINUTE):
        if unit == WEEK and remaining_seconds % unit.nsecs != 0:
            # Say "8 days" instead of "1 week 1 day"
            continue

        v, remaining_seconds = divmod(remaining_seconds, unit.nsecs)
        if v == 1:
            result.append(f"1 {unit.name}")
        elif v > 1:
            result.append(f"{v} {unit.plural}")

    return " ".join(result)
