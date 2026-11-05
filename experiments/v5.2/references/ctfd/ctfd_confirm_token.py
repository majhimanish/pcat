def generate_email_confirm_token(addr, timeout=1800):
    nonce = hexencode(os.urandom(32))
    cache.set(f"confirm_email_{nonce}", addr, timeout=timeout)
    return nonce

def verify_email_confirm_token(nonce):
    addr = cache.get(f"confirm_email_{nonce}")
    if addr is None:
        raise UserConfirmTokenInvalidException
    return addr

def remove_email_confirm_token(nonce):
    cache.delete(f"confirm_email_{nonce}")
