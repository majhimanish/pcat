async def get_account_by_email(
    email: str, active_only: bool = True, conn: Connection | None = None
) -> Account | None:
    if len(email) == 0:
        return None

    return await (conn or db).fetchone(
        """
            SELECT * FROM accounts
            WHERE
                LOWER(email) = :email
                AND (activated = true OR activated = :activated)
        """,
        {"email": email.lower(), "activated": active_only},
        Account,
    )
