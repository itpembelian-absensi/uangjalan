import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { apiFetch } from '../api';
import { clearLoginPrefs, loadLoginPrefs, saveLoginPrefs } from './loginStorage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch('/api/auth/me');
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = useCallback(async (username, password, rememberMe = false) => {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, remember_me: rememberMe }),
    });
    setUser(data);
    return data;
  }, []);

  const logout = useCallback(async () => {
    const { autoLogin, username } = loadLoginPrefs();
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } finally {
      setUser(null);
      if (autoLogin) {
        saveLoginPrefs(true, username);
      } else {
        clearLoginPrefs();
      }
    }
  }, []);

  const hasPermission = useCallback(
    (permission) => {
      if (!user?.permissions) return false;
      return user.permissions.includes(permission);
    },
    [user]
  );

  const canWritePage = useCallback(
    (path) => {
      const menus = user?.menus ?? [];
      const exact = menus.find((m) => m.path === path);
      if (exact) return exact.can_write ?? false;

      let matched = null;
      for (const menu of menus) {
        if (menu.path === '/') continue;
        if (path === menu.path || path.startsWith(`${menu.path}/`)) {
          if (!matched || menu.path.length > matched.path.length) {
            matched = menu;
          }
        }
      }
      return matched?.can_write ?? false;
    },
    [user]
  );

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh, hasPermission, canWritePage }),
    [user, loading, login, logout, refresh, hasPermission, canWritePage]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth harus dipakai di dalam AuthProvider');
  }
  return ctx;
}

/** Apakah user boleh tambah/ubah/hapus di halaman saat ini */
export function usePageWriteAccess() {
  const { canWritePage } = useAuth();
  const { pathname } = useLocation();
  return canWritePage(pathname);
}
