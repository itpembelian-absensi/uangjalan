import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Eye, XCircle, Save } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';
import { useAuth } from '../auth/AuthContext';

const ACCESS_META = {
  full: { label: 'Lihat & Edit', className: 'access-full', icon: CheckCircle2 },
  read: { label: 'Lihat saja', className: 'access-read', icon: Eye },
  none: { label: 'Tidak ada akses', className: 'access-none', icon: XCircle },
};

/** Label khusus untuk baris hak yang bukan navigasi menu. */
const SPECIAL_MENU_LABELS = {
  customer_finance_lock: {
    full: 'Bisa kunci & buka',
    read: 'Lihat status saja',
    none: 'Tidak bisa ubah',
  },
};

function levelLabel(menuId, level, legend) {
  return SPECIAL_MENU_LABELS[menuId]?.[level] || legend[level] || level;
}

function AccessBadge({ level, highlight, label }) {
  const meta = ACCESS_META[level];
  const Icon = meta.icon;
  return (
    <span className={`access-badge ${meta.className} ${highlight ? 'access-badge-current' : ''}`}>
      <Icon size={18} />
      <span>{label || meta.label}</span>
    </span>
  );
}

const AccessMatrix = () => {
  const { user } = useAuth();
  const [matrix, setMatrix] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [savingKey, setSavingKey] = useState(null);

  const loadMatrix = useCallback(() => {
    return apiFetch('/api/auth/access-matrix').then(setMatrix);
  }, []);

  useEffect(() => {
    loadMatrix().catch((err) => setError(err.message));
  }, [loadMatrix]);

  const handleAccessChange = async (menuId, role, accessLevel) => {
    const key = `${menuId}-${role}`;
    setSavingKey(key);
    setError('');
    setSuccess('');
    try {
      const updated = await apiFetch('/api/auth/access-matrix', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          menu_id: menuId,
          role,
          access_level: accessLevel,
        }),
      });
      setMatrix(updated);
      setSuccess('Matriks akses berhasil disimpan.');
    } catch (err) {
      setError(err.message);
      await loadMatrix();
    } finally {
      setSavingKey(null);
    }
  };

  if (error && !matrix) {
    return <div className="alert-error">{error}</div>;
  }

  if (!matrix) {
    return (
      <div className="page-header">
        <h1>Matriks Akses</h1>
        <p>Memuat...</p>
      </div>
    );
  }

  const colCount = matrix.roles.length + 1;
  const levels = matrix.access_levels || ['full', 'read', 'none'];

  return (
    <div className="access-matrix-page">
      <div className="page-header">
        <div>
          <h1>Matriks Akses per Menu</h1>
          <p>
            {matrix.can_edit
              ? 'Admin dapat mengubah hak akses per menu dan role. Perubahan langsung aktif.'
              : 'Referensi hak akses setiap menu berdasarkan role pengguna'}
          </p>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {success && <div className="alert-info">{success}</div>}

      <GlassCard title="Role Anda Saat Ini" className="access-role-card">
        <p className="access-role-text">
          Login sebagai <strong>{user?.full_name}</strong> — role{' '}
          <strong>{user?.role_label}</strong>
        </p>
      </GlassCard>

      <div className="access-legend">
        {Object.entries(matrix.legend).map(([key, label]) => {
          const meta = ACCESS_META[key];
          const Icon = meta.icon;
          return (
            <span key={key} className={`access-legend-item ${meta.className}`}>
              <Icon size={18} />
              {label}
            </span>
          );
        })}
      </div>

      {matrix.can_edit && (
        <GlassCard title="Panduan Edit" className="access-edit-hint">
          <p>
            Pilih level akses pada setiap sel. <strong>Lihat & Edit</strong> = buka menu + ubah data,{' '}
            <strong>Lihat saja</strong> = hanya lihat, <strong>Tidak ada akses</strong> = menu disembunyikan.
            Baris <strong>Kunci Finance Customer</strong> mengatur siapa yang boleh kunci/buka kunci Finance di master customer (bukan menu navigasi).
            Admin selalu memiliki akses penuh ke Manajemen User, Matriks Akses, dan Kunci Finance Customer.
          </p>
        </GlassCard>
      )}

      <GlassCard
        title={matrix.can_edit ? 'Tabel Hak Akses (dapat diedit)' : 'Tabel Hak Akses'}
        className="access-table-card"
      >
        <div className="table-container access-matrix-wrap">
          <table className="glass-table access-matrix-table">
            <thead>
              <tr>
                <th className="access-col-menu">Menu</th>
                {matrix.roles.map((role) => (
                  <th key={role.id} className="access-col-role">
                    {role.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.sections.map((section) => (
                <React.Fragment key={section.name}>
                  <tr className="access-section-row">
                    <td colSpan={colCount}>{section.name}</td>
                  </tr>
                  {section.items.map((item) => (
                    <tr key={item.id} className="access-data-row">
                      <td className="access-menu-cell">
                        <div className="access-menu-label">{item.label}</div>
                        <div className="access-menu-path">
                          {item.id === 'customer_finance_lock'
                            ? 'Hak khusus (lock/unlock Finance)'
                            : item.path}
                        </div>
                      </td>
                      {matrix.roles.map((role) => {
                        const level = item.access[role.id];
                        const highlight = user?.role === role.id;
                        const cellKey = `${item.id}-${role.id}`;
                        const isSaving = savingKey === cellKey;

                        if (matrix.can_edit) {
                          return (
                            <td key={role.id} className="access-role-cell access-role-cell-edit">
                              <select
                                className={`access-level-select ${ACCESS_META[level]?.className || ''}`}
                                value={level}
                                disabled={isSaving}
                                onChange={(e) =>
                                  handleAccessChange(item.id, role.id, e.target.value)
                                }
                              >
                                {levels.map((lv) => (
                                  <option key={lv} value={lv}>
                                    {levelLabel(item.id, lv, matrix.legend)}
                                  </option>
                                ))}
                              </select>
                              {isSaving && (
                                <span className="access-saving">
                                  <Save size={14} /> Menyimpan...
                                </span>
                              )}
                            </td>
                          );
                        }

                        return (
                          <td key={role.id} className="access-role-cell">
                            <AccessBadge
                              level={level}
                              highlight={highlight}
                              label={levelLabel(item.id, level, matrix.legend)}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
};

export default AccessMatrix;
