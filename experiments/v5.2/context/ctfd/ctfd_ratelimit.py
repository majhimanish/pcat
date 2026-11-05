import functools


from flask import abort, jsonify, redirect, request, url_for


from flask_babel import gettext


from CTFd.cache import cache


from CTFd.utils import config, get_config


from CTFd.utils import user as current_user


from CTFd.utils.config import is_teams_mode


from CTFd.utils.dates import ctf_ended, ctf_started, ctftime, view_after_ctf


from CTFd.utils.user import authed, get_current_team, get_current_user, is_admin


def during_ctf_time_only(*args, **kwargs):
    ...


def require_authentication_if_config(*args, **kwargs):
    ...


def require_verified_emails(*args, **kwargs):
    ...


def authed_only(*args, **kwargs):
    ...


def registered_only(*args, **kwargs):
    ...


def admins_only(*args, **kwargs):
    ...


def require_team(*args, **kwargs):
    ...


def require_complete_profile(*args, **kwargs):
    ...
