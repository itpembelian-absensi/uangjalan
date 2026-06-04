import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { LogIn, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { loadLoginPrefs, saveLoginPrefs } from '../auth/loginStorage';

const Login = () => {
  const { user, loading, login, refresh } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [autoLogin, setAutoLogin] = useState(false);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [info, setInfo] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const prefs = loadLoginPrefs();
    setAutoLogin(prefs.autoLogin);
    if (prefs.username) setUsername(prefs.username);
    if (prefs.autoLogin) {
      setNeedsPassword(true);
      setInfo('Session habis. Masukkan password sekali untuk melanjutkan Auto Login.');
    }
  }, []);

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card glass-panel">
          <p>Memuat...</p>
        </div>
      </div>
    );
  }

  if (user) {
    const redirectTo = location.state?.from?.pathname || '/';
    return <Navigate to={redirectTo} replace />;
  }

  const showPasswordField = !autoLogin || needsPassword;

  const handleAutoLoginToggle = async (checked) => {
    setAutoLogin(checked);
    saveLoginPrefs(checked, username);
    setError('');
    setInfo('');

    if (!checked) {
      setNeedsPassword(false);
      return;
    }

    setPassword('');
    const existing = await refresh();
    if (existing) return;

    setNeedsPassword(true);
    setInfo('Masukkan password sekali. Setelah berhasil login, kunjungan berikutnya tidak perlu password.');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    setInfo('');

    try {
      if (autoLogin && !password.trim() && !needsPassword) {
        const existing = await refresh();
        if (existing) return;
        setNeedsPassword(true);
        setInfo('Session habis. Masukkan password sekali untuk melanjutkan.');
        return;
      }

      if (!password.trim()) {
        setError('Password wajib diisi.');
        return;
      }

      await login(username.trim(), password, autoLogin);
      saveLoginPrefs(autoLogin, username);
      setNeedsPassword(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const passwordBlock = (
    <label>
      Password
      <div className="login-password-wrap">
        <input
          className="login-input login-input-password"
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        <button
          type="button"
          className="login-password-toggle"
          onClick={() => setShowPassword((v) => !v)}
          aria-label={showPassword ? 'Sembunyikan password' : 'Tampilkan password'}
          title={showPassword ? 'Sembunyikan password' : 'Tampilkan password'}
        >
          {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
        </button>
      </div>
    </label>
  );

  return (
    <div className="login-page">
      <div className="login-card glass-panel">
        <div className="login-header">
          <div className="login-icon">
            <LogIn size={28} />
          </div>
          <h1>Biaya Pengiriman</h1>
          <p>Masuk ke akun Anda untuk melanjutkan</p>
        </div>

        {error && <div className="alert-error">{error}</div>}
        {info && <div className="alert-info">{info}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Username
            <input
              className="login-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          {showPasswordField ? (
            passwordBlock
          ) : (
            <p className="login-auto-hint">
              Session masih aktif. Klik <strong>Masuk</strong> tanpa password.
            </p>
          )}

          <label className="login-checkbox">
            <input
              type="checkbox"
              checked={autoLogin}
              onChange={(e) => handleAutoLoginToggle(e.target.checked)}
            />
            <span>Auto Login (ingat saya, tanpa isi password)</span>
          </label>

          <button type="submit" className="btn btn-primary login-submit" disabled={submitting}>
            {submitting ? 'Memproses...' : 'Masuk'}
          </button>
        </form>

        <div className="login-roles">
          <p>
            <strong>Auto Login ON:</strong> setelah login sekali, kunjungan berikutnya tanpa password (30 hari).
            <br />
            <strong>Auto Login OFF:</strong> wajib isi password setiap login (8 jam).
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
