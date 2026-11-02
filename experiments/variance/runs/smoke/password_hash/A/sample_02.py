import base64
import hashlib
import hmac
import os

_ALGORITHM = "scrypt"
_N = 2 ** 14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password using scrypt with a random salt.

    Returns a self-describing string: scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
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
    """Verify a password against a hash produced by hash_password."""
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False

    try:
        algorithm, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(derived, expected)
