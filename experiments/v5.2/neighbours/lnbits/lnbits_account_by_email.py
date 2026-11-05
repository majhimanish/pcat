async def get_account_by_login(
    login: str, active_only: bool = True, conn: Connection | None = None
) -> Account | None:
    if len(login) == 0:
        return None

    return await (conn or db).fetchone(
        """
            SELECT * FROM accounts
            WHERE
                (username = :login OR email = :login)
                AND (activated = true OR activated = :activated)
        """,
        {"login": login, "activated": active_only},
        Account,
    )
