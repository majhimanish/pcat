from uuid import UUID
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from hc.accounts.models import Member
from hc.api.models import Channel


def _get_channel_for_user(request: HttpRequest, code: UUID) -> tuple[Channel, bool]:
    """Return specified channel if current user has access to it."""

    assert request.user.is_authenticated

    channel = get_object_or_404(Channel.objects.select_related("project"), code=code)
    if request.user.is_superuser:
        return channel, True

    if request.user.id == channel.project.owner_id:
        return channel, True

    membership = get_object_or_404(Member, project=channel.project, user=request.user)
    return channel, membership.is_rw


def _get_rw_channel_for_user(request: HttpRequest, code: UUID) -> Channel:
    channel, rw = _get_channel_for_user(request, code)
    if not rw:
        raise PermissionDenied

    return channel
