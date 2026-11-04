from lnbits.core.db import db
from lnbits.db import Connection


async def delete_dbversion(*, ext_id: str, conn: Connection | None = None) -> None:
    await (conn or db).execute(
        """
        DELETE FROM dbversions WHERE db = :ext
        """,
        {"ext": ext_id},
    )
