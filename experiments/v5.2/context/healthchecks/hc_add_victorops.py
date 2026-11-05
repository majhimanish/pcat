from __future__ import annotations


from uuid import UUID


from django.contrib.auth.decorators import login_required


from django.http import HttpResponse


from django.shortcuts import redirect, render


from hc.accounts.http import AuthenticatedHttpRequest


from hc.api.models import Channel


from hc.front import forms


from hc.front.decorators import require_setting


from hc.front.views import _get_rw_project_for_user
