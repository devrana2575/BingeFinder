import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { t } from '../i18n';

const TYPE_LABEL = {
  tv_series: 'Web Series',
  movie: 'Movies',
  anime: 'Anime',
};

export default function SearchSuggest({
  initialState = '',
  contentType,
  onSearch,
  onChange,
  placeholder,
  minChars = 2,
  actionLabel,
  inputClassName = '',
  containerClassName = '',
}) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initialState);
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const wrapRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => setValue(initialState), [initialState]);

  useEffect(() => {
    clearTimeout(timerRef.current);
    if (value.trim().length < minChars) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    timerRef.current = setTimeout(() => {
      api.suggest(value.trim(), contentType)
        .then(items => setSuggestions(items.slice(0, 8)))
        .catch(() => setSuggestions([]));
      setOpen(true);
      setHighlight(-1);
    }, 180);
    return () => clearTimeout(timerRef.current);
  }, [value, contentType, minChars]);

  useEffect(() => {
    const onDown = e => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const goSearch = () => {
    const q = value.trim();
    if (!q) return;
    if (onSearch) onSearch(q);
    else navigate(`/discover?q=${encodeURIComponent(q)}`);
    setOpen(false);
    setHighlight(-1);
  };

  const goToSeries = s => {
    navigate(`/series/${s.series_id}`);
    setOpen(false);
    setHighlight(-1);
  };

  const totalRows = suggestions.length + 1; // suggestions + "search for" row

  const handleKey = e => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight(h => (h + 1) % totalRows);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight(h => (h <= 0 ? totalRows - 1 : h - 1));
    } else if (e.key === 'Enter') {
      if (highlight > 0 && suggestions[highlight - 1]) goToSeries(suggestions[highlight - 1]);
      else goSearch();
    } else if (e.key === 'Escape') {
      setOpen(false);
      setHighlight(-1);
    }
  };

  const shown = open && suggestions.length > 0 && value.trim().length >= minChars;

  return (
    <div ref={wrapRef} className={`relative ${containerClassName}`}>
      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          onChange={e => {
            const v = e.target.value;
            setValue(v);
            setHighlight(-1);
            if (onChange) onChange(v);
          }}
          onFocus={() => value.trim().length >= minChars && setOpen(true)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          className={inputClassName}
        />
        {actionLabel && (
          <button type="button" onClick={goSearch} className="btn-primary flex-shrink-0">
            {actionLabel}
          </button>
        )}
      </div>
      {shown && (
        <ul className="absolute left-0 right-0 top-full mt-1.5 z-20 max-h-72 overflow-y-auto rounded-lg border border-border bg-surface shadow-xl">
          <li
            onMouseDown={goSearch}
            onMouseEnter={() => setHighlight(0)}
            className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer text-sm ${highlight === 0 ? 'bg-bg text-accent' : 'text-accent'}`}
          >
            <span aria-hidden>⌕</span>
            {t('discover.searchFor', { q: value.trim() })}
          </li>
          {suggestions.map((s, i) => {
            const row = i + 1;
            const meta = [
              TYPE_LABEL[s.content_type] || s.content_type,
              s.year,
              s.rating != null ? `${s.rating.toFixed(1)}★` : null,
            ].filter(Boolean).join(' · ');
            return (
              <li
                key={s.series_id}
                onMouseDown={() => goToSeries(s)}
                onMouseEnter={() => setHighlight(row)}
                className={`flex items-center gap-3 px-3 py-2 cursor-pointer ${highlight === row ? 'bg-bg' : ''}`}
              >
                <img
                  src={s.image}
                  alt=""
                  className="w-10 h-14 object-cover rounded flex-shrink-0 bg-bg"
                  loading="lazy"
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-text truncate">{s.name}</span>
                  <span className="block text-xs text-text-muted truncate">{meta}</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}