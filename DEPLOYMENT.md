# Deploying BingeFinder

BingeFinder is a **web-series discovery and recommendation app**, not a video
hosting service. "Production-ready" here means the deployment, security,
reliability, observability, and UX foundations are solid - not that it has
Netflix-scale video streaming, DRM, payments, or a multi-region CDN. Those are
separate products and are explicitly out of scope.

The production stack runs directly on a Linux host with `systemd`, `uvicorn`,
and a reverse proxy.

## What is included

- Single-origin deployment: FastAPI serves the built React SPA **and** `/api`
- Login-gated exploration: the SPA redirects guests to `/login`, and catalog,
  discovery, recommendation, watch-provider, event, and library APIs require a
  valid JWT
- Native `systemd` unit template and Caddy reverse-proxy template (`deploy/`)
- Liveness (`/api/health`) and readiness (`/api/ready`, MongoDB ping) probes
- Production hardening: required `JWT_SECRET` and `ALLOWED_HOSTS`, hidden API
  docs, HSTS, CSP, `TrustedHost`, gzip, request IDs, access logs, rate-limited
  auth endpoints
- CI for backend tests + frontend lint/build
- Route-level code splitting, error boundary, loading states, SEO/meta tags,
  PWA manifest, and the required TMDb attribution
- Graceful degradation when TMDb or the recommendation model is unavailable

## Architecture

```
Browser
  |
  v
Caddy / Nginx (TLS termination)
  |
  v
uvicorn + FastAPI  -- serves frontend/dist and /api/*
  |          |
  |          +--> TMDb API (catalog ingest, watch providers)
  v
MongoDB (catalog, users, interactions)
  |
  +--> recommendation_model.joblib (TF-IDF + sentence embeddings)
```

## Authentication model

- **Public:** `/api/auth/login`, `/api/auth/signup`, `/api/regions`,
  `/api/health`, `/api/ready`
- **Protected:** catalog, search, discovery, recommendations, watch providers,
  events, and all user library/settings endpoints
- Guests are redirected by the SPA to `/login`; after login they return to the
  attempted route.
- This is server-side enforcement, not just hidden UI: direct API calls without
  a valid Bearer token receive `401 Authentication required`.

## 1. Server deployment (recommended)

### Prerequisites

- Linux server (Ubuntu 22.04/24.04 or Debian 12 recommended)
- Python 3.11+
- Node.js 20+ (build-time only)
- MongoDB 7 (local service or managed cluster)
- Caddy or Nginx for TLS
- A TMDb v4 **Read Access Token** (optional but recommended):
  <https://www.themoviedb.org/settings/api>
- ~2-4 GB RAM for the API process (PyTorch + sentence-transformers)

### Create the service user and directory

```bash
sudo useradd --system --user-group --create-home --shell /usr/sbin/nologin bingefinder
sudo mkdir -p /opt/bingefinder
sudo chown bingefinder:bingefinder /opt/bingefinder
```

### Get the code

```bash
sudo -u bingefinder git clone <your-repo-url> /opt/bingefinder
# or copy the project there with rsync/scp and chown it to bingefinder
```

### Build the frontend

```bash
cd /opt/bingefinder/frontend
sudo -u bingefinder npm ci
sudo -u bingefinder npm run build
```

The build output is `/opt/bingefinder/frontend/dist`. Rebuild after any
frontend or `index.html` change.

### Create the Python environment

```bash
sudo -u bingefinder python3 -m venv /opt/bingefinder/.venv
sudo -u bingefinder /opt/bingefinder/.venv/bin/pip install --upgrade pip
sudo -u bingefinder /opt/bingefinder/.venv/bin/pip install -r /opt/bingefinder/requirements.txt
```

### Configure the environment

```bash
sudo -u bingefinder cp /opt/bingefinder/.env.example /opt/bingefinder/.env
sudo -u bingefinder nano /opt/bingefinder/.env
sudo chmod 600 /opt/bingefinder/.env
```

Set at minimum:

```dotenv
APP_ENV=production
MONGODB_URI=mongodb://127.0.0.1:27017/
MONGODB_DATABASE=bingefinder
JWT_SECRET=<64-char random hex>
ALLOWED_HOSTS=bingefinder.example.com,www.bingefinder.example.com
TMDB_API_READ_ACCESS_TOKEN=<your TMDb v4 token>
STATIC_DIR=/opt/bingefinder/frontend/dist
WEB_CONCURRENCY=2
FORWARDED_ALLOW_IPS=127.0.0.1
```

