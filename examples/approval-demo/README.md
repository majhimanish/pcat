# Approval demo (v4.1)

`status_client.py` uses the reviewed pattern `http.get_with_retry.requests` (it
keeps the `# pcat: http.get_with_retry.requests@v1` marker) but narrows the retry
to `requests.Timeout`, so connection errors are no longer retried. That is a
high-severity deviation (`PC100`, guard `must_catch`). Like the agents in the v4
feedback run, the author proposed an approval with the function's hash:

```python
# pcat-allow: PC100 #<hash> -- the request says to retry only on timeouts and 5xx responses, ...
```

The approval is **new in this pull request**, so it is a *proposal*: the
`pcat-approvals` check fails and lists it as waiting until an approver from
`.pcat/approvers.yaml` confirms it after the latest commit, with an approving
review or a comment containing `/pcat approve`. Check locally:

```bash
pcat lint examples/approval-demo --changed-since origin/main   # fails: proposal not confirmed
```
