import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';
import {
  useCrudWrite,
  crudTableGridSpan,
  CrudActionsHeader,
  CrudActionsCell,
} from '../components/CrudWriteAccess';

const emptyForm = () => ({
  name: '',
  code: '',
  description: '',
  sort_order: '',
  is_active: true,
});

const TollGolongan = () => {
  const canWrite = useCrudWrite();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(emptyForm());
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm());

  const fetchItems = async () => {
    try {
      const data = await apiFetch('/api/toll-golongan');
      setItems(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.code.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/toll-golongan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          code: form.code.trim(),
          description: form.description.trim() || null,
          sort_order: parseInt(form.sort_order, 10) || 0,
          is_active: form.is_active,
        }),
      });
      setForm(emptyForm());
      await fetchItems();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (row) => {
    if (!canWrite) return;
    setEditId(row.id);
    setEditForm({
      name: row.name,
      code: row.code,
      description: row.description || '',
      sort_order: String(row.sort_order),
      is_active: row.is_active,
    });
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditForm(emptyForm());
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editId || !editForm.name.trim() || !editForm.code.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/toll-golongan/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editForm.name.trim(),
          code: editForm.code.trim(),
          description: editForm.description.trim() || null,
          sort_order: parseInt(editForm.sort_order, 10) || 0,
          is_active: editForm.is_active,
        }),
      });
      closeEdit();
      await fetchItems();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Hapus golongan "${row.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/toll-golongan/${row.id}`, { method: 'DELETE' });
      await fetchItems();
    } catch (err) {
      setError(err.message);
    }
  };

  const FormFields = ({ values, onChange, idPrefix = '' }) => (
    <>
      <div className="form-group">
        <label className="form-label">Nama Golongan</label>
        <input
          type="text"
          className="form-input"
          placeholder="Golongan II"
          value={values.name}
          onChange={(e) => onChange({ ...values, name: e.target.value })}
          required
        />
      </div>
      <div className="grid-cols-2" style={{ gap: '1rem' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Kode</label>
          <input
            type="text"
            className="form-input"
            placeholder="II"
            value={values.code}
            onChange={(e) => onChange({ ...values, code: e.target.value.toUpperCase() })}
            required
          />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Urutan</label>
          <input
            type="number"
            className="form-input"
            min="0"
            value={values.sort_order}
            onChange={(e) => onChange({ ...values, sort_order: e.target.value })}
          />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Keterangan</label>
        <input
          type="text"
          className="form-input"
          placeholder="Truk 2 gandar"
          value={values.description}
          onChange={(e) => onChange({ ...values, description: e.target.value })}
        />
      </div>
      <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: 0 }}>
        <input
          type="checkbox"
          id={`${idPrefix}is_active`}
          checked={values.is_active}
          onChange={(e) => onChange({ ...values, is_active: e.target.checked })}
        />
        <label htmlFor={`${idPrefix}is_active`} style={{ cursor: 'pointer' }}>
          Aktif
        </label>
      </div>
    </>
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Master Golongan Tol</h1>
          <p>Klasifikasi kendaraan untuk tarif tol (Gol II, III, IV, V). Dipilih saat atur ruas tol.</p>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
          }}
        >
          {error}
        </div>
      )}

      <div className="grid-cols-3">
        {canWrite && (
        <div style={{ gridColumn: 'span 1' }}>
          <GlassCard title="Tambah Golongan">
            <form onSubmit={handleSubmit}>
              <FormFields values={form} onChange={setForm} idPrefix="add_" />
              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={saving}>
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Golongan'}
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
                  <th>Urutan</th>
                  <th>Kode</th>
                  <th>Nama</th>
                  <th>Keterangan</th>
                  <th>Status</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.sort_order}</td>
                    <td style={{ fontWeight: 700 }}>{row.code}</td>
                    <td style={{ fontWeight: 500 }}>{row.name}</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{row.description || '-'}</td>
                    <td>
                      {row.is_active ? (
                        <span className="badge badge-green">Aktif</span>
                      ) : (
                        <span className="badge badge-red">Non-Aktif</span>
                      )}
                    </td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(row)}
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(row)}
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 6 : 5} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      Belum ada golongan tol
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
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '520px' }}>
            <form onSubmit={handleEditSubmit}>
              <div className="modal-header">
                <h2>Edit Golongan Tol</h2>
              </div>
              <div className="modal-body">
                <FormFields values={editForm} onChange={setEditForm} idPrefix="edit_" />
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

export default TollGolongan;
