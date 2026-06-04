import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const ProtectedLayout = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card glass-panel">
          <p>Memuat...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const allowed = user.menus?.some((menu) => {
    if (menu.path === '/') return location.pathname === '/';
    return location.pathname === menu.path || location.pathname.startsWith(`${menu.path}/`);
  });
  if (!allowed) {
    const fallback = user.menus?.[0]?.path ?? '/login';
    if (fallback === location.pathname) {
      return (
        <div className="login-page">
          <div className="login-card glass-panel">
            <h2>Akses ditolak</h2>
            <p>Akun Anda tidak memiliki izin untuk halaman ini.</p>
          </div>
        </div>
      );
    }
    return <Navigate to={fallback} replace />;
  }

  return <Outlet />;
};

export default ProtectedLayout;
