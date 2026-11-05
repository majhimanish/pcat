@require_setting("VICTOROPS_ENABLED")
@login_required
def add(request: AuthenticatedHttpRequest, code: UUID) -> HttpResponse:
    project = _get_rw_project_for_user(request, code)

    if request.method == "POST":
        form = forms.AddUrlForm(request.POST)
        if form.is_valid():
            channel = Channel(project=project, kind="victorops")
            channel.value = form.cleaned_data["value"]
            channel.save()

            channel.assign_all_checks()
            return redirect("hc-channels", project.code)
    else:
        form = forms.AddUrlForm()

    ctx = {"page": "channels", "project": project, "form": form}
    return render(request, "add_victorops.html", ctx)
