def verify_invite_token(nonce):
    addr = cache.get(f"invite_{nonce}")
    return addr
