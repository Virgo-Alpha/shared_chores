## Commands

- `uv sync` - install dependencies
- `uv run manage.py runserver` - dev server
- `uv run manage.py migrate` - apply migrations
- `uv run pytest` - the whole suite
- `uv run pytest tests/test_home.py` - one test file

## Rules

- Configuration comes from the environment. A new setting means a new env var
  plus an entry in `.env.example`, never a hardcoded value or a checked-in secret.
- Tests live in `tests/`, named after what they cover. `config/settings_test.py`
  supplies the test environment — production settings stay strict.
- Dependencies are pinned exactly in `pyproject.toml`; run `uv sync` so
  `uv.lock` moves with it. Do not add a dependency without asking.
- Do not edit `_docs/` as a side effect of building something. Changing the
  design is its own deliberate change.
- Commit regularly.
