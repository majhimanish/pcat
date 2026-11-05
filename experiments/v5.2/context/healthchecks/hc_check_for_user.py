from __future__ import annotations


import email


import logging


import os


import re


import sqlite3


from collections import Counter, defaultdict


from collections.abc import Iterable


from datetime import datetime


from datetime import timedelta as td


from itertools import islice


from typing import TypedDict, cast


from urllib.parse import urlencode, urlparse


from uuid import UUID


from zoneinfo import ZoneInfo


from cronsim import CronSim


from django.conf import settings


from django.contrib import messages


from django.contrib.auth.decorators import login_required


from django.core.exceptions import PermissionDenied, ValidationError


from django.db.models import BinaryField, Case, Count, F, Q, When


from django.db.models.functions import Substr


from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)


from django.shortcuts import get_object_or_404, redirect, render


from django.template.loader import get_template


from django.urls import reverse


from django.utils.timezone import now


from django.views.decorators.csrf import csrf_exempt


from django.views.decorators.http import require_POST


from django_stubs_ext import WithAnnotations


from oncalendar import OnCalendar, OnCalendarError


from hc.accounts.http import AuthenticatedHttpRequest


from hc.accounts.models import Member, Profile, Project


from hc.api.models import (
    DEFAULT_GRACE,
    DEFAULT_TIMEOUT,
    Channel,
    Check,
    Flip,
    Notification,
    Ping,
    prepare_durations,
)


from hc.front import forms


from hc.front.templatetags.hc_extras import (
    down_title,
    num_down_title,
    site_hostname,
    sortchecks,
    obfuscated_support_email,
)


from hc.front.validators import CronValidator, OnCalendarValidator


from hc.lib.badges import get_badge_url


from hc.lib.string import is_valid_uuid_string


from hc.lib.tz import all_timezones


from hc.lib.urls import absolute_reverse


logger = None


VALID_SORT_VALUES = ("name", "-name", "last_ping", "-last_ping", "created")


STATUS_TEXT_TMPL = None


LAST_PING_TMPL = None


EVENTS_TMPL = None


DOWNTIMES_TMPL = None


def _tags_counts(*args, **kwargs):
    ...


def _common_timezones(*args, **kwargs):
    ...


def _get_channel_for_user(*args, **kwargs):
    ...


def _get_rw_channel_for_user(*args, **kwargs):
    ...


def _get_project_for_user(*args, **kwargs):
    ...


def _get_rw_project_for_user(*args, **kwargs):
    ...


def _refresh_last_active_date(*args, **kwargs):
    ...


def _get_referer_qs(*args, **kwargs):
    ...


def _status_match(*args, **kwargs):
    ...


def checks(*args, **kwargs):
    ...


def status(*args, **kwargs):
    ...


def switch_channel(*args, **kwargs):
    ...


class ProjectStatus:
    ...


def _get_project_summary(*args, **kwargs):
    ...


def index(*args, **kwargs):
    ...


def projects_menu(*args, **kwargs):
    ...


def dashboard(*args, **kwargs):
    ...


def _replace_placeholders(*args, **kwargs):
    ...


def serve_doc(*args, **kwargs):
    ...


def docs_search(*args, **kwargs):
    ...


def docs_cron(*args, **kwargs):
    ...


def add_check(*args, **kwargs):
    ...


def update_name(*args, **kwargs):
    ...


def filtering_rules(*args, **kwargs):
    ...


def update_timeout(*args, **kwargs):
    ...


def cron_preview(*args, **kwargs):
    ...


def oncalendar_preview(*args, **kwargs):
    ...


def validate_schedule(*args, **kwargs):
    ...


def ping_details(*args, **kwargs):
    ...


def ping_body(*args, **kwargs):
    ...


def pause(*args, **kwargs):
    ...


def resume(*args, **kwargs):
    ...


def remove_check(*args, **kwargs):
    ...


def clear_events(*args, **kwargs):
    ...


class PingAnnotations:
    ...


def _get_events(*args, **kwargs):
    ...


def log(*args, **kwargs):
    ...


def _tz_switches(*args, **kwargs):
    ...


def details(*args, **kwargs):
    ...


def uncloak(*args, **kwargs):
    ...


def transfer(*args, **kwargs):
    ...


def copy(*args, **kwargs):
    ...


def status_single(*args, **kwargs):
    ...


def badges(*args, **kwargs):
    ...


def channels(*args, **kwargs):
    ...


def channel_checks(*args, **kwargs):
    ...


def update_channel_name(*args, **kwargs):
    ...


def send_test_notification(*args, **kwargs):
    ...


def remove_channel(*args, **kwargs):
    ...


def edit_channel(*args, **kwargs):
    ...


def log_events(*args, **kwargs):
    ...


def contact_vcf(*args, **kwargs):
    ...
