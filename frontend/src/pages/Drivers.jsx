import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import { apiFetch } from '../api';
import {
  useCrudWrite,
  crudTableGridSpan,
  CrudActionsHeader,
  CrudActionsCell,
} from '../components/CrudWriteAccess';

const emptyForm = { name: '', phone: '' };

const Drivers = () => {
  const canWrite = useCrudWrite();
  const [drivers, setDrivers] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  const fetchDrivers = async () => {
    try {
      const data = await apiFetch('/api/drivers');
      setDrivers(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchDrivers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;

    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/drivers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          phone: form.phone.trim() || null,
        }),
      });
      setForm(emptyForm);
      await fetchDrivers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (driver) => {
    if (!canWrite) return;
    setEditId(driver.id);
    setEditForm({
      name: driver.name,
      phone: driver.phone || '',
    });
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditForm(emptyForm);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editForm.name.trim() || !editId) return;

    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/drivers/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editForm.name.trim(),
          phone: editForm.phone.trim() || null,
        }),
      });
      closeEdit();
      await fetchDrivers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (driver) => {
    if (!window.confirm(`Hapus supir "${driver.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/drivers/${driver.id}`, { method: 'DELETE' });
      await fetchDrivers();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Drivers</h1>
          <p>Manage your drivers and fleet operators</p>
        </div>
      </div>

      {error && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
          {error}
        </div>
      )}

      <div className="grid-cols-3">
        {canWrite && (
        <div style={{ gridColumn: 'span 1' }}>
          <GlassCard title="Add New Driver">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Driver Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="John Doe"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Phone Number (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="08123456789"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={saving}>
                <Plus size={18} /> {saving ? 'Saving...' : 'Add Driver'}
              </button>
            </form>
          </GlassCard>
        </div>
        )}

        <div style={{ gridColumn: `span ${crudTableGridSpan(canWrite)}` }}>
          <div className="table-container glass-panel" style={{ padding: 0 }}>
            <table className="glass-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Phone</th>
                  <CrudActionsHeader canWrite={canWrite} label="Actions" />
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr key={d.id}>
                    <td>{d.id}</td>
                    <td style={{ fontWeight: 500 }}>{d.name}</td>
                    <td>{d.phone || '-'}</td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(d)}
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(d)}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {drivers.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 4 : 3} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      No drivers found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {isModalOpen && canWrite && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleEditSubmit}>
              <div className="modal-header">
                <h2>Edit Driver</h2>
              </div>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Driver Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    required
                    autoFocus
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Phone Number (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editForm.phone}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                  />
                </div>
              </div>
              <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={closeEdit}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Drivers;
