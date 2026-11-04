# Trimmed copy of lnbits/decorators.py (LNbits, MIT) at the v5 pinned commit, with the
# function an agent wrote in v5 (lnbits_invoice_key, pcat condition, samples 1-3: identical).
from fastapi import Request, Security
from fastapi.security import APIKeyHeader, APIKeyQuery, SecurityBase

from lnbits.core.models import KeyType, WalletTypeInfo

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
api_key_query = APIKeyQuery(name="api-key", auto_error=False)


class BaseKeyChecker(SecurityBase):
    def __init__(self, api_key=None, expected_key_type=None):
        self._api_key = api_key
        self.expected_key_type = expected_key_type


class KeyChecker(BaseKeyChecker):
    async def __call__(self, request: Request) -> WalletTypeInfo:
        return await self._check(request)


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


# pcat: auth.require_api_key@v1
async def require_invoice_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    check: KeyChecker = KeyChecker(
        api_key=api_key_header or api_key_query,
        expected_key_type=KeyType.invoice,
    )
    return await check(request)
