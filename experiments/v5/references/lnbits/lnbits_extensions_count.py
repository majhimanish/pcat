async def get_installed_extensions_count(conn: Connection | None = None) -> int:
    row: dict | None = await (conn or db).fetchone(
        "SELECT COUNT(*) as count FROM installed_extensions"
    )
    return int(row["count"]) if row else 0
