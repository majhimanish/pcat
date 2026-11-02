import base64
import hashlib
import hmac
import secrets

_ALGORITHM = "scrypt"
_N = 2 ** 15
_R = 8
_P = 1
_DKLEN = 64
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt.

    Returns a self-describing string:
    scrypt$N$r$p$base64(salt)$base64(hash)
    """
    if not isinstance(password, str):
        raise TypeError("password must be a str")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        maxmem=128 * _N * _R * 2,
        dklen=_DKLEN,
    )
    return "$".join([
        _ALGORITHM,
        str(_N),
        str(_R),
        str(_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a hash produced by hash_password.

    Uses constant-time comparison. Returns False for malformed hashes.
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    try:
        algorithm, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=128 * n * r * 2,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)
