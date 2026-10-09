# Contributing

## Set up

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-addons.txt
copy .env.example .env
```

On macOS or Linux use `.venv/bin/python` and `cp`. Put a free Space-Track login in `.env`; it is never committed.

## Before you push

```
.venv\Scripts\python -m pytest -q
```

GitHub runs the same tests on every push and pull request. To check a running server end to end, with a fresh run on live data:

```
.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000
.venv\Scripts\python scripts\check_server.py --run
```

## Where things go

| Change | Place |
|---|---|
| A number that can be tuned, or a path | `fusion/config.py`, with a comment that says what it is for |
| A field on an object, event or plan | `fusion/contracts.py`, then `docs/API.md` |
| A stage of the run | Its module under `fusion/core`, `fusion/risk` or `fusion/maneuver`; `fusion/pipeline.py` only calls the stages in order |
| A route | `fusion/api/main.py`, with a test in `tests/test_api.py` and a row in `docs/API.md` |
| The dashboard | `fusion/api/static/`: `index.html`, `dashboard.css`, `dashboard.js`. No build step and no libraries |
| Something a teammate's pack provides | A hook in `fusion/addons.py` with a fallback, so the main system still runs without the pack |
| A measurement or benchmark | `scripts/` |

The packs in `addons/` belong to their authors and keep their own tests. The main system never imports them directly.

## Conventions

- Every behaviour change comes with a test. Tests in `tests/` run with the packs switched off; `tests/test_teammate_packs.py` is the place for tests that need them.
- Numbers in the README and in `docs/` are measured, with the date and the run they came from. Update them when behaviour changes, or say that they are older.
- Commit messages are one plain sentence saying what changed, with a short body when the reason is not obvious.
- A run folder is never changed after its `DONE` file is written. Anything computed later is stored beside the run's own files.
