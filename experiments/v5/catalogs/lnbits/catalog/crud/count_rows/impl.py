from lnbits.core.db import db
from lnbits.db import Connection


async def get_accounts_count(conn: Connection | None = None) -> int:
    row: dict | None = await (conn or db).fetchone(
        "SELECT COUNT(*) as count FROM accounts"
    )
    return int(row["count"]) if row else 0
