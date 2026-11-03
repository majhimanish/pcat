`/security-review` needs to run inside a git repository, but the current working directory (`/tmp/pcat-variance-cpcg5l62`) isn't one.

If the repository is in a subdirectory, `cd` into it first and then re-run `/security-review`.

If this is a self-hosted runner session created without a `git_repository` source, do one of these:
- Add a `git_repository` source at session creation, so the runner clones the repo and sets the working directory.
- `cd` into the cloned repo before running the review.
