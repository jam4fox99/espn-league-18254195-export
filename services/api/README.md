# MyGM API

FastAPI backend contract for the ESPN private alpha.

## Run

```bash
uv run uvicorn mygm_api.main:app --reload
```

## Test

```bash
uv run pytest -q
uv run ruff check .
uv run basedpyright
```
