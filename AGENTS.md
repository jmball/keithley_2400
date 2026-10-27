# Python development tools

- Use **ty** for type checking and **Ruff** for linting and formatting throughout this project. Do not introduce another type checker, linter, or formatter.
- Keep configuration in `pyproject.toml` and development dependencies in its `dev` group. Update `uv.lock` when dependencies change.
- Install the development environment with `uv sync --locked --extra test`.
- Format changes with `uv run ruff format .`; apply safe lint fixes with `uv run ruff check --fix .` when appropriate.
- Before committing Python changes, run all of:
  - `uv run --locked ty check --error-on-warning`
  - `uv run --locked ruff check .`
  - `uv run --locked ruff format --check .`
  - `uv run --locked pytest -q`
- Check source, tests, and examples. Fix diagnostics rather than disabling rules globally or excluding files merely to make checks pass.
