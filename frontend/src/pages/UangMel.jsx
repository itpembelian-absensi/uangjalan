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

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const emptyForm = () => ({ name: '', amount: '' });

const FormFields = ({ values, onChange }) => (
  <>
    <div className="form-group">
      <label className="form-label">Nama Uang Mel</label>
      <input
        type="text"
        className="form-input"
        placeholder="Misal: Uang Mel Besar, Uang Mel Kecil"
        value={values.name}
        onChange={(e) => onChange({ ...values, name: e.target.value })}
        required
      />
    </div>
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label className="form-label">Nominal (Rp)</label>
      <input
        type="number"
        className="form-input"
        min="0"
        step="1000"
        placeholder="50000"
        value={values.amount}
        onChange={(e) => onChange({ ...values, amount: e.target.value })}
        required
      />
    </div>
  </>
);

const UangMel = () => {
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
      const data = await apiFetch('/api/uang-mel');
      setItems(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const payloadFromForm = (values) => ({
    name: values.name.trim(),
    amount: parseFloat(values.amount) || 0,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/uang-mel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadFromForm(form)),
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
    setEditForm({ name: row.name, amount: String(row.amount) });
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditForm(emptyForm());
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editId || !editForm.name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/uang-mel/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadFromForm(editForm)),
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
    if (!window.confirm(`Hapus Master Uang Mel "${row.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/uang-mel/${row.id}`, { method: 'DELETE' });
      await fetchItems();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Master Uang Mel</h1>
          <p>Kelola jenis dan nominal uang mel.</p>
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
          <GlassCard title="Tambah Uang Mel">
            <form onSubmit={handleSubmit}>
              <FormFields values={form} onChange={setForm} />
              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={saving}>
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Uang Mel'}
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
                  <th>Nama Uang Mel</th>
                  <th style={{ textAlign: 'right' }}>Nominal</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td style={{ fontWeight: 500 }}>{row.name}</td>
                    <td style={{ textAlign: 'right' }}>{formatIDR(row.amount)}</td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(row)}
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(row)}
                        title="Hapus"
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 4 : 3} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      Belum ada data Master Uang Mel
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
                <h2>Edit Uang Mel</h2>
              </div>
              <div className="modal-body">
                <FormFields values={editForm} onChange={setEditForm} />
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

export default UangMel;
