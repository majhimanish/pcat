import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimum: N=2**17, r=8, p=1)
_SCRYPT_N = 2 ** 17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16
_MAXMEM = 256 * 1024 * 1024


def hash_password(password: str) -> str:
    """Hash a password with a random salt using scrypt.

    Returns a self-describing string:
    scrypt$N$r$p$<b64 salt>$<b64 hash>
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_MAXMEM,
    )
    return "$".join([
        "scrypt",
        str(_SCRYPT_N),
        str(_SCRYPT_R),
        str(_SCRYPT_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash using constant-time comparison."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=_MAXMEM,
        )
    except (ValueError, TypeError, AttributeError):
        return False

    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the stored hash uses weaker parameters than current ones."""
    try:
        scheme, n, r, p, _, _ = stored_hash.split("$")
        return scheme != "scrypt" or (int(n), int(r), int(p)) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    except (ValueError, AttributeError):
        return True
