from __future__ import annotations


import logging


import time


from datetime import timedelta as td


from urllib.parse import urlparse


from uuid import UUID, uuid4


import pyotp


import segno


from django.conf import settings


from django.contrib import messages


from django.contrib.auth import authenticate, update_session_auth_hash


from django.contrib.auth import login as auth_login


from django.contrib.auth import logout as auth_logout


from django.contrib.auth.decorators import login_required


from django.contrib.auth.models import User


from django.core.signing import BadSignature, SignatureExpired, TimestampSigner


from django.db import transaction


from django.db.models.functions import Lower


from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)


from django.middleware import csrf


from django.shortcuts import get_object_or_404, redirect, render


from django.urls import Resolver404, resolve, reverse


from django.utils.timezone import now


from django.views.decorators.csrf import csrf_exempt


from django.views.decorators.debug import sensitive_post_parameters


from django.views.decorators.http import require_POST


from hc.accounts import forms


from hc.accounts.decorators import require_sudo_mode


from hc.accounts.http import AuthenticatedHttpRequest


from hc.accounts.models import Credential, Member, Profile, Project


from hc.api.models import Channel, Check, TokenBucket


from hc.lib.tz import all_timezones


from hc.lib.webauthn import CreateHelper, GetHelper


from hc.payments.models import Subscription


logger = None


POST_LOGIN_ROUTES = (
    "hc-checks",
    "hc-details",
    "hc-log",
    "hc-channels",
    "hc-add-slack",
    "hc-add-pushover",
    "hc-add-telegram",
    "hc-project-settings",
    "hc-uncloak",
)


def _make_user(*args, **kwargs):
    ...


def _redirect_after_login(*args, **kwargs):
    ...


def _check_2fa(*args, **kwargs):
    ...


def _set_autologin_cookie(*args, **kwargs):
    ...


def login(*args, **kwargs):
    ...


def logout(*args, **kwargs):
    ...


def signup_csrf(*args, **kwargs):
    ...


def signup(*args, **kwargs):
    ...


def login_link_sent(*args, **kwargs):
    ...


def check_token(*args, **kwargs):
    ...


def profile(*args, **kwargs):
    ...


def add_project(*args, **kwargs):
    ...


def project(*args, **kwargs):
    ...


def notifications(*args, **kwargs):
    ...


def set_password(*args, **kwargs):
    ...


def change_email(*args, **kwargs):
    ...


def change_email_verify(*args, **kwargs):
    ...


def unsubscribe_reports(*args, **kwargs):
    ...


def close(*args, **kwargs):
    ...


def remove_project(*args, **kwargs):
    ...


def add_webauthn(*args, **kwargs):
    ...


def add_totp(*args, **kwargs):
    ...


def remove_totp(*args, **kwargs):
    ...


def remove_credential(*args, **kwargs):
    ...


def login_webauthn(*args, **kwargs):
    ...


def login_totp(*args, **kwargs):
    ...


def appearance(*args, **kwargs):
    ...
