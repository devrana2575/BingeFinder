"""
ui/components.py
===================
Small, reusable rendering helpers shared by every page of the Streamlit
app: the global stylesheet (dark cinematic theme), poster images (with
a graceful fallback when a series has no image), rating badges, genre
tag pills, and the series "card" used on Home/Discover/Recommendations
grids.

Phase 4.1 note: this is a pure UI/UX polish pass. Every function here
still has the exact same name, signature, and return contract it had in
Phase 4 — streamlit_app.py calls them exactly as before. Only the CSS
and the markup used to *present* the same data has changed. No
MongoDB/recommender calls live here, and none were added.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

PLACEHOLDER_EMOJI = "🎬"


def inject_global_css() -> None:
    """Dark, cinematic, gradient-accented styling for the whole app. Injected once per page."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bf-bg: #121212;
            --bf-surface: #1A1A1A;
            --bf-surface-2: #212121;
            --bf-border: rgba(255,255,255,0.08);
            --bf-text: #F5F5F3;
            --bf-text-dim: #9C9C9C;
            --bf-accent-1: #2979FF;
            --bf-accent-2: #5B9DFF;
            --bf-accent-1-rgb: 41,121,255;
            --bf-gradient: linear-gradient(135deg, var(--bf-accent-1) 0%, var(--bf-accent-2) 100%);
            --bf-sidebar-bg: #0E0E17;
            --bf-card-glow: rgba(41,121,255,0.45);
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            transition: background-color 1.5s ease, color 1.5s ease;
        }
        h1, h2, h3, .bf-title, .bf-hero h1 { font-family: 'Sora', sans-serif; }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 15% -10%, rgba(var(--bf-accent-1-rgb),0.14), transparent 40%),
                radial-gradient(circle at 85% 0%, rgba(var(--bf-accent-1-rgb),0.08), transparent 35%),
                var(--bf-bg);
            transition: background 1.5s ease;
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: var(--bf-sidebar-bg);
            border-right: 1px solid var(--bf-border);
            transition: background-color 1.5s ease, border-color 1.5s ease;
        }

        .block-container { animation: bfFadeIn 0.35s ease-out; padding-top: 2rem; }
        @keyframes bfFadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* ---------------- Hero ---------------- */
        .bf-hero {
            position: relative;
            padding: 2.2rem 0 1.4rem 0;
            margin-bottom: 0.6rem;
        }
        .bf-hero-eyebrow {
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--bf-accent-2);
            margin-bottom: 0.6rem;
            transition: color 1.5s ease;
        }
        .bf-hero h1 {
            margin: 0 0 0.35rem 0;
            font-size: 2.4rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--bf-text);
            transition: color 1.5s ease;
        }
        .bf-hero p { margin: 0; opacity: 0.85; font-size: 1rem; max-width: 640px; color: var(--bf-text-dim); transition: color 1.5s ease; }
        .bf-hero-stats { display: flex; gap: 1.4rem; margin-top: 0.9rem; flex-wrap: wrap; }
        .bf-hero-stat { display: flex; flex-direction: column; }
        .bf-hero-stat b { font-size: 1.15rem; font-weight: 800; line-height: 1.1; color: var(--bf-text); transition: color 1.5s ease; }
        .bf-hero-stat span { font-size: 0.76rem; opacity: 0.8; color: var(--bf-text-dim); transition: color 1.5s ease; }

        /* ---------------- Section headers ---------------- */
        .bf-section {
            display: flex;
            align-items: baseline;
            gap: 0.6rem;
            margin: 2rem 0 0.9rem 0;
        }
        .bf-section h3 {
            margin: 0;
            font-size: 1.35rem;
            font-weight: 700;
            background: var(--bf-gradient);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            transition: background 1.5s ease;
        }
        .bf-section-sub { color: var(--bf-text-dim); font-size: 0.85rem; transition: color 1.5s ease; }

        /* ---------------- Sidebar logo ---------------- */
        .bf-logo-text {
            font-family: 'Sora', sans-serif;
            font-weight: 800;
            font-size: 1.4rem;
            background: var(--bf-gradient);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            transition: background 1.5s ease;
        }

        /* ---------------- Cards (st.container(border=True)) ---------------- */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bf-poster-wrap) {
            background: var(--bf-surface);
            border: 1px solid var(--bf-border) !important;
            border-radius: 16px !important;
            padding: 0.6rem 0.7rem 0.8rem 0.7rem;
            transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease, background-color 1.5s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bf-poster-wrap):hover {
            transform: translateY(-6px);
            border-color: rgba(var(--bf-accent-1-rgb),0.55) !important;
            box-shadow: 0 18px 34px -16px var(--bf-card-glow);
        }

        .bf-poster-wrap {
            position: relative;
            width: 100%;
            aspect-ratio: 2 / 3;
            border-radius: 12px;
            overflow: hidden;
            background: linear-gradient(160deg, #23233333, #14141f);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.6rem;
        }
        .bf-poster-wrap img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.35s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover .bf-poster-wrap img { transform: scale(1.06); }

        .bf-poster-placeholder {
            color: var(--bf-text-dim);
            text-align: center;
            font-size: 0.78rem;
            padding: 0.5rem;
            transition: color 1.5s ease;
        }
        .bf-poster-placeholder .emoji { font-size: 2.4rem; display: block; margin-bottom: 0.3rem; }

        .bf-title {
            font-weight: 700;
            font-size: 0.96rem;
            color: var(--bf-text);
            margin: 0 0 0.35rem 0;
            line-height: 1.28;
            min-height: 2.5em;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            transition: color 1.5s ease;
        }

        .bf-badge-row { display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.45rem; flex-wrap: wrap; }

        .bf-rating-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.2rem;
            padding: 0.14rem 0.55rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
            color: white;
            box-shadow: 0 2px 8px -2px rgba(0,0,0,0.5);
        }
        .bf-sim-badge {
            display: inline-block;
            padding: 0.14rem 0.55rem;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
            background: var(--bf-gradient);
            color: white;
            transition: background 1.5s ease;
        }

        .bf-tag-row { display: flex; flex-wrap: wrap; gap: 0.32rem; margin-bottom: 0.6rem; min-height: 1.6em; }
        .bf-tag {
            background: rgba(255,255,255,0.06);
            border: 1px solid var(--bf-border);
            color: var(--bf-text-dim);
            border-radius: 999px;
            padding: 0.1rem 0.6rem;
            font-size: 0.7rem;
            letter-spacing: 0.02em;
            transition: border-color 1.5s ease, color 1.5s ease;
        }

        .bf-simbar-track {
            width: 100%; height: 5px; border-radius: 999px;
            background: rgba(255,255,255,0.08);
            margin-bottom: 0.6rem; overflow: hidden;
        }
        .bf-simbar-fill { height: 100%; border-radius: 999px; background: var(--bf-gradient); transition: background 1.5s ease; }

        /* ---------------- Buttons ---------------- */
        .stButton > button {
            border-radius: 999px !important;
            border: none !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em;
            transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease, background 1.5s ease;
        }
        div[data-testid="stVerticalBlock"] .stButton > button {
            background: var(--bf-gradient) !important;
            color: #0E0E0E !important;
            box-shadow: 0 6px 18px -8px rgba(var(--bf-accent-1-rgb),0.55);
            transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease, background 1.5s ease, box-shadow 1.5s ease;
        }
        .stButton > button:hover { transform: translateY(-2px); filter: brightness(1.08); }
        .stButton > button:active { transform: translateY(0); }

        [data-testid="stSidebar"] .stButton > button {
            background: transparent !important;
            border: 1px solid var(--bf-border) !important;
            color: var(--bf-text) !important;
            box-shadow: none !important;
            text-align: left;
            transition: border-color 1.5s ease, color 1.5s ease;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: var(--bf-accent-1) !important;
            color: var(--bf-accent-2) !important;
        }

        /* ---------------- Inputs ---------------- */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 12px !important;
            background: var(--bf-surface-2) !important;
            border: 1px solid var(--bf-border) !important;
            transition: background-color 1.5s ease, border-color 1.5s ease;
        }
        .stTextInput input:focus { border-color: var(--bf-accent-1) !important; transition: border-color 1.5s ease; }

        /* ---------------- Poster placeholder on Details page ---------------- */
        .bf-detail-poster-placeholder {
            aspect-ratio: 2/3; border-radius: 16px;
            background: linear-gradient(160deg, #23233333, #14141f);
            border: 1px solid var(--bf-border);
            display: flex; align-items: center; justify-content: center;
            flex-direction: column; color: var(--bf-text-dim); gap: 0.4rem;
            transition: border-color 1.5s ease, color 1.5s ease;
        }
        .bf-detail-poster-placeholder .emoji { font-size: 3rem; }

        [data-testid="stImage"] img {
            border-radius: 16px;
            box-shadow: 0 24px 50px -18px rgba(0,0,0,0.65);
        }

        .bf-chip-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.6rem 0 1rem 0; }
        .bf-meta-card {
            background: var(--bf-surface);
            border: 1px solid var(--bf-border);
            border-radius: 14px;
            padding: 0.9rem 1.1rem;
            transition: background-color 1.5s ease, border-color 1.5s ease;
        }
        .bf-meta-card b { color: var(--bf-text-dim); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; transition: color 1.5s ease; }
        .bf-meta-card p { margin: 0.15rem 0 0 0; font-size: 0.98rem; color: var(--bf-text); transition: color 1.5s ease; }

        /* ---------------- TVmaze candidate picker (Discover) ---------------- */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bf-cand-marker) {
            background: var(--bf-surface);
            border: 1px solid var(--bf-border) !important;
            border-radius: 16px !important;
            padding: 0.6rem 0.7rem 0.8rem 0.7rem;
            transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background-color 1.5s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bf-cand-marker):hover {
            transform: translateY(-4px);
            border-color: rgba(var(--bf-accent-1-rgb),0.55) !important;
            box-shadow: 0 14px 30px -16px var(--bf-card-glow);
        }
        .bf-cand-title { font-weight: 700; font-size: 0.92rem; color: var(--bf-text); margin: 0 0 0.15rem 0; line-height: 1.25; transition: color 1.5s ease; }
        .bf-cand-meta { font-size: 0.78rem; color: var(--bf-text-dim); margin-bottom: 0.5rem; transition: color 1.5s ease; }

        /* ---------------- Why this? ---------------- */
        .bf-why-line {
            font-size: 0.82rem;
            color: var(--bf-text-dim);
            padding: 0.25rem 0;
            border-bottom: 1px dashed var(--bf-border);
            transition: color 1.5s ease, border-color 1.5s ease;
        }
        .bf-why-line:last-child { border-bottom: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_theme_rotator() -> None:
    """
    Cycles the app through 6 complete cinematic themes — background,
    surfaces, accents, sidebar, and card glow — every 10 seconds,
    purely client-side via a browser setInterval. Guards against
    double-init across Streamlit reruns.
    """
    st.markdown(
        """
        <script>
        (function () {
            if (window.__bfThemeRotationStarted) { return; }
            window.__bfThemeRotationStarted = true;

            var THEMES = [
                {   // Cyber Night
                    bg: "#0b0e14", surface: "#131720", surface2: "#1a1f2e",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#06B6D4", a2: "#67E8F9",
                    rgb: "6,182,212", sidebar: "#080b10",
                    glow: "rgba(6,182,212,0.45)"
                },
                {   // Neon Dream
                    bg: "#0d0a14", surface: "#161222", surface2: "#1e1830",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#D946EF", a2: "#F0ABFC",
                    rgb: "217,70,239", sidebar: "#09070f",
                    glow: "rgba(217,70,239,0.45)"
                },
                {   // Ocean
                    bg: "#0a1118", surface: "#111d26", surface2: "#172832",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#0891B2", a2: "#67E8F9",
                    rgb: "8,145,178", sidebar: "#070d13",
                    glow: "rgba(8,145,178,0.45)"
                },
                {   // Matrix
                    bg: "#080808", surface: "#0c1210", surface2: "#111a16",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#10B981", a2: "#6EE7B7",
                    rgb: "16,185,129", sidebar: "#060a08",
                    glow: "rgba(16,185,129,0.45)"
                },
                {   // After Dark
                    bg: "#101014", surface: "#18181c", surface2: "#202026",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#DC2626", a2: "#F87171",
                    rgb: "220,38,38", sidebar: "#0c0c0f",
                    glow: "rgba(220,38,38,0.45)"
                },
                {   // Aurora
                    bg: "#080c18", surface: "#101628", surface2: "#18203a",
                    border: "rgba(255,255,255,0.08)", text: "#F5F5F3",
                    textDim: "#9C9C9C", a1: "#34D399", a2: "#6EE7B7",
                    rgb: "52,211,153", sidebar: "#060912",
                    glow: "rgba(52,211,153,0.45)"
                }
            ];
            var INTERVAL_MS = 10000;

            function apply(t) {
                var r = document.documentElement;
                r.style.setProperty("--bf-bg", t.bg);
                r.style.setProperty("--bf-surface", t.surface);
                r.style.setProperty("--bf-surface-2", t.surface2);
                r.style.setProperty("--bf-border", t.border);
                r.style.setProperty("--bf-text", t.text);
                r.style.setProperty("--bf-text-dim", t.textDim);
                r.style.setProperty("--bf-accent-1", t.a1);
                r.style.setProperty("--bf-accent-2", t.a2);
                r.style.setProperty("--bf-accent-1-rgb", t.rgb);
                r.style.setProperty("--bf-sidebar-bg", t.sidebar);
                r.style.setProperty("--bf-card-glow", t.glow);
                r.style.setProperty("--bf-gradient", "linear-gradient(135deg, " + t.a1 + " 0%, " + t.a2 + " 100%)");
            }

            var idx = Math.floor(Math.random() * THEMES.length);
            apply(THEMES[idx]);

            setInterval(function () {
                idx = (idx + 1) % THEMES.length;
                apply(THEMES[idx]);
            }, INTERVAL_MS);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def hero_html(series_count: int = 0) -> str:
    """The Home page hero banner, with a live count pulled from MongoDB by the caller."""
    stat = f'<div class="bf-hero-stat"><b>{series_count:,}</b><span>series in the catalog</span></div>' if series_count else ""
    return f"""
    <div class="bf-hero">
        <span class="bf-hero-eyebrow">🎬 BingeFinder</span>
        <h1>What's your next binge?</h1>
        <p>Search a title or hit Surprise Me — matched from the catalog, no endless scrolling.</p>
        <div class="bf-hero-stats">
            {stat}
        </div>
    </div>
    """


def section_header(icon: str, title: str, subtitle: str = "") -> None:
    """A gradient-accented section title used to introduce each row/grid of cards."""
    sub = f'<span class="bf-section-sub">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="bf-section"><h3>{icon} {title}</h3>{sub}</div>',
        unsafe_allow_html=True,
    )


def render_tvmaze_candidates(candidates: List[Dict[str, Any]], key_prefix: str) -> Optional[Dict[str, Any]]:
    """
    Render a row of TVmaze search-result cards (poster, title, premiere
    year) so the user can pick the exact series they meant — e.g. the
    real "Money Heist" vs. "Money Heist: Korea" — instead of the app
    silently grabbing TVmaze's #1-ranked result.

    `candidates` is the list returned by `ui.data_access.search_tvmaze()`
    (each item has "tvmaze_id", "name", "premiered", "image_medium" and
    the raw "show" dict). Returns the picked candidate dict the moment
    its button is clicked this run, or None otherwise.
    """
    if not candidates:
        return None

    st.caption(f"Found {len(candidates)} match{'es' if len(candidates) != 1 else ''} on TVmaze — pick the right one:")
    picked: Optional[Dict[str, Any]] = None
    columns = min(4, len(candidates))
    cols = st.columns(columns)
    for i, cand in enumerate(candidates):
        with cols[i % columns]:
            with st.container(border=True):
                st.markdown('<span class="bf-cand-marker"></span>', unsafe_allow_html=True)
                st.markdown(poster_html(cand.get("image_medium"), cand.get("name") or ""), unsafe_allow_html=True)
                st.markdown(f'<p class="bf-cand-title">{cand.get("name") or "Untitled"}</p>', unsafe_allow_html=True)
                year = (cand.get("premiered") or "")[:4] or "Unknown year"
                lang = cand.get("language") or "Unknown language"
                st.markdown(f'<p class="bf-cand-meta">{year} · {lang}</p>', unsafe_allow_html=True)
                if st.button("＋ Add this one", key=f"{key_prefix}_{cand.get('tvmaze_id')}", use_container_width=True):
                    picked = cand
    return picked


def rating_color(rating: Optional[float]) -> str:
    """Map a 0-10 rating to a badge gradient (grey when unknown)."""
    if rating is None:
        return "linear-gradient(135deg,#5b5b6b,#3f3f4c)"
    if rating >= 8.0:
        return "linear-gradient(135deg,#22C55E,#0D9488)"
    if rating >= 6.5:
        return "linear-gradient(135deg,#F59E0B,#B45309)"
    return "linear-gradient(135deg,#F43F5E,#9F1239)"


def rating_badge_html(rating: Optional[float]) -> str:
    label = f"⭐ {rating:.1f}" if isinstance(rating, (int, float)) else "⭐ N/A"
    return f'<span class="bf-rating-badge" style="background:{rating_color(rating)};">{label}</span>'


def genre_tags_html(genres: Optional[List[str]], limit: int = 3) -> str:
    genres = genres or []
    if not genres:
        return '<span class="bf-tag">Uncategorized</span>'
    shown = genres[:limit]
    return "".join(f'<span class="bf-tag">{g}</span>' for g in shown)


def poster_html(image_url: Optional[str], title: str = "") -> str:
    """A fixed-aspect-ratio poster box; falls back to a placeholder when there's no image."""
    if image_url:
        safe_title = (title or "Poster").replace('"', "'")
        return f'<div class="bf-poster-wrap"><img src="{image_url}" alt="{safe_title}"/></div>'
    return (
        '<div class="bf-poster-wrap">'
        f'<div class="bf-poster-placeholder"><span class="emoji">{PLACEHOLDER_EMOJI}</span>No poster available</div>'
        "</div>"
    )


def render_series_card(
    doc: Dict[str, Any],
    key_prefix: str,
    on_open,
    similarity_score: Optional[float] = None,
    button_label: str = "View Details",
    why_reasons: Optional[List[str]] = None,
) -> None:
    """
    Render one series as a premium poster card with a title, rating
    badge, genre tags, and an action button. `on_open` is called with
    the series' tvmaze_id when the button is clicked.

    Missing fields (poster, rating, genres) degrade gracefully instead
    of raising — this is the single place cards are drawn, so every
    grid (Home/Discover/Details/Recommendations) gets the same
    error-tolerant behavior. Same signature/contract as Phase 4, plus
    one new optional `why_reasons` param: when a caller (currently only
    the Recommendations page) passes a list of reason strings, an
    expander is added at the bottom of the card. Every other caller
    passes nothing and gets the exact same card as before.
    """
    title = doc.get("name") or "Untitled Series"
    image_url = doc.get("image_medium") or doc.get("image_original")
    series_id = doc.get("tvmaze_id")

    with st.container(border=True):
        st.markdown(poster_html(image_url, title), unsafe_allow_html=True)
        st.markdown(f'<p class="bf-title">{title}</p>', unsafe_allow_html=True)

        badges = rating_badge_html(doc.get("rating"))
        if similarity_score is not None:
            badges += f'<span class="bf-sim-badge">🎯 {similarity_score * 100:.0f}% match</span>'
        st.markdown(f'<div class="bf-badge-row">{badges}</div>', unsafe_allow_html=True)

        if similarity_score is not None:
            pct = max(0.0, min(1.0, similarity_score)) * 100
            st.markdown(
                f'<div class="bf-simbar-track"><div class="bf-simbar-fill" style="width:{pct:.0f}%;"></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown(f'<div class="bf-tag-row">{genre_tags_html(doc.get("genres"))}</div>', unsafe_allow_html=True)

        if why_reasons:
            with st.expander("💡 Why this?"):
                for reason in why_reasons:
                    st.markdown(f'<div class="bf-why-line">{reason}</div>', unsafe_allow_html=True)

        disabled = series_id is None
        if st.button(button_label, key=f"{key_prefix}_{series_id}", use_container_width=True, disabled=disabled):
            on_open(series_id)


def render_series_grid(
    docs: List[Dict[str, Any]],
    key_prefix: str,
    on_open,
    columns: int = 5,
    similarity_scores: Optional[Dict[int, float]] = None,
    button_label: str = "View Details",
    why_map: Optional[Dict[int, List[str]]] = None,
) -> None:
    """Lay out a list of series documents in a responsive grid of cards.

    `why_map` (optional): {tvmaze_id: [reason, ...]} — when given, each
    card whose id is a key gets a "Why this?" expander. Every existing
    caller that doesn't pass it behaves exactly as before.
    """
    if not docs:
        st.info("No series to show here yet.")
        return

    similarity_scores = similarity_scores or {}
    why_map = why_map or {}
    cols = st.columns(columns)
    for i, doc in enumerate(docs):
        with cols[i % columns]:
            render_series_card(
                doc,
                key_prefix=key_prefix,
                on_open=on_open,
                similarity_score=similarity_scores.get(doc.get("tvmaze_id")),
                button_label=button_label,
                why_reasons=why_map.get(doc.get("tvmaze_id")),
            )
