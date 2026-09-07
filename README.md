# BingeFinder

A data-science-powered web-series discovery and recommendation platform that helps users find their next binge using content-based Machine Learning, and discover legitimate places to watch them.

---

## Features

- **Smart Search** — Search by title with exact-match priority; ambiguous titles (e.g. "Money Heist") show multiple candidates for the user to pick
- **Content-Based Recommendations** — TF-IDF + cosine similarity + semantic embeddings on summary, genres, cast, and network
- **Personalized Recommendations** — Weighted preference vector from **Like / Love / Not For Me** reactions, watchlist, and recently-viewed history, reranked with an adaptive LinUCB contextual bandit
- **"Why This?" Explanations** — Every recommendation comes with a plain-language reason based on overlapping metadata
- **Where to Watch** — Streaming provider availability via TMDb (Netflix, Prime, etc.) with legitimate "Watch Now" links
- **Watchlist** — Save and manage your personal watchlist (persisted in MongoDB)
- **Like / Love / Not For Me** — Tell us exactly how you feel. NOT FOR ME actively suppresses rejected titles (and similar ones) from your recommendations
- **Surprise Me** — One-click random series pick from the catalog
- **Dynamic Visual Theme** — Cinematic dark themes with smooth transitions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ / FastAPI |
| Frontend | React 19 + Vite + Tailwind CSS |
| Database | MongoDB (via PyMongo) |
| Data Source | MongoDB catalog; TMDb API (watch providers) |
| ML | scikit-learn (TF-IDF), sentence-transformers (embeddings), NumPy |
| Adaptive Ranking | LinUCB contextual bandit |

---

## Architecture

```
MongoDB ──> Data Access Layer ──> FastAPI ──> React SPA
                                      │
                       ┌──────────────┘
                       ▼
                Recommender
    (TF-IDF + semantic embeddings + bandit)
                       │
                       ▼
        Ranked Recommendations + Why-This explanations
```

### Data Model

Each series document in the `series` collection is keyed by a unique `series_id` and stores: name, summary, genres, rating, language, premiere/end dates, status, network/web_channel, cast, and imagery. Per-user collections (`watchlist`, `likes`, `recently_viewed`, `interaction_events`) reference series by `series_id`. The unified `interactions` collection stores one LIKE/LOVE/NOT-FOR-ME reaction per (user, series).

---

## Project Structure

```
BingeFinder/
├── backend/                  # FastAPI application
│   ├── main.py               # App entry point (CORS, routers, lifecycle)
│   ├── routes/               # API route handlers
│   ├── schemas/              # Pydantic request/response models
│   └── services/             # Business logic (discovery, recs, provider, etc.)
├── api/
│   ├── tmdb.py               # TMDb API client
│   └── watch_providers.py    # Watch-provider lookup
├── database/
│   ├── mongo_client.py       # MongoDB persistence layer
│   ├── watchlist.py          # Watchlist operations
│   ├── likes.py              # Like operations
│   ├── interactions.py       # Unified LIKE/LOVE/NOT-FOR-ME reactions
│   ├── recently_viewed.py    # Recently-viewed operations
│   └── interaction_events.py # Reward/event logging for the bandit
├── recommender/
│   ├── preprocess.py         # Content-soup builder
│   ├── build_model.py        # TF-IDF + embeddings model trainer
│   ├── recommend.py          # Recommendation engine
│   ├── adaptive.py           # Adaptive ranking pipeline
│   ├── bandit.py             # LinUCB contextual bandit
│   ├── train_ranker.py       # Ranker training helper
│   ├── embeddings.py         # Semantic embedding helpers
│   └── exceptions.py         # Custom exception hierarchy
├── frontend/                 # React 19 SPA
│   └── src/
│       ├── pages/            # Route pages
│       ├── components/       # Reusable UI components
│       ├── context/          # Auth context
│       └── api/              # API client
├── tests/                    # pytest suite (mongomock)
├── config.py                 # Central configuration
└── requirements.txt          # Python dependencies
```

---

## ML Approach

**Content-Based Filtering using TF-IDF + Semantic Embeddings + Cosine Similarity**

