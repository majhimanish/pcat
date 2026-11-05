async def require_wallet_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    wallet = await get_wallet_for_key(api_key_header or api_key_query)
    if not wallet:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid key or wallet.")
    return WalletTypeInfo(key_type=KeyType.invoice, wallet=wallet)
