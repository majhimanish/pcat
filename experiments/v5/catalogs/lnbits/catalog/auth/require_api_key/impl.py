from fastapi import Request, Security
from lnbits.core.models import KeyType, WalletTypeInfo
from lnbits.decorators import KeyChecker, api_key_header, api_key_query


async def require_admin_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    check: KeyChecker = KeyChecker(
        api_key=api_key_header or api_key_query,
        expected_key_type=KeyType.admin,
    )
    return await check(request)
