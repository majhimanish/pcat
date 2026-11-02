"""Config parsing helpers: the same loop idiom inside different functions."""

RESERVED = ("include", "import")


def parse_ini(lines, result, errors):
    count = 0
    for raw in lines:
        line = raw.strip()
        try:
            key, value = line.split("=", 1)
            result[key.strip().lower()] = int(value.strip())
        except ValueError:
            errors.append(line)
            continue
        if key in RESERVED:
            errors.append(key)
    count += len(result)
    return count


def parse_env(entries, out, problems, verbose=False):
    if verbose:
        print("parsing", len(entries), "entries")
    for item in entries:
        text = item.strip()
        try:
            name, number = text.split(":", 1)
            out[name.strip().lower()] = int(number.strip())
        except ValueError:
            problems.append(text)
            continue
        if name in RESERVED:
            problems.append(name)
    return out


class Loader:
    def load(self, rows):
        bad = []
        data = {}
        for r in rows:
            s = r.strip()
            try:
                k, v = s.split("=", 1)
                data[k.strip().lower()] = int(v.strip())
            except ValueError:
                bad.append(s)
                continue
            if k in RESERVED:
                bad.append(k)
        self.data = data
        return bad
