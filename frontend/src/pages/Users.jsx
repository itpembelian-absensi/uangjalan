import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Edit2, Shield } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useCrudWrite, CrudActionsHeader, CrudActionsCell } from '../components/CrudWriteAccess';

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'finance', label: 'Finance & Accounting' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'gudang', label: 'Gudang' },
];

const emptyForm = {
  username: '',
  full_name: '',
  password: '',
  role: 'marketing',
  is_active: true,
};

const Users = () => {
  const { user: currentUser } = useAuth();
  const canWrite = useCrudWrite();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ ...emptyForm, password: '' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchUsers = async () => {
    try {
      const data = await apiFetch('/api/users');
      setItems(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username.trim(),
          full_name: form.full_name.trim(),
          password: form.password,
          role: form.role,
          is_active: form.is_active,
        }),
      });
      setForm(emptyForm);
      await fetchUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (item) => {
    setEditId(item.id);
    setEditForm({
      username: item.username,
      full_name: item.full_name,
      password: '',
      role: item.role,
      is_active: item.is_active,
    });
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditForm({ ...emptyForm, password: '' });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editId) return;
    setSaving(true);
    setError('');
    try {
      const payload = {
        full_name: editForm.full_name.trim(),
        role: editForm.role,
        is_active: editForm.is_active,
      };
      if (editForm.password.trim()) {
        payload.password = editForm.password;
      }
      await apiFetch(`/api/users/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      closeEdit();
      await fetchUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Hapus user ini?')) return;
    setError('');
    try {
      await apiFetch(`/api/users/${id}`, { method: 'DELETE' });
      await fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Manajemen User</h1>
          <p>Kelola akun login dan role akses pengguna</p>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className={canWrite ? 'grid-2' : ''}>
        {canWrite && (
        <GlassCard title="Tambah User Baru">
          <form onSubmit={handleSubmit} className="form-grid">
            <label>
              Username
              <input
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                required
              />
            </label>
            <label>
              Nama Lengkap
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </label>
            <label>
              Role
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Aktif
            </label>
            <button type="submit" className="btn btn-primary form-submit" disabled={saving}>
              <Plus size={18} /> {saving ? 'Menyimpan...' : 'Tambah User'}
            </button>
          </form>
        </GlassCard>
        )}

        <GlassCard title="Daftar User">
          <div className="table-container users-table-wrap">
            <table className="glass-table users-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Nama</th>
                  <th>Role</th>
                  <th>Status</th>
                  <CrudActionsHeader canWrite={canWrite} label="Aksi" align="left" />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.username}</td>
                    <td>{item.full_name}</td>
                    <td>
                      <span className="role-badge">
                        <Shield size={14} />
                        {item.role_label}
                      </span>
                    </td>
                    <td>{item.is_active ? 'Aktif' : 'Nonaktif'}</td>
                    <CrudActionsCell canWrite={canWrite} align="left">
                      <button type="button" className="btn-icon" onClick={() => openEdit(item)}>
                        <Edit2 size={16} />
                      </button>
                      {item.id !== currentUser?.id && (
                        <button
                          type="button"
                          className="btn-icon btn-danger"
                          onClick={() => handleDelete(item.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </CrudActionsCell>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>

      {isModalOpen && canWrite && (
        <div className="modal-overlay" onClick={closeEdit}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()}>
            <h3>Edit User</h3>
            <form onSubmit={handleEditSubmit} className="form-grid">
              <label>
                Username
                <input value={editForm.username} disabled />
              </label>
              <label>
                Nama Lengkap
                <input
                  value={editForm.full_name}
                  onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                  required
                />
              </label>
              <label>
                Password Baru (kosongkan jika tidak diubah)
                <input
                  type="password"
                  value={editForm.password}
                  onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                />
              </label>
              <label>
                Role
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  disabled={editId === currentUser?.id}
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  disabled={editId === currentUser?.id}
                />
                Aktif
              </label>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeEdit}>Batal</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Menyimpan...' : 'Simpan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Users;
