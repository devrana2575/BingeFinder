# BingeFinder

A data-science-powered web-series discovery and recommendation platform that helps users find their next binge using content-based Machine Learning, and discover legitimate places to watch them.

---

## Features

- **Smart Search** — Search by title with exact-match priority; ambiguous titles (e.g. "Money Heist") show multiple candidates for the user to pick
- **TVmaze Fallback** — When a title isn't in the local catalog, search TVmaze live and add the series on-demand
- **Content-Based Recommendations** — TF-IDF + cosine similarity on summary, genres, cast, and network
- **"Why This?" Explanations** — Every recommendation comes with a plain-language reason based on overlapping metadata
- **Where to Watch** — Streaming provider availability via TMDb (Netflix, Prime, etc.) with legitimate "Watch Now" links
- **Watchlist** — Save and manage your personal watchlist (persisted in MongoDB)
- **Analytics** — Interactive Plotly charts: genre distribution, ratings, languages, premiere years, networks, and more
- **Surprise Me** — One-click random series pick from the catalog
- **Dynamic Visual Theme** — 6 cinematic dark themes that rotate automatically every 10 seconds with smooth CSS transitions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Frontend | Streamlit |
| Database | MongoDB (via PyMongo) |
| Data Source | TVmaze API (catalog), TMDb API (watch providers) |
| ML | scikit-learn (TF-IDF Vectorizer, Cosine Similarity) |
| Visualization | Plotly |
| Styling | Custom CSS (Sora + Inter fonts, cinematic dark themes) |

---

## Architecture

```
TVmaze API ──> Data Ingestion ──> MongoDB
                                      │
                   ┌──────────────────┘
                   ▼
            Data Access Layer (cached)
                   │
         ┌─────────┼──────────┐
         ▼         ▼          ▼
   Recommender  Analytics  Watchlist
   (TF-IDF)    (Plotly)   (MongoDB)
         │
         ▼
   Cosine Similarity ──> Ranked Recommendations
                                    │
                                    ▼
                            Streamlit UI
```

### Data Flow
1. **Ingestion**: `python -m database.update_mongo` fetches TVmaze catalog pages, enriches each show with cast, and upserts into MongoDB
2. **Model Building**: `python -m recommender.build_model` reads all series, builds a TF-IDF content soup (name + summary + weighted genres + cast + network), and saves a `.joblib` artifact
3. **Serving**: `streamlit run streamlit_app.py` reads MongoDB for browsing and loads the `.joblib` model for recommendations

---

## Project Structure

```
BingeFinder/
├── app.py                     # Backend entry point (TVmaze -> MongoDB sync)
├── streamlit_app.py           # Streamlit UI entry point (page router)
├── config.py                  # Centralized configuration (env vars, paths)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
│
├── api/
│   ├── tvmaze.py              # TVmaze API client (ACTIVE)
│   ├── tmdb.py                # TMDb API client (for watch providers)
│   └── watch_providers.py     # Watch provider lookup + JustWatch fallback
│
├── database/
│   ├── mongo_client.py        # MongoDB persistence (upsert, query)
│   ├── update_mongo.py        # TVmaze -> MongoDB ingestion pipeline
│   └── watchlist.py           # Watchlist MongoDB operations
│
├── recommender/
│   ├── preprocess.py          # Content soup builder (TF-IDF input)
│   ├── build_model.py         # TF-IDF model trainer
│   ├── recommend.py           # Recommendation engine
│   ├── exceptions.py          # Custom exception hierarchy
│   ├── cli.py                 # CLI demo
│   └── artifacts/             # Saved model artifacts
│
├── ui/
│   ├── data_access.py         # Read-only backend wrapper (cached)
│   ├── components.py          # CSS, cards, badges, grids, theme system
│   ├── explain.py             # "Why this?" explanation builder
│   └── vibes.py               # Mood picker + Surprise Me
│
├── utils/
│   └── logger.py              # Centralized logging
│
└── tests/
    ├── conftest.py            # pytest fixtures (mongomock)
    ├── sample_series.py       # Sample series documents
    └── test_recommender.py    # Full test suite
```

---

## ML Approach

**Content-Based Filtering using TF-IDF + Cosine Similarity**

For each series, a "content soup" is built from:
- **Series name** — title included as a primary identifier
- **Summary** — the full synopsis (primary signal)
- **Genres** — repeated 3x for heavier TF-IDF weight
- **Cast names** — top 5 billed actors (collapsed to single tokens)
- **Network/Channel** — broadcaster or streaming platform name

The `TfidfVectorizer` (max_features=20000, English stop words) converts these soups into a sparse matrix. Cosine similarity compares every series against the query series, and the top-N most similar results are returned ranked by genuine similarity score (0.0 to 1.0).

---

## Search Flow

1. User searches a title in the Discover page
2. The local MongoDB catalog is filtered with exact-match priority
3. If an exact match exists, it appears first
4. If only partial matches exist, they're shown with a notice
5. A "Search TVmaze" button appears when no local match is found
6. TVmaze results are ranked: exact title > starts-with > partial
7. For ambiguous titles (e.g. "Money Heist"), multiple candidates are shown for user selection
8. Selected series is stored via the existing upsert logic (never duplicated)

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

# Install dependencies
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
| `TVMAZE_SYNC_PAGES` | No | 15 | Catalog pages to fetch (~250 shows/page) |
| `TVMAZE_CAST_LIMIT` | No | 10 | Max cast members per show |
| `LOG_LEVEL` | No | INFO | Logging verbosity |

---

## How to Run

```bash
# 1. Sync series data from TVmaze into MongoDB
python -m database.update_mongo

# 2. Build the recommendation model
python -m recommender.build_model

# 3. Launch the Streamlit app
streamlit run streamlit_app.py
```

The app opens at `http://localhost:8501`.

---

## Testing

```bash
pytest tests/ -v
```

Tests use `mongomock` (in-memory MongoDB) — no live database required.

---

## Analytics

The Analytics page provides interactive Plotly visualizations:
- Total series count
- Genre distribution (top 15)
- Rating distribution (histogram)
- Language distribution (top 10)
- Series by premiere year
- Status distribution (donut chart)
- Network/channel distribution (top 15)
- Average rating by genre

All charts operate on real MongoDB data and handle missing data gracefully.

---

## How to Deploy

### Streamlit Cloud
1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select the repository and `streamlit_app.py` as the main file
4. Add environment variables in Streamlit's secrets management

### Manual
```bash
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

---

## Future Improvements

- User authentication for shared watchlists
- Collaborative filtering alongside content-based recommendations
- Incremental TVmaze sync (using the updates endpoint)
- More granular watch-provider data (season/episode availability)
- Mobile-optimized responsive layout
- Export watchlist functionality

---

## License

This project is for educational purposes.
