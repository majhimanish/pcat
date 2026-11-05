def create_share_token(data: dict, token_expire_minutes: int | None = None) -> str:
    minutes = token_expire_minutes or settings.auth_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    to_encode = {k: v for k, v in data.items() if v is not None}
    to_encode.update({"exp": int(expire.timestamp())})
    payload = json.dumps(to_encode, separators=(",", ":"))
    signature = hashlib.sha256((payload + settings.auth_secret_key).encode()).hexdigest()
    return f"{payload.encode().hex()}.{signature}"
