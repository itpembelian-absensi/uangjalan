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

const VehicleBrands = () => {
  const canWrite = useCrudWrite();
  const [brands, setBrands] = useState([]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editName, setEditName] = useState('');

  const fetchBrands = async () => {
    try {
      const data = await apiFetch('/api/vehicle-brands');
      setBrands(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchBrands();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/vehicle-brands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      });
      setName('');
      await fetchBrands();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (brand) => {
    if (!canWrite) return;
    setEditId(brand.id);
    setEditName(brand.name);
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditName('');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editName.trim() || !editId) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/vehicle-brands/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName.trim() }),
      });
      closeEdit();
      await fetchBrands();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (brand) => {
    if (!window.confirm(`Hapus merek "${brand.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/vehicle-brands/${brand.id}`, { method: 'DELETE' });
      await fetchBrands();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Merek Kendaraan</h1>
          <p>Kelola data merek kendaraan</p>
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
          <GlassCard title="Tambah Merek">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Nama Merek</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Misal: Hino, Mitsubishi"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={saving}>
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Merek'}
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
                  <th>Merek</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {brands.map((b) => (
                  <tr key={b.id}>
                    <td>{b.id}</td>
                    <td style={{ fontWeight: 500 }}>{b.name}</td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(b)}
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(b)}
                        title="Hapus"
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {brands.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 3 : 2} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      Belum ada data merek
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
                <h2>Edit Merek</h2>
              </div>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Nama Merek</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
              </div>
              <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={closeEdit}>
                  Batal
                </button>
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

export default VehicleBrands;