Generate the JWT secret with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`JWT_SECRET` and `ALLOWED_HOSTS` are mandatory in production; the API refuses
to start without them. `.env.example` ships with `ALLOWED_HOSTS=localhost,
127.0.0.1` so local production-style testing works before you add a domain.

### Seed the catalog (first run)

A fresh MongoDB database is empty. Run the idempotent ingest commands:

```bash
cd /opt/bingefinder

# Web-series sweep (TMDb). --pages 3 is a quick smoke seed; omit it for a
# larger sweep.
sudo -u bingefinder bash -c \
  'set -a; . ./.env; set +a; .venv/bin/python -m backend.services.web_series_ingest --pages 3'

# Optional: incremental TMDb catalog update with detail enrichment
sudo -u bingefinder bash -c \
  'set -a; . ./.env; set +a; .venv/bin/python -m backend.services.catalog_ingest --pages 3 --enrich'

# Build/refresh the recommendation model against the new catalog
sudo -u bingefinder bash -c \
  'set -a; . ./.env; set +a; .venv/bin/python -m recommender.build_model'
```

Ingest is upsert-only and never wipes existing data, so all commands are safe
to re-run. After a catalog change, rebuild the model and restart the API.

### Install the systemd service

```bash
sudo cp /opt/bingefinder/deploy/bingefinder.service.example \
  /etc/systemd/system/bingefinder.service
sudo systemctl daemon-reload
sudo systemctl enable --now bingefinder
sudo systemctl status bingefinder
```

The unit assumes `/opt/bingefinder`; adjust `User`, `WorkingDirectory`,
`EnvironmentFile`, `ExecStart`, and `ReadWritePaths` if you use another path.
It runs two uvicorn workers and only grants write access to the model
directory.

