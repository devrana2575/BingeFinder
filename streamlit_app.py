"""
streamlit_app.py
===================
Phase 4 — Streamlit UI for BingeFinder.

Turns the existing Phase 2 (TVmaze -> MongoDB) and Phase 3 (TF-IDF +
cosine similarity recommender) backends into a browsable web app:

    Home -> Search/Discover -> Series Details -> Find Similar
         -> Recommendations -> Open Recommended Series

Nothing here writes to MongoDB or touches the recommendation algorithm;
it only reads through `ui/data_access.py`, which itself only calls the
existing `database.mongo_client` and `recommender.recommend` modules.

Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui import data_access as da
from ui import explain, vibes
from ui.components import (
    inject_global_css,
    inject_theme_rotator,
    render_series_grid,
    render_tvmaze_candidates,
    rating_badge_html,
    genre_tags_html,
    hero_html,
    section_header,
)

st.set_page_config(
    page_title="BingeFinder",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state / navigation
# ---------------------------------------------------------------------------

DEFAULTS = {
    "page": "home",
    "selected_series_id": None,
    "rec_source_id": None,
    "discover_query": "",
    "tvmaze_candidates": None,
    "tvmaze_candidates_query": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go_home() -> None:
    st.session_state.page = "home"
    st.rerun()


def go_discover(query: str = "") -> None:
    st.session_state.page = "discover"
    st.session_state.discover_query = query
    st.rerun()


def go_details(series_id: Optional[int]) -> None:
    if series_id is None:
        st.warning("That series is missing an id and can't be opened.")
        return
    st.session_state.page = "details"
    st.session_state.selected_series_id = series_id
    st.rerun()


def go_recommendations(series_id: Optional[int]) -> None:
    if series_id is None:
        st.warning("That series is missing an id — can't find similar titles.")
        return
    st.session_state.page = "recommendations"
    st.session_state.rec_source_id = series_id
    st.rerun()


def go_surprise() -> None:
    """Surprise Me: pick a real series from the existing MongoDB catalog and open it."""
    docs, err = da.load_all_series()
    if err:
        st.error(f"⚠️ {err}")
        return
    if not docs:
        st.info("The series database is empty. Run the Phase 2 sync (`python -m database.update_mongo`) first.")
        return
    pick = vibes.pick_surprise(docs)
    if pick is None:
        st.warning("Couldn't find a series to shuffle to yet.")
        return
    go_details(pick.get("tvmaze_id"))


def go_watchlist() -> None:
    st.session_state.page = "watchlist"
    st.rerun()


def go_analytics() -> None:
    st.session_state.page = "analytics"
    st.rerun()


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def _get_watchlist_manager():
    """Return a WatchlistManager (or None with an error message)."""
    try:
        from database.mongo_client import MongoDatabaseError, MongoDBManager
        from database.watchlist import WatchlistManager
        manager = MongoDBManager()
        return WatchlistManager(manager), None, manager
    except Exception as exc:
        return None, f"Watchlist unavailable: {exc}", None


def _is_in_watchlist(tvmaze_id: int) -> bool:
    """Check if a series is in the watchlist (never crashes)."""
    try:
        wl, err, mgr = _get_watchlist_manager()
        if err or wl is None:
            return False
        return wl.is_in_watchlist(tvmaze_id)
    except Exception:
        return False
    finally:
        try:
            mgr.close()
        except Exception:
            pass


def save_to_watchlist(tvmaze_id: int) -> str:
    """Add a series to the watchlist. Returns 'added', 'already_exists', or error msg."""
    try:
        wl, err, mgr = _get_watchlist_manager()
        if err:
            return err
        result = wl.add_to_watchlist(tvmaze_id)
        return result
    except Exception as exc:
        return f"Error: {exc}"
    finally:
        try:
            mgr.close()
        except Exception:
            pass


def remove_from_watchlist(tvmaze_id: int) -> str:
    """Remove a series from the watchlist. Returns 'removed', 'not_found', or error msg."""
    try:
        wl, err, mgr = _get_watchlist_manager()
        if err:
            return err
        result = wl.remove_from_watchlist(tvmaze_id)
        return result
    except Exception as exc:
        return f"Error: {exc}"
    finally:
        try:
            mgr.close()
        except Exception:
            pass


def _get_watchlist_ids() -> list:
    """Return list of tvmaze_ids in the watchlist."""
    try:
        wl, err, mgr = _get_watchlist_manager()
        if err or wl is None:
            return []
        items = wl.get_watchlist()
        return [item.get("tvmaze_id") for item in items if item.get("tvmaze_id") is not None]
    except Exception:
        return []
    finally:
        try:
            mgr.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Watch providers helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner="Looking up watch providers...")
def _cached_watch_providers(tvmaze_id: int, imdb_id: Optional[str]) -> dict:
    """Cached wrapper around get_watch_providers_for_series."""
    try:
        from api.watch_providers import get_watch_providers_for_series
        return get_watch_providers_for_series(tvmaze_id, imdb_id=imdb_id)
    except Exception:
        return {}


def _render_watch_providers(doc: dict) -> None:
    """Render the Where to Watch section for a series."""
    st.markdown("---")
    st.subheader("📺 Where to Watch")

    series_name = doc.get("name") or ""
    tvmaze_id = doc.get("tvmaze_id")
    imdb_id = doc.get("imdb_id")

    providers_data = _cached_watch_providers(tvmaze_id, imdb_id)

    if not providers_data or not providers_data.get("providers"):
        justwatch_url = None
        try:
            from api.watch_providers import get_provider_page_url
            justwatch_url = get_provider_page_url(series_name)
        except Exception:
            pass
        st.info("Watch availability unavailable for this series.")
        if justwatch_url:
            st.markdown(f"🔗 [Check JustWatch for availability]({justwatch_url})")
        return

    providers = providers_data["providers"]
    region = providers_data.get("region", "US")
    tmdb_link = providers_data.get("link", "")

    type_labels = {
        "flatrate": ("Stream", "🟢"),
        "free": ("Free", "🆓"),
        "rent": ("Rent", "🏷️"),
        "buy": ("Buy", "🛒"),
    }

    has_any = False
    for ptype, type_key in [("flatrate", "Stream"), ("free", "Free"), ("rent", "Rent"), ("buy", "Buy")]:
        items = providers.get(ptype) or []
        if not items:
            continue
        has_any = True
        label, emoji = type_labels.get(ptype, (type_key, "📺"))
        st.markdown(f"**{emoji} {label}**")
        cols = st.columns(min(4, len(items)))
        for idx, provider in enumerate(items):
            with cols[idx % len(cols)]:
                pname = provider.get("provider_name", "Unknown")
                logo = provider.get("logo_path")
                if logo:
                    logo_url = f"https://image.tmdb.org/t/p/original{logo}"
                    st.image(logo_url, width=40)
                st.caption(pname)

    if not has_any:
        st.info("No streaming providers found for your region.")
        justwatch_url = None
        try:
            from api.watch_providers import get_provider_page_url
            justwatch_url = get_provider_page_url(series_name)
        except Exception:
            pass
        if justwatch_url:
            st.markdown(f"🔗 [Check JustWatch for availability]({justwatch_url})")
        return

    if tmdb_link:
        st.markdown(f"🔗 [View on TMDb]({tmdb_link})")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div style="padding:0.4rem 0 0.2rem 0;">'
            '<span class="bf-logo-text">🎬 BingeFinder</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Find your next binge ✨")
        st.divider()

        if st.button("🏠  Home", use_container_width=True):
            go_home()
        if st.button("🔎  Discover", use_container_width=True):
            go_discover()
        if st.button("🎲  Surprise Me", use_container_width=True, help="Jump to a random series from the catalog"):
            go_surprise()
        if st.button("📊  Analytics", use_container_width=True, help="Catalog analytics & charts"):
            go_analytics()
        if st.button("❤️  Watchlist", use_container_width=True, help="Your saved series"):
            go_watchlist()

        st.divider()
        docs, err = da.load_all_series()
        if err:
            st.error("Database unavailable.")
        else:
            st.metric("Series in catalog", len(docs))
        if st.button("↻ Refresh data", use_container_width=True, help="Re-read the latest data from MongoDB"):
            da.load_all_series.clear()
            st.rerun()


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------

def render_home() -> None:
    docs, err = da.load_all_series()

    st.markdown(hero_html(series_count=len(docs) if not err else 0), unsafe_allow_html=True)

    with st.form("home_search_form"):
        cols = st.columns([5, 1.3])
        query = cols[0].text_input(
            "Search", placeholder="🔍  Search by title, e.g. 'Money Heist'", label_visibility="collapsed"
        )
        submitted = cols[1].form_submit_button("Search", use_container_width=True, type="primary")
    if submitted:
        go_discover(query)

    st.write("")
    if st.button("🎲  Surprise Me", key="home_shuffle", use_container_width=True, type="primary"):
        go_surprise()

    if err:
        st.error(f"⚠️ {err}")
        return
    if not docs:
        st.info("The series database is empty. Run the Phase 2 sync (`python -m database.update_mongo`) first.")
        return

    # -----------------------------------------------------------------
    # POPULAR / TRENDING
    # -----------------------------------------------------------------
    section_header("🔥", "Popular & Trending", "Currently airing and highly ranked, right now")
    trending = da.get_trending_series(docs)
    popular_trending = trending if trending else da.get_popular_series(docs)
    if popular_trending:
        render_series_grid(popular_trending, key_prefix="home_trend", on_open=go_details)
    else:
        st.caption("Not enough data yet — try Discover instead.")

    # -----------------------------------------------------------------
    # RECOMMENDED
    # -----------------------------------------------------------------
    section_header("🎯", "Recommended For You", "Top-rated picks from the catalog")
    recommended = da.get_featured_series(docs)
    if recommended:
        render_series_grid(recommended, key_prefix="home_rec", on_open=go_details)
    else:
        st.caption("No rated series in the catalog yet.")

    # -----------------------------------------------------------------
    # HIDDEN GEMS
    # -----------------------------------------------------------------
    section_header("💎", "Hidden Gems", "Underrated finds — lower weight, but top-notch ratings")
    try:
        gems = da.get_hidden_gems(docs)
    except (AttributeError, Exception):
        gems = da.get_featured_series(docs, limit=8)
    if gems:
        render_series_grid(gems, key_prefix="home_gems", on_open=go_details)
    else:
        st.caption("Not enough rated series to find hidden gems yet.")


# ---------------------------------------------------------------------------
# DISCOVER
# ---------------------------------------------------------------------------

def render_discover() -> None:
    st.markdown(
        '<h1 style="font-family:Sora,sans-serif;font-weight:800;">🔎 Discover Series</h1>'
        '<p style="color:#9A9AAE;margin-top:-0.6rem;">Search the full catalog, or narrow it down with filters.</p>',
        unsafe_allow_html=True,
    )

    docs, err = da.load_all_series()
    if err:
        st.error(f"⚠️ {err}")
        return
    if not docs:
        st.info("The series database is empty. Run the Phase 2 sync (`python -m database.update_mongo`) first.")
        return

    options = da.get_filter_options(docs)

    query = st.text_input(
        "Search by title", value=st.session_state.discover_query, placeholder="🔍  Search by title..."
    )

    with st.expander("⚙️  Filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        genres = c1.multiselect("Genre", options["genres"])
        language = c2.selectbox("Language", ["Any"] + options["languages"])
        year = c3.selectbox("Year", ["Any"] + options["years"])
        status = c4.selectbox("Status", ["Any"] + options["statuses"])
        min_rating = st.slider("Minimum rating", 0.0, 10.0, 0.0, 0.5)

    filtered = da.filter_series(
        docs,
        query=query,
        genres=genres or None,
        min_rating=min_rating,
        language=None if language == "Any" else language,
        year=None if year == "Any" else year,
        status=None if status == "Any" else status,
    )

    active_filters = bool(genres) or language != "Any" or year != "Any" or status != "Any" or min_rating > 0 or query
    filter_chip = '<span class="bf-tag">Filters active</span>' if active_filters else ""
    st.markdown(
        f'<div class="bf-badge-row" style="margin:0.8rem 0 1.2rem 0;">'
        f'<span class="bf-sim-badge">🎬 {len(filtered)} of {len(docs)} series</span>'
        f"{filter_chip}</div>",
        unsafe_allow_html=True,
    )

    no_filters_active = not (genres or (language != "Any") or (year != "Any") or (status != "Any") or min_rating > 0)

    q_norm = query.strip().lower()
    exact_local_match = any((d.get("name") or "").strip().lower() == q_norm for d in filtered) if q_norm else True

    if q_norm and no_filters_active and not exact_local_match:
        if filtered:
            st.info(f'No exact match for "{query}" in the catalog — showing partial matches below.')
        else:
            st.info(f'No series matching "{query}" in the catalog yet.')
        if st.button(f'🔍  Search TVmaze for "{query}"', key="tvmaze_live_search"):
            with st.spinner(f'Searching TVmaze for "{query}"...'):
                candidates, search_err = da.search_tvmaze(query)
            if search_err:
                st.warning(search_err)
                st.session_state.tvmaze_candidates = None
            else:
                exact = [c for c in candidates if (c.get("name") or "").strip().lower() == query.strip().lower()]
                if len(exact) == 1:
                    with st.spinner(f'Adding "{exact[0]["name"]}"...'):
                        new_doc, add_err = da.add_series_from_tvmaze(exact[0]["show"])
                    if add_err:
                        st.warning(add_err)
                    else:
                        st.session_state.tvmaze_candidates = None
                        go_details(new_doc.get("tvmaze_id"))
                else:
                    st.session_state.tvmaze_candidates = candidates
                    st.session_state.tvmaze_candidates_query = query
                    st.rerun()

    if (
        st.session_state.tvmaze_candidates
        and st.session_state.tvmaze_candidates_query == query
        and no_filters_active
    ):
        picked = render_tvmaze_candidates(st.session_state.tvmaze_candidates, key_prefix="tvmaze_pick")
        if picked is not None:
            with st.spinner(f'Adding "{picked.get("name")}"...'):
                new_doc, add_err = da.add_series_from_tvmaze(picked["show"])
            if add_err:
                st.warning(add_err)
            else:
                st.session_state.tvmaze_candidates = None
                go_details(new_doc.get("tvmaze_id"))

    page_size = 24
    shown = st.session_state.get("discover_shown", page_size)
    render_series_grid(filtered[:shown], key_prefix="disc", on_open=go_details)

    if shown < len(filtered):
        if st.button("Show more"):
            st.session_state.discover_shown = shown + page_size
            st.rerun()
    elif "discover_shown" in st.session_state:
        st.session_state.discover_shown = page_size


# ---------------------------------------------------------------------------
# SERIES DETAILS
# ---------------------------------------------------------------------------

def _channel_name(channel_obj) -> Optional[str]:
    if isinstance(channel_obj, dict):
        return channel_obj.get("name")
    return None


def render_details() -> None:
    series_id = st.session_state.selected_series_id
    if series_id is None:
        st.info("No series selected yet. Head to Discover to pick one.")
        if st.button("Go to Discover"):
            go_discover()
        return

    doc, err = da.get_series_by_id(series_id)
    if err:
        st.error(f"⚠️ {err}")
        if st.button("Back to Discover"):
            go_discover()
        return

    if st.button("← Back"):
        go_discover(st.session_state.discover_query)

    left, right = st.columns([1, 2], gap="large")
    with left:
        image_url = doc.get("image_original") or doc.get("image_medium")
        if image_url:
            st.image(image_url, use_container_width=True)
        else:
            st.markdown(
                '<div class="bf-detail-poster-placeholder">'
                '<span class="emoji">🎬</span>No poster available</div>',
                unsafe_allow_html=True,
            )

    with right:
        status = doc.get("status")
        status_chip = f'<span class="bf-tag">📺 {status}</span>' if status else ""
        st.markdown(
            f'<div style="font-family:Sora,sans-serif;font-weight:800;font-size:2.1rem;'
            f'line-height:1.15;margin-bottom:0.5rem;">{doc.get("name") or "Untitled Series"}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="bf-chip-row">{rating_badge_html(doc.get("rating"))}{status_chip}'
            f'{genre_tags_html(doc.get("genres"), limit=10)}</div>',
            unsafe_allow_html=True,
        )

        summary = doc.get("summary")
        st.markdown(
            f'<p style="font-size:1rem;line-height:1.6;color:#D8D8E2;">'
            f'{summary if summary else "<i>No summary available for this series.</i>"}</p>',
            unsafe_allow_html=True,
        )

        st.write("")
        meta_cols = st.columns(2)
        runtime = doc.get("runtime") or doc.get("average_runtime")
        channel = _channel_name(doc.get("network")) or _channel_name(doc.get("web_channel"))
        with meta_cols[0]:
            st.markdown(
                '<div class="bf-meta-card">'
                f'<b>Language</b><p>{doc.get("language") or "Unknown"}</p></div>',
                unsafe_allow_html=True,
            )
            st.write("")
            st.markdown(
                '<div class="bf-meta-card">'
                f'<b>Premiered</b><p>{doc.get("premiered") or "Unknown"}'
                f'{" → " + doc["ended"] if doc.get("ended") else ""}</p></div>',
                unsafe_allow_html=True,
            )
        with meta_cols[1]:
            st.markdown(
                '<div class="bf-meta-card">'
                f'<b>Runtime</b><p>{f"{runtime} min" if runtime else "Unknown"}</p></div>',
                unsafe_allow_html=True,
            )
            st.write("")
            st.markdown(
                '<div class="bf-meta-card">'
                f'<b>Network / Channel</b><p>{channel or "Unknown"}</p></div>',
                unsafe_allow_html=True,
            )

        cast = doc.get("cast")
        if isinstance(cast, list) and cast:
            names = [c.get("person_name") for c in cast if isinstance(c, dict) and c.get("person_name")]
            if names:
                st.write("")
                st.markdown(
                    '<div class="bf-meta-card">'
                    f'<b>Cast</b><p>{", ".join(names[:10])}</p></div>',
                    unsafe_allow_html=True,
                )

        st.write("")
        st.write("")

        # --- Action buttons row ---
        btn_cols = st.columns([2, 2, 2])
        with btn_cols[0]:
            if st.button("🔗  Find Similar Series", type="primary", use_container_width=True):
                go_recommendations(series_id)

        with btn_cols[1]:
            in_watchlist = _is_in_watchlist(series_id)
            if in_watchlist:
                if st.button("💔 Remove from Watchlist", use_container_width=True):
                    result = remove_from_watchlist(series_id)
                    if "Error" in str(result):
                        st.error(result)
                    else:
                        st.rerun()
            else:
                if st.button("❤️  Save to Watchlist", use_container_width=True):
                    result = save_to_watchlist(series_id)
                    if "Error" in str(result):
                        st.error(result)
                    else:
                        st.rerun()

        # --- Where to Watch ---
        try:
            _render_watch_providers(doc)
        except Exception:
            st.info("Watch provider lookup unavailable.")


# ---------------------------------------------------------------------------
# RECOMMENDATIONS
# ---------------------------------------------------------------------------

def render_recommendations() -> None:
    source_id = st.session_state.rec_source_id
    if source_id is None:
        st.info("Open a series and click 'Find Similar Series' to see recommendations here.")
        if st.button("Go to Discover"):
            go_discover()
        return

    source_doc, source_err = da.get_series_by_id(source_id)
    source_title = source_doc.get("name") if source_doc else f"series #{source_id}"

    if st.button("← Back to details"):
        go_details(source_id)

    st.markdown(
        '<div style="font-family:Sora,sans-serif;font-weight:800;font-size:2rem;margin:0.6rem 0 0.1rem 0;">'
        "🍿 Your Next Binge</div>"
        f'<p style="color:#9A9AAE;font-size:1.02rem;margin-bottom:0.4rem;">'
        f"Because you liked <b style=\"color:#F4F4F6;\">{source_title}</b> 👀</p>",
        unsafe_allow_html=True,
    )

    recs, err = da.fetch_recommendations(source_id, top_n=12)
    if err:
        st.warning(f"⚠️ {err}")
        return
    if not recs:
        st.info("No similar series were found for this title yet.")
        return

    section_header("🎯", "Ranked by Similarity Score", "Matched using TF-IDF + cosine similarity on genres, summary, cast & network")

    cards = [
        {
            "tvmaze_id": r["series_id"],
            "name": r["title"],
            "rating": r["rating"],
            "genres": r["genres"],
            "image_medium": r["image"],
        }
        for r in recs
    ]
    similarity_scores = {r["series_id"]: r["similarity_score"] for r in recs}
    why_map = explain.build_why_map(source_doc, recs)

    render_series_grid(
        cards,
        key_prefix="rec",
        on_open=go_details,
        similarity_scores=similarity_scores,
        button_label="Open",
        why_map=why_map,
    )


# ---------------------------------------------------------------------------
# WATCHLIST
# ---------------------------------------------------------------------------

def render_watchlist() -> None:
    st.markdown(
        '<h1 style="font-family:Sora,sans-serif;font-weight:800;">❤️ My Watchlist</h1>'
        '<p style="color:#9A9AAE;margin-top:-0.6rem;">Series you&#39;ve saved for later.</p>',
        unsafe_allow_html=True,
    )

    try:
        wl_ids = _get_watchlist_ids()
    except Exception as exc:
        st.error(f"⚠️ Could not load watchlist: {exc}")
        return

    if not wl_ids:
        st.info("Your watchlist is empty. Open a series and hit ❤️ Save to Watchlist to start building it.")
        if st.button("Go to Discover"):
            go_discover()
        return

    series_map = da.get_series_map()
    docs = [series_map[tid] for tid in wl_ids if tid in series_map]

    if not docs:
        st.info("None of the watchlist series are in the current catalog. Try refreshing data.")
        return

    st.caption(f"{len(docs)} series in your watchlist")
    render_series_grid(docs, key_prefix="wl", on_open=go_details, button_label="View Details")


# ---------------------------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------------------------

def render_analytics() -> None:
    st.markdown(
        '<h1 style="font-family:Sora,sans-serif;font-weight:800;">📊 Analytics</h1>'
        '<p style="color:#9A9AAE;margin-top:-0.6rem;">Visual insights from the series catalog.</p>',
        unsafe_allow_html=True,
    )

    import plotly.express as px
    import plotly.graph_objects as go

    docs, err = da.load_all_series()
    if err:
        st.error(f"⚠️ {err}")
        return
    if not docs:
        st.info("The series database is empty. Run the Phase 2 sync first.")
        return

    # --- Total count metric ---
    st.metric("Total Series in Catalog", len(docs))

    # --- Prepare data ---
    genre_counts = {}
    rating_list = []
    lang_counts = {}
    year_counts = {}
    status_counts = {}
    network_counts = {}
    genre_ratings = {}

    for doc in docs:
        for g in (doc.get("genres") or []):
            if isinstance(g, str) and g.strip():
                genre_counts[g] = genre_counts.get(g, 0) + 1
        r = doc.get("rating")
        if isinstance(r, (int, float)):
            rating_list.append(r)
            for g in (doc.get("genres") or []):
                if isinstance(g, str) and g.strip():
                    genre_ratings.setdefault(g, []).append(r)
        lang = doc.get("language")
        if isinstance(lang, str) and lang.strip():
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        premiered = doc.get("premiered")
        if isinstance(premiered, str) and len(premiered) >= 4 and premiered[:4].isdigit():
            yr = int(premiered[:4])
            if 1950 <= yr <= 2030:
                year_counts[yr] = year_counts.get(yr, 0) + 1
        status = doc.get("status")
        if isinstance(status, str) and status.strip():
            status_counts[status] = status_counts.get(status, 0) + 1
        nw = _channel_name(doc.get("network")) or _channel_name(doc.get("web_channel"))
        if isinstance(nw, str) and nw.strip():
            network_counts[nw] = network_counts.get(nw, 0) + 1

    # --- a. Genre distribution (top 15) ---
    try:
        if genre_counts:
            sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            labels, values = zip(*sorted_genres)
            fig_genre = px.bar(
                x=list(values), y=list(labels), orientation="h",
                title="Genre Distribution (Top 15)",
                labels={"x": "Count", "y": "Genre"},
                color=list(values), color_continuous_scale="Blues",
            )
            fig_genre.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font_color="#D8D8E2", height=420,
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            st.plotly_chart(fig_genre, use_container_width=True)
    except Exception:
        pass

    row1_cols = st.columns(2)

    # --- b. Rating distribution ---
    with row1_cols[0]:
        try:
            if rating_list:
                fig_rating = px.histogram(
                    x=rating_list, nbins=20,
                    title="Rating Distribution",
                    labels={"x": "Rating", "y": "Count"},
                    color_discrete_sequence=["#2979FF"],
                )
                fig_rating.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=360,
                    bargap=0.05,
                )
                st.plotly_chart(fig_rating, use_container_width=True)
        except Exception:
            pass

    # --- c. Language distribution (top 10) ---
    with row1_cols[1]:
        try:
            if lang_counts:
                sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                labels, values = zip(*sorted_langs)
                fig_lang = px.bar(
                    x=list(labels), y=list(values),
                    title="Language Distribution (Top 10)",
                    labels={"x": "Language", "y": "Count"},
                    color=list(values), color_continuous_scale="Teal",
                )
                fig_lang.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=360,
                    showlegend=False,
                )
                st.plotly_chart(fig_lang, use_container_width=True)
        except Exception:
            pass

    row2_cols = st.columns(2)

    # --- d. Series by premiere year ---
    with row2_cols[0]:
        try:
            if year_counts:
                sorted_years = sorted(year_counts.items())
                labels, values = zip(*sorted_years)
                fig_year = px.bar(
                    x=list(labels), y=list(values),
                    title="Series by Premiere Year",
                    labels={"x": "Year", "y": "Count"},
                    color=list(values), color_continuous_scale="Purples",
                )
                fig_year.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=360,
                    showlegend=False,
                )
                st.plotly_chart(fig_year, use_container_width=True)
        except Exception:
            pass

    # --- e. Status distribution ---
    with row2_cols[1]:
        try:
            if status_counts:
                labels = list(status_counts.keys())
                values = list(status_counts.values())
                fig_status = px.pie(
                    names=labels, values=values,
                    title="Status Distribution",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_status.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=360,
                )
                fig_status.update_traces(textfont_color="#F5F5F3")
                st.plotly_chart(fig_status, use_container_width=True)
        except Exception:
            pass

    row3_cols = st.columns(2)

    # --- f. Network / Channel distribution (top 15) ---
    with row3_cols[0]:
        try:
            if network_counts:
                sorted_nw = sorted(network_counts.items(), key=lambda x: x[1], reverse=True)[:15]
                labels, values = zip(*sorted_nw)
                fig_nw = px.bar(
                    x=list(values), y=list(labels), orientation="h",
                    title="Network / Channel (Top 15)",
                    labels={"x": "Count", "y": "Network"},
                    color=list(values), color_continuous_scale="Oranges",
                )
                fig_nw.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=420,
                    yaxis=dict(autorange="reversed"),
                    showlegend=False,
                )
                st.plotly_chart(fig_nw, use_container_width=True)
        except Exception:
            pass

    # --- g. Average rating by genre ---
    with row3_cols[1]:
        try:
            if genre_ratings:
                avg_data = []
                for genre, rats in genre_ratings.items():
                    avg_data.append((genre, sum(rats) / len(rats), len(rats)))
                avg_data.sort(key=lambda x: x[1], reverse=True)
                avg_data = avg_data[:15]
                labels = [x[0] for x in avg_data]
                avgs = [round(x[1], 2) for x in avg_data]
                counts = [x[2] for x in avg_data]
                fig_avg = px.bar(
                    x=avgs, y=labels, orientation="h",
                    title="Avg Rating by Genre (Top 15)",
                    labels={"x": "Avg Rating", "y": "Genre"},
                    color=avgs, color_continuous_scale="YlGn",
                    text=avgs,
                )
                fig_avg.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#D8D8E2", height=420,
                    yaxis=dict(autorange="reversed"),
                    showlegend=False,
                )
                fig_avg.update_traces(texttemplate="%{text:.1f}", textposition="outside")
                st.plotly_chart(fig_avg, use_container_width=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def main() -> None:
    inject_global_css()
    inject_theme_rotator()
    render_sidebar()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "discover":
        render_discover()
    elif page == "details":
        render_details()
    elif page == "recommendations":
        render_recommendations()
    elif page == "watchlist":
        render_watchlist()
    elif page == "analytics":
        render_analytics()
    else:
        go_home()


if __name__ == "__main__":
    main()
