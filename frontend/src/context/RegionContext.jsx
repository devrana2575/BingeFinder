import { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { api } from '../api/client';
import { useAuth } from './AuthContext';

const RegionContext = createContext(null);

const REGION_STORAGE_KEY = 'bf_region';

// Best-effort country guess from the browser's timezone (no IPs, no geo
// APIs). Only used the first time, before the user picks or saves a region.
const TIMEZONE_TO_REGION = {
  'Asia/Kolkata': 'IN',
  'Europe/London': 'GB',
  'Europe/Berlin': 'DE',
  'Europe/Paris': 'FR',
  'Europe/Madrid': 'ES',
  'Europe/Rome': 'IT',
  'Europe/Lisbon': 'PT',
  'Europe/Amsterdam': 'NL',
  'Europe/Brussels': 'BE',
  'Europe/Stockholm': 'SE',
  'Europe/Oslo': 'NO',
  'Europe/Copenhagen': 'DK',
  'Europe/Helsinki': 'FI',
  'Europe/Warsaw': 'PL',
  'Europe/Prague': 'CZ',
  'Europe/Vienna': 'AT',
  'Europe/Bern': 'CH',
  'Europe/Istanbul': 'TR',
  'Europe/Moscow': 'RU',
  'Africa/Johannesburg': 'ZA',
  'Africa/Lagos': 'NG',
  'Africa/Cairo': 'EG',
  'Asia/Tokyo': 'JP',
  'Asia/Seoul': 'KR',
  'Asia/Shanghai': 'CN',
  'Asia/Taipei': 'TW',
  'Asia/Hong_Kong': 'HK',
  'Asia/Singapore': 'SG',
  'Asia/Kuala_Lumpur': 'MY',
  'Asia/Bangkok': 'TH',
  'Asia/Jakarta': 'ID',
  'Asia/Manila': 'PH',
  'Asia/Ho_Chi_Minh': 'VN',
  'Asia/Riyadh': 'SA',
  'Asia/Dubai': 'AE',
  'Asia/Jerusalem': 'IL',
  'Australia/Sydney': 'AU',
  'Australia/Perth': 'AU',
  'Pacific/Auckland': 'NZ',
};

function guessRegionFromTimezone(fallback) {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (zone && TIMEZONE_TO_REGION[zone]) return TIMEZONE_TO_REGION[zone];
  } catch {}
  return fallback;
}

export function RegionProvider({ children }) {
  const { isAuth, user, loading: authLoading } = useAuth();

  const [regions, setRegions] = useState([]);
  const [defaultRegion, setDefaultRegion] = useState('US');
  const [region, setRegionState] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api.regions()
      .then(data => {
        setRegions(data.regions || []);
        if (data.default) setDefaultRegion(data.default);
      })
      .catch(() => {});
  }, []);

  // Resolve initial region once, when we know whether the user is authed.
  useEffect(() => {
    if (region !== null || authLoading) return;
    const saved = localStorage.getItem(REGION_STORAGE_KEY);
    const fromAccount = isAuth ? user?.preferences?.region : null;
    const guess = guessRegionFromTimezone(defaultRegion);
    const initial = fromAccount || saved || guess || defaultRegion;
    setRegionState(initial);
    setReady(true);
  }, [isAuth, user, defaultRegion, region, authLoading]);

  const setRegion = useCallback(async (code) => {
    setRegionState(code);
    localStorage.setItem(REGION_STORAGE_KEY, code);
    if (isAuth) {
      try {
        await api.updateSettings({ region: code });
      } catch {}
    }
  }, [isAuth]);

  const regionName = useMemo(() => {
    const found = regions.find(r => r.code === region);
    return found ? found.name : (region || defaultRegion);
  }, [regions, region, defaultRegion]);

  const value = useMemo(() => ({
    region,
    regionName,
    regions,
    setRegion,
    ready,
  }), [region, regionName, regions, setRegion, ready]);

  return <RegionContext.Provider value={value}>{children}</RegionContext.Provider>;
}

export function useRegion() {
  const ctx = useContext(RegionContext);
  if (!ctx) throw new Error('useRegion must be used within RegionProvider');
  return ctx;
}