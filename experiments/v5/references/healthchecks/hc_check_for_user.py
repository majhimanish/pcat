def _get_check_for_user(
    request: HttpRequest, code: UUID, preload_owner_profile: bool = False
) -> tuple[Check, bool]:
    """Return specified check if current user has access to it.

    If `preload_owner_profile` is `True`, the returned check's
    project.owner.profile will be already loaded. This helps avoid extra SQL queries
    if the caller later looks up the project owner's check_limit or ping_log_limit.

    """

    assert request.user.is_authenticated

    q = Check.objects.select_related("project")
    if preload_owner_profile:
        q = q.select_related("project__owner__profile")

    check = get_object_or_404(q, code=code)
    if request.user.is_superuser:
        return check, True

    if request.user.id == check.project.owner_id:
        return check, True

    membership = get_object_or_404(Member, project=check.project, user=request.user)
    return check, membership.is_rw

def _get_rw_check_for_user(request: HttpRequest, code: UUID) -> Check:
    check, rw = _get_check_for_user(request, code)
    if not rw:
        raise PermissionDenied

    return check
