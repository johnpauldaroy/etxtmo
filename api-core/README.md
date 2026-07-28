# api-core

FastAPI backend for centralized multi-branch TextBlast.

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## Migrations

```bash
alembic upgrade head
```

## Tests

```bash
pytest
```
