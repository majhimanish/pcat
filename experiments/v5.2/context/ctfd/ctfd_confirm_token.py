import os


from CTFd.cache import cache


from CTFd.exceptions.email import (
    UserConfirmTokenInvalidException,
    UserResetPasswordTokenInvalidException,
)


from CTFd.utils.encoding import hexencode


def generate_password_reset_token(*args, **kwargs):
    ...


def verify_reset_password_token(*args, **kwargs):
    ...


def remove_reset_password_token(*args, **kwargs):
    ...
