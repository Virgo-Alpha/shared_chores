# Shared Chores

A Django application for managing shared household chores and one-off tasks.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Debian or Ubuntu, install `python3.12-venv` first if creating the virtual
environment reports that `ensurepip` is unavailable.

## Development

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

The Django project is in `config/` and the application is in `chores/`.
