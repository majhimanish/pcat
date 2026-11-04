from django.conf import settings
from django.core.signing import base64_hmac


def check_signature(badge_key: str, tag: str, sig: str) -> bool:
    ours = base64_hmac(str(badge_key), tag, settings.SECRET_KEY, algorithm="sha1")
    return ours[:8] == sig[:8]
