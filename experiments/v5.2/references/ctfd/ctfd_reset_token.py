def generate_password_reset_token(addr, timeout=1800):
    nonce = hexencode(os.urandom(32))
    cache.set(f"reset_password_{nonce}", addr, timeout=timeout)
    return nonce

def verify_reset_password_token(nonce):
    addr = cache.get(f"reset_password_{nonce}")
    if addr is None:
        raise UserResetPasswordTokenInvalidException
    return addr

def remove_reset_password_token(nonce):
    cache.delete(f"reset_password_{nonce}")
