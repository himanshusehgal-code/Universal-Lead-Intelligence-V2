# Deployment Guide

## Local deployment

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## Render

The repository includes `render.yaml` with a Python web service, health-check path and persistent disk for the saved model.

1. Push the project to a Git repository.
2. Create a new Render Blueprint or web service from that repository.
3. Confirm the persistent disk is mounted at `/opt/render/project/src/data`.
4. Deploy and inspect build/runtime logs.
5. Test `/health`, `/docs` and a small CSV training request.

## Environment variables

| Variable | Default / example | Purpose |
|---|---|---|
| `MODEL_DIR` | `data` locally | Directory where the serialized model is stored |
| `MAX_UPLOAD_ROWS` | documented placeholder | Reserved for future configurable upload limit; V1 currently uses a fixed limit in code |

Do not deploy the unauthenticated V1 publicly with real customer data. Add authentication, tenant separation, request limits and privacy controls first.
