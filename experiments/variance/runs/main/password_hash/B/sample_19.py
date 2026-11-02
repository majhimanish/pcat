import base64
import hashlib
import hmac
import secrets

# scrypt parameters (OWASP-recommended: N=2^17, r=8, p=1)
_N = 2 ** 17
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
_MAXMEM = 256 * 1024 * 1024


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt.

    Returns a self-describing string:
        scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=_MAXMEM,
    )
    return f"scrypt${_N}${_R}${_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash using constant-time comparison.

    Returns False for any mismatch or malformed hash.
    """
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)

        # Guard against absurd parameters in tampered/untrusted hashes
        if n > 2 ** 20 or r > 32 or p > 16 or n < 2 or (n & (n - 1)) != 0:
            return False

        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=max(_MAXMEM, 128 * n * r * 2),
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the stored hash uses weaker parameters than current ones."""
    try:
        scheme, n, r, p, _, _ = stored_hash.split("$")
        return scheme != "scrypt" or (int(n), int(r), int(p)) != (_N, _R, _P)
    except (ValueError, AttributeError):
        return True
