import React, { useState, useEffect } from 'react';
import { Save, Upload, X, ShieldCheck } from 'lucide-react';
import { useAppSettings } from '../context/AppSettingsContext';

const AppSettings = () => {
  const { settings, refreshSettings } = useAppSettings();
  const [formData, setFormData] = useState({
    app_name: '',
    app_subtitle: '',
    logo_base64: null,
    favicon_base64: null,
    finance_can_unlock_customer: false,
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (settings) {
      setFormData({
        app_name: settings.app_name || '',
        app_subtitle: settings.app_subtitle || '',
        logo_base64: settings.logo_base64 || null,
        favicon_base64: settings.favicon_base64 || null,
        finance_can_unlock_customer: settings.finance_can_unlock_customer || false,
      });
    }
  }, [settings]);

  const handleFileChange = (e, field) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 1024 * 1024) { // 1MB limit
      setError('Ukuran file maksimal 1MB');
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      setFormData(prev => ({
        ...prev,
        [field]: reader.result,
      }));
    };
    reader.readAsDataURL(file);
  };

  const removeImage = (field) => {
    setFormData(prev => ({
      ...prev,
      [field]: null,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    setError('');

    try {
      const response = await fetch('/api/app-settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          app_name: formData.app_name,
          app_subtitle: formData.app_subtitle,
          // Extract base64 part if it contains data:image/...;base64,
          logo_base64: formData.logo_base64,
          favicon_base64: formData.favicon_base64,
          finance_can_unlock_customer: formData.finance_can_unlock_customer,
        }),
      });

      if (!response.ok) {
        throw new Error('Gagal menyimpan pengaturan');
      }

      setMessage('Pengaturan berhasil disimpan');
      refreshSettings(); // Update global context
    } catch (err) {
      setError(err.message || 'Terjadi kesalahan');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Pengaturan Aplikasi</h1>
      </div>

      <div className="card" style={{ maxWidth: '600px' }}>
        <form onSubmit={handleSubmit} className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
          
          <div className="form-group">
            <label>Nama Aplikasi</label>
            <input
              type="text"
              value={formData.app_name}
              onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
              required
              className="form-control"
              placeholder="Contoh: Biaya Pengiriman"
            />
          </div>

          <div className="form-group">
            <label>Subtitle / Tagline</label>
            <input
              type="text"
              value={formData.app_subtitle}
              onChange={(e) => setFormData({ ...formData, app_subtitle: e.target.value })}
              className="form-control"
              placeholder="Contoh: Premium Logistics"
            />
          </div>

          <div className="form-group">
            <label>Logo Sidebar</label>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Rekomendasi ukuran: 64x64px. Maksimal 1MB. (PNG/JPG/SVG)
            </p>
            {formData.logo_base64 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
                <img 
                  src={formData.logo_base64.startsWith('data:') ? formData.logo_base64 : `data:image/png;base64,${formData.logo_base64}`} 
                  alt="Logo Preview" 
                  style={{ width: '48px', height: '48px', objectFit: 'contain', background: '#f1f5f9', borderRadius: '4px', padding: '4px' }} 
                />
                <button type="button" onClick={() => removeImage('logo_base64')} className="btn btn-danger btn-sm" style={{ padding: '0.25rem 0.5rem' }}>
                  <X size={14} /> Hapus
                </button>
              </div>
            ) : (
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleFileChange(e, 'logo_base64')}
                className="form-control"
                style={{ padding: '0.4rem' }}
              />
            )}
          </div>

          <div className="form-group">
            <label>Favicon (Ikon Tab Browser)</label>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Rekomendasi ukuran: 32x32px atau 16x16px (Format .ico atau .png). Maksimal 1MB.
            </p>
            {formData.favicon_base64 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
                <img 
                  src={formData.favicon_base64.startsWith('data:') ? formData.favicon_base64 : `data:image/png;base64,${formData.favicon_base64}`} 
                  alt="Favicon Preview" 
                  style={{ width: '32px', height: '32px', objectFit: 'contain', background: '#f1f5f9', borderRadius: '4px', padding: '4px' }} 
                />
                <button type="button" onClick={() => removeImage('favicon_base64')} className="btn btn-danger btn-sm" style={{ padding: '0.25rem 0.5rem' }}>
                  <X size={14} /> Hapus
                </button>
              </div>
            ) : (
              <input
                type="file"
                accept="image/x-icon,image/png,image/jpeg"
                onChange={(e) => handleFileChange(e, 'favicon_base64')}
                className="form-control"
                style={{ padding: '0.4rem' }}
              />
            )}
          </div>

          <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--glass-border, #e5e7eb)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <ShieldCheck size={18} style={{ color: '#6366f1' }} />
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Kontrol Akses</h3>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '1rem',
                borderRadius: '8px',
                background: formData.finance_can_unlock_customer
                  ? 'rgba(16, 185, 129, 0.08)'
                  : 'rgba(107, 114, 128, 0.06)',
                border: `1px solid ${formData.finance_can_unlock_customer ? 'rgba(16, 185, 129, 0.25)' : 'rgba(107, 114, 128, 0.15)'}`,
                transition: 'all 0.2s ease',
              }}>
                <input
                  type="checkbox"
                  id="finance_can_unlock_customer"
                  checked={formData.finance_can_unlock_customer}
                  onChange={(e) => setFormData({ ...formData, finance_can_unlock_customer: e.target.checked })}
                  style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                />
                <div>
                  <label htmlFor="finance_can_unlock_customer" style={{ cursor: 'pointer', fontWeight: 500, display: 'block' }}>
                    Finance dapat unlock Master Customer
                  </label>
                  <small style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                    Cadangan lama. Hak kunci/buka Finance utama diatur di <strong>Matriks Akses → Kunci Finance Customer</strong> (Lihat &amp; Edit = bisa kunci &amp; buka).
                  </small>
                </div>
              </div>
            </div>
          </div>

          {error && <div className="alert alert-error">{error}</div>}
          {message && <div className="alert alert-success" style={{ background: '#dcfce7', color: '#166534', padding: '0.75rem', borderRadius: '0.375rem' }}>{message}</div>}

          <div style={{ marginTop: '1rem' }}>
            <button type="submit" disabled={loading} className="btn btn-primary">
              <Save size={18} />
              {loading ? 'Menyimpan...' : 'Simpan Pengaturan'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AppSettings;
