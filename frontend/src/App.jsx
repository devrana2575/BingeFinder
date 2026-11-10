import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { RegionProvider } from './context/RegionContext';
import { ToastProvider } from './context/ToastContext';
import ErrorBoundary from './components/ErrorBoundary';
import AuthLayout from './components/AuthLayout';
import Layout from './components/Layout';
import PageLoader from './components/PageLoader';
import ProtectedRoute from './components/ProtectedRoute';
import PublicOnlyRoute from './components/PublicOnlyRoute';

// Route-level code splitting keeps the first paint small: each page (and its
// dependencies) is fetched only when the user navigates to it.
const HomePage = lazy(() => import('./pages/HomePage'));
const DiscoverPage = lazy(() => import('./pages/DiscoverPage'));
const SeriesPage = lazy(() => import('./pages/SeriesPage'));
const AnimePage = lazy(() => import('./pages/AnimePage'));
const SurprisePage = lazy(() => import('./pages/SurprisePage'));
const SeriesDetailPage = lazy(() => import('./pages/SeriesDetailPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const SignupPage = lazy(() => import('./pages/SignupPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'));
const LikedPage = lazy(() => import('./pages/LikedPage'));
const RecentlyViewedPage = lazy(() => import('./pages/RecentlyViewedPage'));
const ForYouPage = lazy(() => import('./pages/ForYouPage'));
const VibesFilterPage = lazy(() => import('./pages/VibesFilterPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <RegionProvider>
            <ToastProvider>
              <Suspense fallback={<PageLoader fullScreen />}>
                <Routes>
                  {/* Catalog, discovery, and library pages are members-only. */}
                  <Route element={<ProtectedRoute />}>
                    <Route element={<Layout />}>
                      <Route index element={<HomePage />} />
                      <Route path="discover" element={<DiscoverPage />} />
                      <Route path="discover/vibes/:key" element={<VibesFilterPage />} />
                      <Route path="series" element={<SeriesPage />} />
                      <Route path="anime" element={<AnimePage />} />
                      <Route path="surprise" element={<SurprisePage />} />
                      <Route path="series/:id" element={<SeriesDetailPage />} />
                      <Route path="watchlist" element={<WatchlistPage />} />
                      <Route path="liked" element={<LikedPage />} />
                      <Route path="recently-viewed" element={<RecentlyViewedPage />} />
                      <Route path="for-you" element={<ForYouPage />} />
                      <Route path="onboarding" element={<OnboardingPage />} />
                    </Route>
                  </Route>

                  {/* Auth pages are public but signed-in users skip them. */}
                  <Route element={<PublicOnlyRoute />}>
                    <Route element={<AuthLayout />}>
                      <Route path="login" element={<LoginPage />} />
                      <Route path="signup" element={<SignupPage />} />
                    </Route>
                  </Route>

                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </ToastProvider>
          </RegionProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
