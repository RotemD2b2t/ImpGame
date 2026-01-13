# ImpGame

## Deployment (Render) ✅
This repo includes `render.yaml` and is ready for a fast deploy to Render as a Python Web Service.
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn main:app --bind 0.0.0.0:$PORT`

Or run locally for quick testing:
```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 main:app
```

`Procfile` already contains a `web: gunicorn main:app --workers 3 --bind 0.0.0.0:$PORT` entry for Heroku-style platforms.

If you prefer static hosting (Cloudflare Pages), set the build output directory to `static` instead.

## Environment variables (important) ⚠️
For production, set the following environment variables (Render dashboard or your host's env settings):
- `MAIL_USERNAME` — your mail sender address
- `MAIL_PASSWORD` — mail password or app-specific password
- `MAIL_SERVER` — (optional) defaults to `smtp.gmail.com`
- `MAIL_PORT` — (optional) defaults to `587`
- `MAIL_USE_TLS` — set to `True`/`False` (defaults to `True`)
- `SECRET_KEY` — override the `app.secret_key` for session security

Example on Render: add these variables in the service's Environment section before deploying.

