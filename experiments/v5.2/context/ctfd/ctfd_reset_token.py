import os


from CTFd.cache import cache


from CTFd.exceptions.email import (
    UserConfirmTokenInvalidException,
    UserResetPasswordTokenInvalidException,
)


from CTFd.utils.encoding import hexencode


def generate_email_confirm_token(*args, **kwargs):
    ...


def verify_email_confirm_token(*args, **kwargs):
    ...


def remove_email_confirm_token(*args, **kwargs):
    ...
