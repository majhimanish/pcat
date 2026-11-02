import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimum: N=2**17, r=8, p=1)
_N = 2 ** 17
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt.

    Returns a self-describing string: scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=256 * 1024 * 1024,
    )
    return "$".join([
        "scrypt",
        str(_N),
        str(_R),
        str(_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash in constant time."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=256 * 1024 * 1024,
        )
    except (ValueError, TypeError, AttributeError):
        return False

    return hmac.compare_digest(dk, expected)
