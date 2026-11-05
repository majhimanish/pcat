# Releasing pcat

pcat is installed from git today:

```bash
pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"     # or: pip install "…"
```

Extras: `mcp` (needed for `pcat serve`, so for Claude Code), `catalog` (the third-party
libraries the starter patterns import; only needed to run their tests with `pcat
validate`), `dev` (pytest, for working on pcat itself). A team adopting pcat needs `mcp`;
CI needs only the base package for `pcat lint` and `pcat approvals check`.

## Publishing to PyPI (owner's steps; needs the owner's PyPI account)

1. Bump `version` in `pyproject.toml` and `src/pcat/__init__.py`, add a `CHANGELOG.md`
   entry, run the full test matrix, commit, and tag: `git tag v0.1.0 && git push --tags`.
2. Build: `python -m pip install build twine && python -m build` (writes `dist/*.whl`
   and `dist/*.tar.gz`).
3. Check the wheel installs in a fresh virtualenv: `pip install dist/pcat-*.whl` then
   `pcat --version`.
4. Create a PyPI API token (pypi.org → Account settings → API tokens), scoped to the
   `pcat` project after the first upload. The name `pcat` may already be taken on PyPI;
   if so, choose another distribution name (e.g. `pcat-catalog`) in `pyproject.toml`
   and keep the `pcat` command.
5. Upload: `twine upload dist/*` (user `__token__`, password the token). Test first with
   `twine upload --repository testpypi dist/*`.
6. Afterwards the install becomes `pipx install "pcat[mcp]"`; update the README,
   `docs/getting-started.md` and the workflows `pcat init` writes (`PCAT_INSTALL` in
   `src/pcat/initrepo.py`).