For each series, a "content soup" is built from:
- **Series name** — title included as a primary identifier
- **Summary** — the full synopsis (primary signal)
- **Genres** — repeated 3x for heavier TF-IDF weight
- **Cast names** — top billed actors (limited count)
- **Network/Channel** — broadcaster or streaming platform name

The `TfidfVectorizer` (max_features=20000, English stop words) converts these soups into a sparse matrix, and a sentence-transformer model produces dense semantic embeddings. A weighted combination of cosine similarities scores every series against the query, and the top-N results are returned ranked by genuine relevance score (0.0 to 1.0).

**Personalization + Adaptive Ranking** — A user's reactions, watchlist, and recently-viewed history are weighted (LOVE 5.0 / LIKE 3.0 / watchlist 2.0 / viewed 1.0) into a combined preference vector. NOT FOR ME titles are excluded from recommendations and their genres down-weighted so similar content is pushed lower. Candidate recommendations are then reranked by a **LinUCB contextual bandit** trained on interaction events, so the system continuously adapts to what the user actually engages with.

---

## Search Flow

1. User searches a title in the Discover page
2. The local MongoDB catalog is filtered with exact-match priority
3. If an exact match exists, it appears first
4. If only partial matches exist, they're shown with a notice
5. Results are ranked: exact title > starts-with > contains (so "Money Heist" always surfaces above "Money Heist: Korea")

---

## Where to Watch

Provider availability is fetched from TMDb's watch-provider API:
- Stream (Netflix, Prime, Disney+, etc.)
- Free (ad-supported platforms)
- Rent / Buy (iTunes, Google Play, etc.)
- Falls back to a JustWatch search link when no provider data is available
- Always shows "Watch availability unavailable" instead of fake links when data is missing

---

## Installation

```bash
# Clone the repository
git clone https://github.com/devrana2575/BingeFinder.git
cd BingeFinder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MongoDB URI and TMDb API key
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGODB_URI` | Yes | — | MongoDB connection URI |
| `MONGODB_DATABASE` | Yes | — | MongoDB database name |
| `TMDB_API_KEY` | Yes | — | TMDb API key (for watch providers) |
| `LOG_LEVEL` | No | INFO | Logging verbosity |
| `JWT_SECRET` | No | auto-gen | Secret for session tokens |

---

## How to Run

### 1. MongoDB

Start MongoDB (local default `mongodb://127.0.0.1:27017/`). The `series`, `watchlist`, `likes`, `interactions`, `recently_viewed`, and `interaction_events` collections live in the configured database.

### 2. Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

The API runs at `http://localhost:8000` (docs at `/docs`).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The SPA runs at `http://localhost:5173` and proxies API calls to the backend.

---

## Testing

```bash
# Backend
pytest tests/ -v

# Frontend
cd frontend && npm run build
```

Tests use `mongomock` (in-memory MongoDB) — no live database required.

---

## Model Building

Rebuild the recommendation model (TF-IDF + semantic embeddings) against the current catalog:

```bash
python -m recommender.build_model
```

The model artifact is saved to `recommender/artifacts/` and auto-loads at API startup (auto-rebuilt if stale via `REBUILD_MODEL_TTL_HOURS`).

---

## Catalog Maintenance

The catalog grows via two idempotent, upsert-only ingesters (data is never wiped):

- **TMDb ingest** (needs `TMDB_API_KEY`): incremental pull of TMDb TV list endpoints.

  ```bash
  python -m backend.services.catalog_ingest --pages 3 --enrich
  ```

- **TVMaze backfill** (keyless — no API key required): scans the public TVMaze index and adds quality shows.
  Shows need a name and an image to be included; the `--max-new` cap bounds each run.

  ```bash
  python -m backend.services.tvmaze_backfill --min-weight 25 --max-new 3000
  ```

After growing the catalog, rebuild the recommendation model (above) so newly added titles are recommendable. The live count endpoint (`/api/series/count`) reflects the catalog as-is.

---

## Future Improvements

- Collaborative filtering alongside content-based recommendations
- More granular watch-provider data (season/episode availability)
- Mobile-optimized responsive layout improvements
- Export watchlist functionality

---

## License

This project is for educational purposes.
