import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassCard from '../components/GlassCard';
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

const buildRatesForm = (golonganList, existingRates = []) => {
  const existingById = Object.fromEntries(
    (existingRates || []).map((r) => [r.golongan_id, r])
  );
  const active = [...golonganList]
    .filter((g) => g.is_active)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id);
  const seen = new Set(active.map((g) => g.id));

  const rows = active.map((g) => ({
    golongan_id: g.id,
    golongan_name: g.name,
    golongan_code: g.code,
    rate:
      existingById[g.id]?.rate != null ? String(existingById[g.id].rate) : '',
  }));

  for (const r of existingRates || []) {
    if (!seen.has(r.golongan_id)) {
      rows.push({
        golongan_id: r.golongan_id,
        golongan_name: r.golongan_name || '-',
        golongan_code: r.golongan_code || '?',
        rate: r.rate != null ? String(r.rate) : '',
        inactive: true,
      });
    }
  }

  return rows;
};

const emptySectionForm = (golonganList) => ({
  name: '',
  length_km: '',
  sort_order: '',
  is_active: true,
  rates: buildRatesForm(golonganList),
});

const TollSections = () => {
  const canWrite = useCrudWrite();
  const [sections, setSections] = useState([]);
  const [golonganList, setGolonganList] = useState([]);
  const [form, setForm] = useState({ name: '', length_km: '', sort_order: '', is_active: true, rates: [] });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', length_km: '', sort_order: '', is_active: true, rates: [] });

  const fetchGolongan = async () => {
    const data = await apiFetch('/api/toll-golongan');
    setGolonganList(data);
    return data;
  };

  const fetchSections = async () => {
    const data = await apiFetch('/api/toll-sections');
    setSections(data);
    setError('');
  };

  useEffect(() => {
    (async () => {
      try {
        const gol = await fetchGolongan();
        setForm(emptySectionForm(gol));
        await fetchSections();
      } catch (err) {
        setError(err.message);
      }
    })();
  }, []);

  const payloadFromForm = (values) => ({
    name: values.name.trim(),
    length_km: parseFloat(values.length_km) || 1,
    sort_order: parseInt(values.sort_order, 10) || 0,
    is_active: values.is_active,
    rates: values.rates
      .filter((r) => r.rate !== '' && !Number.isNaN(parseFloat(r.rate)))
      .map((r) => ({
        golongan_id: r.golongan_id,
        rate: parseFloat(r.rate) || 0,
      })),
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/toll-sections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadFromForm(form)),
      });
      setForm(emptySectionForm(golonganList));
      await fetchSections();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = async (row) => {
    if (!canWrite) return;
    setError('');
    try {
      const gol = await fetchGolongan();
      setEditId(row.id);
      setEditForm({
        name: row.name,
        length_km: String(row.length_km),
        sort_order: String(row.sort_order),
        is_active: row.is_active,
        rates: buildRatesForm(gol, row.rates || []),
      });
      setIsModalOpen(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditForm(emptySectionForm(golonganList));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editId || !editForm.name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/toll-sections/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadFromForm(editForm)),
      });
      closeEdit();
      await fetchGolongan();
      await fetchSections();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Hapus ruas tol "${row.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/toll-sections/${row.id}`, { method: 'DELETE' });
      await fetchSections();
    } catch (err) {
      setError(err.message);
    }
  };

  const updateRate = (values, onChange, golonganId, rateValue) => {
    onChange({
      ...values,
      rates: values.rates.map((r) =>
        r.golongan_id === golonganId ? { ...r, rate: rateValue } : r
      ),
    });
  };

  const SectionFields = ({ values, onChange, idPrefix = '' }) => (
    <>
      <div className="form-group">
        <label className="form-label">Nama Ruas Tol</label>
        <input
          type="text"
          className="form-input"
          placeholder="Misal: Japek, JORR"
          value={values.name}
          onChange={(e) => onChange({ ...values, name: e.target.value })}
          required
        />
      </div>
      <div className="grid-cols-2" style={{ gap: '1rem' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Panjang Ruas (km)</label>
          <input
            type="number"
            className="form-input"
            min="0.1"
            step="0.1"
            value={values.length_km}
            onChange={(e) => onChange({ ...values, length_km: e.target.value })}
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
      <div
        className="form-group"
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}
      >
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

      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label" style={{ marginBottom: '0.25rem' }}>
          Tarif per Golongan (Rp)
        </label>
        <small style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
          Daftar golongan dari{' '}
          <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
            Master Golongan Tol
          </Link>
          .
        </small>
        {values.rates.length === 0 ? (
          <p style={{ fontSize: '0.9rem', color: '#92400e' }}>
            Belum ada golongan aktif. Tambahkan dulu di{' '}
            <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
              Master Golongan Tol
            </Link>
            .
          </p>
        ) : (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {values.rates.map((r) => (
              <div
                key={r.golongan_id}
                style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: '0.5rem', alignItems: 'center' }}
              >
                <span style={{ fontSize: '0.9rem' }}>
                  <strong>Gol {r.golongan_code}</strong>
                  {r.golongan_name ? ` — ${r.golongan_name}` : ''}
                  {r.inactive ? ' (nonaktif)' : ''}
                </span>
                <input
                  type="number"
                  className="form-input"
                  min="0"
                  step="500"
                  placeholder="0"
                  value={r.rate}
                  onChange={(e) => updateRate(values, onChange, r.golongan_id, e.target.value)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );

  const activeGolongan = golonganList.filter((g) => g.is_active);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Ruas &amp; Tarif Tol</h1>
          <p>
            Kelola ruas tol dan tarif per golongan. Master golongan di{' '}
            <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
              Golongan Tol
            </Link>
            .
          </p>
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
          <GlassCard title="Tambah Ruas Tol">
            <form onSubmit={handleSubmit}>
              <SectionFields values={form} onChange={setForm} idPrefix="add_" />
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '1rem' }}
                disabled={saving || activeGolongan.length === 0}
              >
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Ruas'}
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
                  <th>Urutan</th>
                  <th>Ruas Tol</th>
                  <th style={{ textAlign: 'right' }}>Panjang (km)</th>
                  {activeGolongan.map((g) => (
                    <th key={g.id} style={{ textAlign: 'right' }}>
                      Gol {g.code}
                    </th>
                  ))}
                  <th>Status</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {sections.map((row) => (
                  <tr key={row.id}>
                    <td>{row.sort_order}</td>
                    <td style={{ fontWeight: 500 }}>{row.name}</td>
                    <td style={{ textAlign: 'right' }}>{Number(row.length_km).toLocaleString('id-ID')}</td>
                    {activeGolongan.map((g) => {
                      const rate = (row.rates || []).find((r) => r.golongan_id === g.id);
                      return (
                        <td key={g.id} style={{ textAlign: 'right', fontSize: '0.85rem' }}>
                          {rate ? formatIDR(rate.rate) : '-'}
                        </td>
                      );
                    })}
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
                {sections.length === 0 && (
                  <tr>
                    <td
                      colSpan={(canWrite ? 5 : 4) + activeGolongan.length}
                      style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}
                    >
                      Belum ada ruas tol
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
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '560px' }}>
            <form onSubmit={handleEditSubmit}>
              <div className="modal-header">
                <h2>Edit Ruas Tol</h2>
              </div>
              <div className="modal-body">
                <SectionFields values={editForm} onChange={setEditForm} idPrefix="edit_" />
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

export default TollSections;
