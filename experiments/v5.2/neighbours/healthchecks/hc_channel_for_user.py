def _get_rw_notification_for_user(request: HttpRequest, code: UUID) -> Notification:
    q = Notification.objects.select_related("owner__project")
    notification = get_object_or_404(q, code=code)
    _get_project_for_user(request, notification.owner.project.code)

    return notification
