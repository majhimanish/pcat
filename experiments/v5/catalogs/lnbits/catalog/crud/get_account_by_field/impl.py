from lnbits.core.db import db
from lnbits.db import Connection
from lnbits.core.models import Account


async def get_account_by_username(
    username: str, active_only: bool = True, conn: Connection | None = None
) -> Account | None:
    if len(username) == 0:
        return None

    return await (conn or db).fetchone(
        """
            SELECT * FROM accounts
            WHERE
                LOWER(username) = :username
                AND (activated = true OR activated = :activated)
        """,
        {"username": username.lower(), "activated": active_only},
        Account,
    )
