import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PageLoader from './PageLoader';

/**
 * Gate for every catalog/discovery route.
 *
 * Waiting for AuthContext.loading avoids redirecting a returning user to
 * /login while /auth/me is still in flight, and preserves the attempted
 * destination so login can send them straight back.
 */
export default function ProtectedRoute() {
  const { isAuth, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader fullScreen />;
  if (!isAuth) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
