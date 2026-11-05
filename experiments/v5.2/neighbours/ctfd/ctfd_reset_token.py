def generate_invite_token(addr, timeout=604800):
    nonce = hexencode(os.urandom(32))
    cache.set(f"invite_{nonce}", addr, timeout=timeout)
    return nonce
