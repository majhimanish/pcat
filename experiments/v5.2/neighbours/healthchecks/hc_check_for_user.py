def _get_notification_for_user(
    request: HttpRequest, code: UUID
) -> tuple[Notification, bool]:
    """Return specified notification if current user has access to it."""

    assert request.user.is_authenticated

    q = Notification.objects.select_related("owner__project")
    notification = q.get(code=code)
    project = notification.owner.project
    if request.user.is_superuser or request.user.id == project.owner_id:
        return notification, True

    is_rw = Member.objects.filter(
        project=project, user=request.user, role=Member.Role.REGULAR
    ).exists()
    return notification, is_rw
