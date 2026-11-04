async def check_super_user(
    account: Annotated[Account, Depends(check_admin)],
) -> Account:
    if account.id != settings.super_user:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "User not authorized. No super user privileges."
        )
    if not account.has_password:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Super user must have credentials configured."
        )
    return account
