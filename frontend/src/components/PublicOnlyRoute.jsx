import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PageLoader from './PageLoader';
import { getReturnPath } from '../utils/navigation';

/** Keep authenticated users out of /login and /signup. */
export default function PublicOnlyRoute() {
  const { isAuth, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader fullScreen />;
  if (isAuth) {
    return <Navigate to={getReturnPath(location.state?.from)} replace />;
  }

  return <Outlet />;
}