Check the probes:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/ready
```

### Put TLS in front

Caddy (automatic HTTPS):

```bash
sudo cp /opt/bingefinder/deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile   # replace domain and email
sudo systemctl reload caddy
```

Nginx equivalent:

```nginx
server {
    listen 443 ssl http2;
    server_name bingefinder.example.com;

    # ssl_certificate ...;
    # ssl_certificate_key ...;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The proxy connects from loopback, matching the default
`FORWARDED_ALLOW_IPS=127.0.0.1`. Do not publish the uvicorn port directly to
the internet.

Also update the placeholder canonical/Open Graph domain in
`frontend/index.html` (`https://bingefinder.app/`) to your real domain, then
rebuild the frontend.

## 2. Local development

```bash
# MongoDB on a non-default port (example)
mongod --dbpath ./.mongo-data --port 27018 --bind_ip 127.0.0.1

# Backend (Linux/macOS)
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Backend (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm ci
npm run dev        # http://localhost:5174
```

Vite proxies `/api` to `http://localhost:8000`. In development, API docs are
available at `/docs`, CORS defaults to the common localhost ports, and
`JWT_SECRET` may be omitted (a per-process dev secret is generated).
`ALLOWED_HOSTS` is not required in development.

## 3. Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `APP_ENV` | No | `development` | `production` enables strict security and disables docs |
| `JWT_SECRET` | **Prod** | random (dev only) | Signs access tokens; rotating it logs everyone out |
| `MONGODB_URI` | Yes | - | Mongo connection string |
| `MONGODB_DATABASE` | Yes | - | Database name |
| `TMDB_API_READ_ACCESS_TOKEN` | Recommended | - | TMDb v4 Bearer token for ingest/watch providers |
| `TMDB_API_KEY` | No | - | Legacy v3 key fallback |
| `ALLOWED_HOSTS` | **Prod** | `localhost,127.0.0.1` in `.env.example` | Comma-separated hostnames for `TrustedHostMiddleware` |
| `CORS_ORIGINS` | No | dev localhosts / empty in prod | Comma-separated origins; empty = same-origin only |
| `STATIC_DIR` | No | `frontend/dist` | Built SPA directory |
| `WEB_CONCURRENCY` | No | `2` in the systemd unit | Uvicorn worker count (pass `--workers`) |
| `FORWARDED_ALLOW_IPS` | Behind proxy | `127.0.0.1` | Which proxy IPs may set `X-Forwarded-*` |
| `LOG_LEVEL` | No | `INFO` | Python log level |
| `BCRYPT_ROUNDS` | No | `12` | Password hashing cost |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `REBUILD_MODEL_TTL_HOURS` | No | `24` | Staleness window for auto-rebuild |

## 4. Health, logs, and observability

- `GET /api/health` - liveness; always fast, no dependencies
- `GET /api/ready` - readiness; pings MongoDB, returns `503` if unavailable
- Every response includes `X-Request-ID` and `X-Response-Time`
- API requests are access-logged with method, path, status, latency, request ID
- `/docs` and `/openapi.json` are disabled when `APP_ENV=production`

Logs go to stdout/stderr and are captured by journald:

```bash
sudo journalctl -u bingefinder -f
```

For incident response, ship journald logs to your platform's log aggregator and
map `/api/ready` to the load balancer's health check.

## 5. Scaling notes

- The API is stateless (JWT sessions), so scale horizontally with replicas
  behind a load balancer.
- Auth rate limiting is currently **in-process per worker**. For strict
  cross-instance limits, put a shared store (Redis) behind the limiter.
- The catalog snapshot is cached in-process for 120 seconds per worker.
- The recommendation model is loaded/warmed per worker. More workers mean more
  RAM; size accordingly.
- MongoDB is the only stateful dependency. Use a managed replica set for HA and
  point `MONGODB_URI` at it; the app creates its indexes on startup.
- Rebuild the frontend on the build host, then deploy `frontend/dist` with the
  API release.

## 6. Backups

Back up MongoDB on a schedule:

```bash
# Dump
mongodump --uri="$MONGODB_URI" \
  --archive="/var/backups/bingefinder-$(date +%F).gz" --gzip

# Restore (destructive)
mongorestore --uri="$MONGODB_URI" \
  --archive="/var/backups/bingefinder-2026-01-01.gz" --gzip --drop
```

The model can always be rebuilt with `python -m recommender.build_model`, so
backing up `recommender/artifacts` is optional. Test a restore periodically.

## 7. CI

`.github/workflows/ci.yml` runs on pushes and pull requests:

- Backend: installs CPU PyTorch + requirements, runs `pytest -q`
- Frontend: `npm ci`, `npm run lint`, `npm run build`

`tests/test_api_endpoints.py` exercises the real catalog artifact. It skips
automatically in a bare checkout where `recommender/artifacts/` is empty; build
the model locally to run it. The model-building suites still run in CI.

## 8. Security checklist

- [ ] `APP_ENV=production`
- [ ] Strong random `JWT_SECRET` (never committed)
- [ ] `ALLOWED_HOSTS` set to real hostname(s)
- [ ] `CORS_ORIGINS` empty for single-origin, or explicitly restricted
- [ ] TLS terminated at the proxy; uvicorn bound to `127.0.0.1`
- [ ] MongoDB bound to loopback/firewalled, not publicly exposed
- [ ] `.env` owned by the service user and mode `600`
- [ ] TMDb token treated as a secret
- [ ] Backups scheduled and restore tested
- [ ] Canonical/OG URLs updated to the real domain
- [ ] Journald retention/aggregation configured

## 9. TMDb attribution (required)

BingeFinder uses the TMDb API. The footer displays:

> This product uses the TMDb API but is not endorsed or certified by TMDb.

Do not remove it. See the
[TMDb attribution requirements](https://www.themoviedb.org/documentation/api/terms-of-use).

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| API exits: `JWT_SECRET must be set in production` | Set `JWT_SECRET` in `.env` |
| API exits: `ALLOWED_HOSTS must be set in production` | Set `ALLOWED_HOSTS` to your hostname(s) |
| `/api/ready` returns 503 | MongoDB not reachable; check `systemctl status mongod` / URI |
| Recommendations empty | Model missing/stale; run `python -m recommender.build_model` and restart |
| Where to Watch is empty | TMDb token missing/invalid, or TMDb unreachable |
| 400 `Invalid host header` | Add the hostname to `ALLOWED_HOSTS` |
| Permission denied writing the model | Check ownership of `recommender/artifacts` and `ReadWritePaths` |
| Frontend route returns API 404 | Build `frontend/dist` or set `STATIC_DIR` correctly |
