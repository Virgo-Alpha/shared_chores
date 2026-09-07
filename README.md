# Shared Chores

A Django application for managing shared household chores and one-off tasks.

## Features

- Email-based authentication and one-household membership with roles.
- Household categories with default and custom values.
- Chores and one-off tasks with priorities, due dates, workload points, and assignments.
- Single, joint, any-of, round-robin, and claimable task assignment modes.
- Recurrence rules, overdue occurrences, checklists, completion proof, and approval.
- Personal dashboard, household board, calendar, workload reports, and notifications.
- Optional points and consecutive-day streak tracking.

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

Run the checks and complete test suite with:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

The Django project is in `config/` and the application is in `chores/`.
Database migrations are stored in `chores/migrations/`.
