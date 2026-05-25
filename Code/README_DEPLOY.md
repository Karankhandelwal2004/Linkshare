# Deployment notes

This app is a FastAPI application intended to run as a long-lived server (ASGI);
Vercel and Netlify are primarily static / serverless platforms and do not run
arbitrary long-running servers directly. Recommended deployment options:

- Container platforms: Render, Fly, Railway, AWS ECS, DigitalOcean App Platform.
- PaaS with Procfile: Heroku, Railway (use `Procfile`).

Included artifacts:

- `Dockerfile` — container image with a healthcheck on `/health`.
- `requirements-lock.txt` — pinned dependencies (generated from the venv).
- `Procfile` — existing entry for Heroku-style deploys.
- `.env.example` — environment variable placeholders (do NOT commit real secrets).

Quick local build with Docker:

```bash
cd Code
docker build -t linkshare:latest .
docker run -p 3000:3000 --env-file .env -d linkshare:latest
```

To deploy on Vercel/Netlify you will need to use a different approach (serverless
functions or an external backend). If you want I can add a serverless adapter
or provide step-by-step instructions for a target provider.
