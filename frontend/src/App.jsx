import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { RegionProvider } from './context/RegionContext';
import { ToastProvider } from './context/ToastContext';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import DiscoverPage from './pages/DiscoverPage';
import SurprisePage from './pages/SurprisePage';
import SeriesDetailPage from './pages/SeriesDetailPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import WatchlistPage from './pages/WatchlistPage';
import LikedPage from './pages/LikedPage';
import RecentlyViewedPage from './pages/RecentlyViewedPage';
import ForYouPage from './pages/ForYouPage';
import VibesFilterPage from './pages/VibesFilterPage';
import SettingsPage from './pages/SettingsPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RegionProvider>
          <ToastProvider>
            <Routes>
              <Route element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="discover" element={<DiscoverPage />} />
              <Route path="discover/vibes/:key" element={<VibesFilterPage />} />
              <Route path="surprise" element={<SurprisePage />} />
              <Route path="series/:id" element={<SeriesDetailPage />} />
              <Route path="watchlist" element={<WatchlistPage />} />
              <Route path="liked" element={<LikedPage />} />
              <Route path="recently-viewed" element={<RecentlyViewedPage />} />
              <Route path="for-you" element={<ForYouPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="signup" element={<SignupPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
          </ToastProvider>
        </RegionProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
