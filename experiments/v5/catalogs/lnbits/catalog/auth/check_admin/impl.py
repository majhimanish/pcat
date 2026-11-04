from http import HTTPStatus
from typing import Annotated
from fastapi import Depends
from fastapi.exceptions import HTTPException
from lnbits.core.models import Account
from lnbits.decorators import check_account_exists
from lnbits.settings import settings


async def check_admin(
    account: Annotated[Account, Depends(check_account_exists)],
) -> Account:
    if (
        account.id != settings.super_user
        and account.id not in settings.lnbits_admin_users
    ):
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "User not authorized. No admin privileges."
        )
    if not account.has_password:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Admin users must have credentials configured."
        )

    return account
