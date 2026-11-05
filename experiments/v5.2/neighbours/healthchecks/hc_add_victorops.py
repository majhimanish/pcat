@require_setting("VICTOROPS_ENABLED")
@login_required
def add_splunk_oncall(request: AuthenticatedHttpRequest, code: UUID) -> HttpResponse:
    project = _get_rw_project_for_user(request, code)

    if request.method == "POST":
        channel = Channel(project=project, kind="victorops")
        channel.value = request.POST.get("value", "")
        channel.save()

        channel.assign_all_checks()
        return redirect("hc-channels", project.code)

    ctx = {"page": "channels", "project": project, "form": forms.AddUrlForm()}
    return render(request, "add_victorops.html", ctx)
