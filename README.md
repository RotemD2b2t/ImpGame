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
