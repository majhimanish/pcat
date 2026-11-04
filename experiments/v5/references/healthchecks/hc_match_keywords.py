def match_keywords(haystack: str, keywords: str) -> bool:
    for s in keywords.split(","):
        s = s.strip()
        if s and s in haystack:
            return True

    return False
