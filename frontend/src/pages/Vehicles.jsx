import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import GlassCard from '../components/GlassCard';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import { apiFetch } from '../api';
import {
  useCrudWrite,
  crudTableGridSpan,
  CrudActionsHeader,
  CrudActionsCell,
} from '../components/CrudWriteAccess';

const emptyForm = { plate_number: '', brand_id: '', type_id: '' };

const VehicleFormFields = ({ values, onChange, brands, types }) => (
  <>
    <div className="form-group">
      <label className="form-label">Plat Nomor</label>
      <input
        type="text"
        className="form-input"
        placeholder="B 1234 CD"
        value={values.plate_number}
        onChange={(e) => onChange({ ...values, plate_number: e.target.value })}
        required
      />
    </div>
    <div className="form-group">
      <label className="form-label">Merek</label>
      <select
        className="form-select"
        value={values.brand_id}
        onChange={(e) => onChange({ ...values, brand_id: e.target.value })}
        required
      >
        <option value="">-- Pilih Merek --</option>
        {brands.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
    </div>
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label className="form-label">Jenis Kendaraan</label>
      <select
        className="form-select"
        value={values.type_id}
        onChange={(e) => onChange({ ...values, type_id: e.target.value })}
        required
      >
        <option value="">-- Pilih Jenis --</option>
        {types.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      {types.length === 0 && (
        <small style={{ color: 'var(--text-secondary)' }}>
          Belum ada jenis. Atur di{' '}
          <Link to="/vehicle-types" style={{ color: '#4f46e5' }}>
            Master Jenis Kendaraan
          </Link>
          .
        </small>
      )}
    </div>
  </>
);

const Vehicles = () => {
  const canWrite = useCrudWrite();
  const [vehicles, setVehicles] = useState([]);
  const [brands, setBrands] = useState([]);
  const [types, setTypes] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  const fetchData = async () => {
    const errors = [];
    try {
      const vData = await apiFetch('/api/vehicles');
      setVehicles(vData);
    } catch (err) {
      errors.push(err.message);
    }
    try {
      const bData = await apiFetch('/api/vehicle-brands');
      setBrands(bData);
    } catch (err) {
      errors.push(err.message);
    }
    try {
      const tData = await apiFetch('/api/vehicle-types');
      setTypes(tData);
    } catch (err) {
      errors.push(err.message);
    }
    setError(errors.length ? errors[0] : '');
  };

  useEffect(() => {
    fetchData();
  }, []);

  const buildPayload = (values) => ({
    plate_number: values.plate_number.trim(),
    brand_id: parseInt(values.brand_id, 10),
    type_id: values.type_id ? parseInt(values.type_id, 10) : null,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.plate_number.trim() || !form.brand_id || !form.type_id) return;

    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload(form)),
      });
      setForm(emptyForm);
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (vehicle) => {
    if (!canWrite) return;
    setEditId(vehicle.id);
    setEditForm({
      plate_number: vehicle.plate_number,
      brand_id: String(vehicle.brand_id),
      type_id: vehicle.type_id ? String(vehicle.type_id) : '',
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
    if (!editForm.plate_number.trim() || !editForm.brand_id || !editForm.type_id || !editId) return;

    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/vehicles/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload(editForm)),
      });
      closeEdit();
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (vehicle) => {
    if (!window.confirm(`Hapus kendaraan plat "${vehicle.plate_number}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/vehicles/${vehicle.id}`, { method: 'DELETE' });
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const getBrandName = (id) => brands.find((b) => b.id === id)?.name || '-';

  const canSave = brands.length > 0 && types.length > 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Kendaraan</h1>
          <p>Plat nomor, merek, dan jenis kendaraan dari master data.</p>
        </div>
      </div>

      {error && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
          {error}
        </div>
      )}

      {brands.length === 0 && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a' }}>
          Isi data <strong>Merek</strong> terlebih dahulu.
        </div>
      )}

      {types.length === 0 && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a' }}>
          Isi data <strong>Jenis Kendaraan</strong> terlebih dahulu di menu Jenis Kendaraan.
        </div>
      )}

      <div className="grid-cols-3">
        {canWrite && (
        <div style={{ gridColumn: 'span 1' }}>
          <GlassCard title="Tambah Kendaraan">
            <form onSubmit={handleSubmit}>
              <VehicleFormFields values={form} onChange={setForm} brands={brands} types={types} />
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '1rem' }}
                disabled={saving || !canSave}
              >
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Kendaraan'}
              </button>
            </form>
          </GlassCard>
        </div>
        )}

        <div style={{ gridColumn: `span ${crudTableGridSpan(canWrite)}` }}>
          <div className="table-container glass-panel" style={{ padding: 0, overflowX: 'auto' }}>
            <table className="glass-table">
              <thead>
                <tr>
                  <th>Plat Nomor</th>
                  <th>Merek</th>
                  <th>Jenis Kendaraan</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {vehicles.map((v) => (
                  <tr key={v.id}>
                    <td style={{ fontWeight: 600, color: 'var(--accent-color)' }}>{v.plate_number}</td>
                    <td>{getBrandName(v.brand_id)}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{v.type_name || '-'}</td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(v)}
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(v)}
                        title="Hapus"
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {vehicles.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 4 : 3} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      Belum ada data kendaraan
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
                <h2>Edit Kendaraan</h2>
              </div>
              <div className="modal-body">
                <VehicleFormFields values={editForm} onChange={setEditForm} brands={brands} types={types} />
              </div>
              <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={closeEdit}>
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving || !canSave}>
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

export default Vehicles;
