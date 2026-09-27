# TypeQuest

TypeQuest is a local typing game for the Design Thinking & Idea Lab. This branch is the presentable Week-1 demonstration build of TypeQuest; ongoing full development continues on `main`.

## Week-1 features

- Local player profiles and saved Classic results
- Classic typing with exactly 20 levels stored in SQLite
- Levels 1–10 unlocked at the start; levels 11–20 unlock at 23 cumulative best stars from levels 1–10
- Live raw WPM, accuracy, and net WPM, with accuracy-based stars
- Pause and focus-loss handling
- Classic Progress page and responsive baseline UI

## Not implemented in this branch

Time Attack, Survival, profile rename/delete/reset, audio or sound effects, and final Week-3/Week-4 polish are not included.

## Technology and offline use

The project uses HTML, CSS, vanilla JavaScript, Flask/Python, and SQLite. The application and its content run locally without external APIs, hosted services, or network assets, so it can be demonstrated offline after dependencies are installed.

## Run on Windows

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt  # only if dependencies are not installed
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser.

This branch stores its local database at `instance/typequest_week1.sqlite3`. It is generated on first run and is gitignored.

## Classic progression

| Levels | Availability |
| --- | --- |
| 1–10 | Unlocked from the start |
| 11–20 | Unlock at 23/30 cumulative best stars from levels 1–10 |

Speed does not affect unlocking.

## Tests

```powershell
python -m unittest discover -s tests -v
node --test tests/classic_js.test.mjs
```

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py` | Flask routes and result validation |
| `database.py` | SQLite setup and queries |
| `progression.py` | Classic tier unlock rules |
| `schema.sql` | Week-1 database schema |
| `seed_content.sql` | Initial Classic level content |
| `templates/` | Flask/Jinja pages |
| `static/` | Local CSS and browser JavaScript |
| `tests/` | Python and JavaScript tests |

## Branches and history

`week1-demo` preserves this demonstration milestone. `main` contains later development, and `v0.1-foundation` remains the earlier historical snapshot.
