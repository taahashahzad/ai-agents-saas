import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Spinner from '../components/Spinner';

export default function PublicOnlyRoute() {
  const { user, loading } = useAuth();

  if (loading) return <Spinner fullScreen label="Loading..." />;
  if (user) return <Navigate to="/" replace />;
  return <Outlet />;
}
