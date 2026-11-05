from datetime import datetime, timezone


from time import time


from typing import Any


from uuid import uuid4


from lnbits.core.crud.extensions import get_user_active_extensions_ids


from lnbits.core.crud.wallets import (
    clear_wallet_cache,
    create_wallet,
    get_standalone_wallet,
    get_wallets,
)


from lnbits.core.db import db


from lnbits.core.models import UserAcls


from lnbits.db import Connection, Filters, Page


from lnbits.helpers import sha256s


from lnbits.utils.cache import cache


from ..models import (
    Account,
    AccountFilters,
    AccountOverview,
    User,
)


async def create_account(*args, **kwargs):
    ...


async def get_accounts_count(*args, **kwargs):
    ...


async def update_account(*args, **kwargs):
    ...


async def delete_account(*args, **kwargs):
    ...


async def get_accounts(*args, **kwargs):
    ...


async def get_account(*args, **kwargs):
    ...


async def delete_accounts_no_wallets(*args, **kwargs):
    ...


async def get_account_by_username(*args, **kwargs):
    ...


async def get_account_by_pubkey(*args, **kwargs):
    ...


async def get_account_by_username_or_email(*args, **kwargs):
    ...


async def get_user(*args, **kwargs):
    ...


async def get_user_from_account(*args, **kwargs):
    ...


async def update_user_access_control_list(*args, **kwargs):
    ...


async def get_user_access_control_lists(*args, **kwargs):
    ...


async def clear_user_id_cache(*args, **kwargs):
    ...


def clear_user_cache(*args, **kwargs):
    ...
