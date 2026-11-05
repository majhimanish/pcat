from http import HTTPStatus


from typing import Annotated, Literal


import jwt


from fastapi import Cookie, Depends, Query, Request, Security


from fastapi.exceptions import HTTPException


from fastapi.openapi.models import APIKey, APIKeyIn, SecuritySchemeType


from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer, OAuth2PasswordBearer


from fastapi.security.base import SecurityBase


from loguru import logger


from pydantic.types import UUID4


from lnbits.core.crud import (
    get_account,
    get_account_by_email,
    get_account_by_username,
    get_user_active_extensions_ids,
    get_user_from_account,
    get_wallet_for_key,
)


from lnbits.core.crud.users import get_user_access_control_lists


from lnbits.core.crud.wallets import get_base_wallet_for_key


from lnbits.core.db import db


from lnbits.core.models import (
    AccessTokenPayload,
    Account,
    KeyType,
    SimpleStatus,
    User,
    WalletTypeInfo,
)


from lnbits.core.models.users import AccountId, EndpointAccess


from lnbits.core.models.wallets import BaseWallet, BaseWalletTypeInfo


from lnbits.db import Connection, Filter, Filters, TFilterModel


from lnbits.helpers import normalize_path, path_segments, sha256s


from lnbits.settings import AuthMethods, settings


from lnbits.utils.cache import cache


oauth2_scheme = None


http_bearer = None


api_key_header = None


api_key_query = None


class BaseKeyChecker:
    ...


class KeyChecker:
    ...


class LightKeyChecker:
    ...


async def require_admin_key(*args, **kwargs):
    ...


async def require_base_admin_key(*args, **kwargs):
    ...


async def require_base_invoice_key(*args, **kwargs):
    ...


async def check_access_token(*args, **kwargs):
    ...


async def check_account_id_exists(*args, **kwargs):
    ...


async def check_account_exists(*args, **kwargs):
    ...


async def _check_account_exists(*args, **kwargs):
    ...


async def check_user_exists(*args, **kwargs):
    ...


async def optional_user_id(*args, **kwargs):
    ...


async def access_token_payload(*args, **kwargs):
    ...


async def optional_acl_token_payload(*args, **kwargs):
    ...


async def check_api_write_access(*args, **kwargs):
    ...


async def check_admin(*args, **kwargs):
    ...


async def check_super_user(*args, **kwargs):
    ...


def parse_filters(*args, **kwargs):
    ...


async def check_user_extension_access(*args, **kwargs):
    ...


async def _check_user_access(*args, **kwargs):
    ...


async def _check_user_extension_access(*args, **kwargs):
    ...


def _extension_id_from_request_path(*args, **kwargs):
    ...


async def _get_account_from_token(*args, **kwargs):
    ...


def _decode_access_token(*args, **kwargs):
    ...


async def _get_account_from_jwt_payload(*args, **kwargs):
    ...


async def _check_account_api_access(*args, **kwargs):
    ...


def url_for_interceptor(*args, **kwargs):
    ...


async def check_admin_ui(*args, **kwargs):
    ...


async def check_extension_builder(*args, **kwargs):
    ...


async def check_first_install(*args, **kwargs):
    ...


def check_blockexplorer_public(*args, **kwargs):
    ...


async def check_blockexplorer_access(*args, **kwargs):
    ...
