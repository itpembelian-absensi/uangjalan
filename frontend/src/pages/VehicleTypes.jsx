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

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const formatAmount = (num) =>
  new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(num) || 0);

const parseAmountInput = (val) => {
  if (val === '' || val == null) return '';
  const cleaned = String(val).replace(/[^\d]/g, '');
  return cleaned === '' ? '' : cleaned;
};

const amountToNumber = (val) => {
  if (val === '' || val == null) return 0;
  const n = parseFloat(parseAmountInput(val));
  return Number.isNaN(n) ? 0 : n;
};

const GolonganSelect = ({ value, onChange, id, golonganList }) => (
  <div className="form-group">
    <label className="form-label" htmlFor={id}>
      Golongan Tol
    </label>
    <select
      id={id}
      className="form-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">-- Pilih Golongan --</option>
      {golonganList.map((g) => (
        <option key={g.id} value={String(g.id)}>
          Gol {g.code} — {g.name}
        </option>
      ))}
    </select>
    {golonganList.length === 0 && (
      <small style={{ color: 'var(--text-secondary)' }}>
        Belum ada golongan. Atur di{' '}
        <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
          Master Golongan Tol
        </Link>
        .
      </small>
    )}
  </div>
);

const BbmSelect = ({ value, onChange, id, bbmList }) => (
  <div className="form-group">
    <label className="form-label" htmlFor={id}>
      BBM
    </label>
    <select
      id={id}
      className="form-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">-- Pilih BBM --</option>
      {bbmList.map((b) => (
        <option key={b.id} value={String(b.id)}>
          {b.name} — {formatIDR(b.price)}/L
        </option>
      ))}
    </select>
    {bbmList.length === 0 && (
      <small style={{ color: 'var(--text-secondary)' }}>
        Belum ada BBM. Atur di{' '}
        <Link to="/bbm" style={{ color: '#4f46e5' }}>
          Master BBM
        </Link>
        .
      </small>
    )}
  </div>
);

const KmPerLiterField = ({ value, onChange, id }) => (
  <div className="form-group">
    <label className="form-label" htmlFor={id}>
      1 Liter BBM = ... Km
    </label>
    <input
      id={id}
      type="number"
      className="form-input"
      min="0.1"
      step="0.1"
      placeholder="Misal: 8"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
    <small style={{ color: 'var(--text-secondary)' }}>
      Efisiensi bahan bakar per jenis kendaraan (km per liter).
    </small>
  </div>
);

const UangMelSelect = ({ value, onChange, id, uangMelList = [] }) => (
  <div className="form-group">
    <label className="form-label" htmlFor={id}>
      Master Uang Mel
    </label>
    <select
      id={id}
      className="form-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">-- Pilih Uang Mel --</option>
      {uangMelList.map((u) => (
        <option key={u.id} value={String(u.id)}>
          {u.name} — {formatIDR(u.amount)}
        </option>
      ))}
    </select>
    {uangMelList.length === 0 && (
      <small style={{ color: 'var(--text-secondary)' }}>
        Belum ada Uang Mel. Atur di{' '}
        <Link to="/uang-mel" style={{ color: '#4f46e5' }}>
          Master Uang Mel
        </Link>
        .
      </small>
    )}
  </div>
);

const VehicleTypes = () => {
  const canWrite = useCrudWrite();
  const [types, setTypes] = useState([]);
  const [golonganList, setGolonganList] = useState([]);
  const [bbmList, setBbmList] = useState([]);
  const [uangMelList, setUangMelList] = useState([]);
  const [name, setName] = useState('');
  const [tollGolonganId, setTollGolonganId] = useState('');
  const [bbmId, setBbmId] = useState('');
  const [uangMelId, setUangMelId] = useState('');
  const [kmPerLiter, setKmPerLiter] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editTollGolonganId, setEditTollGolonganId] = useState('');
  const [editBbmId, setEditBbmId] = useState('');
  const [editUangMelId, setEditUangMelId] = useState('');
  const [editKmPerLiter, setEditKmPerLiter] = useState('');

  const parseKmPerLiter = (value) => {
    if (value === '' || value == null) return null;
    const num = parseFloat(value);
    return Number.isNaN(num) || num <= 0 ? null : num;
  };

  const formatKmPerLiter = (value) =>
    value != null ? `${Number(value).toLocaleString('id-ID')} km/L` : '-';

  const fetchTypes = async () => {
    try {
      const data = await apiFetch('/api/vehicle-types');
      setTypes(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const fetchGolongan = async () => {
    try {
      const data = await apiFetch('/api/toll-golongan');
      setGolonganList(data.filter((g) => g.is_active));
    } catch (err) {
      setError(err.message);
    }
  };

  const fetchBbm = async () => {
    try {
      const data = await apiFetch('/api/bbm');
      setBbmList(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const fetchUangMel = async () => {
    try {
      const data = await apiFetch('/api/uang-mel');
      setUangMelList(data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchGolongan();
    fetchBbm();
    fetchUangMel();
    fetchTypes();
  }, []);

  const golonganLabel = (type) => {
    if (type.toll_golongan_code) {
      return `Gol ${type.toll_golongan_code}${type.toll_golongan_name ? ` — ${type.toll_golongan_name}` : ''}`;
    }
    return '-';
  };

  const bbmLabel = (type) => {
    if (type.bbm_name) {
      return type.bbm_price != null
        ? `${type.bbm_name} (${formatIDR(type.bbm_price)}/L)`
        : type.bbm_name;
    }
    return '-';
  };

  const buildPayload = (values) => ({
    name: values.name.trim(),
    toll_golongan_id: values.tollGolonganId ? parseInt(values.tollGolonganId, 10) : null,
    bbm_id: values.bbmId ? parseInt(values.bbmId, 10) : null,
    uang_mel_id: values.uangMelId ? parseInt(values.uangMelId, 10) : null,
    km_per_liter: parseKmPerLiter(values.kmPerLiter),
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/vehicle-types', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload({ name, tollGolonganId, bbmId, uangMelId, kmPerLiter })),
      });
      setName('');
      setTollGolonganId('');
      setBbmId('');
      setUangMelId('');
      setKmPerLiter('');
      await fetchTypes();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (type) => {
    if (!canWrite) return;
    setEditId(type.id);
    setEditName(type.name);
    setEditTollGolonganId(type.toll_golongan_id ? String(type.toll_golongan_id) : '');
    setEditBbmId(type.bbm_id ? String(type.bbm_id) : '');
    setEditUangMelId(type.uang_mel_id ? String(type.uang_mel_id) : '');
    setEditKmPerLiter(type.km_per_liter != null ? String(type.km_per_liter) : '');
    setIsModalOpen(true);
  };

  const closeEdit = () => {
    setIsModalOpen(false);
    setEditId(null);
    setEditName('');
    setEditTollGolonganId('');
    setEditBbmId('');
    setEditUangMelId('');
    setEditKmPerLiter('');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editName.trim() || !editId) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/vehicle-types/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          buildPayload({
            name: editName,
            tollGolonganId: editTollGolonganId,
            bbmId: editBbmId,
            uangMelId: editUangMelId,
            kmPerLiter: editKmPerLiter,
          })
        ),
      });
      closeEdit();
      await fetchTypes();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (type) => {
    if (!window.confirm(`Hapus jenis "${type.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/vehicle-types/${type.id}`, { method: 'DELETE' });
      await fetchTypes();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Jenis Kendaraan</h1>
          <p>
            Master jenis kendaraan, golongan tol, BBM, efisiensi (km/liter), dan uang mel. Tarif uang jalan diatur per customer di menu Customer.
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
          <GlassCard title="Tambah Jenis">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Nama Jenis</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Misal: Tronton, Fuso, Engkel"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <GolonganSelect
                value={tollGolonganId}
                onChange={setTollGolonganId}
                id="add_golongan"
                golonganList={golonganList}
              />
              <BbmSelect value={bbmId} onChange={setBbmId} id="add_bbm" bbmList={bbmList} />
              <UangMelSelect value={uangMelId} onChange={setUangMelId} id="add_uang_mel" uangMelList={uangMelList} />
              <KmPerLiterField value={kmPerLiter} onChange={setKmPerLiter} id="add_km_per_liter" />
              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={saving}>
                <Plus size={18} /> {saving ? 'Menyimpan...' : 'Simpan Jenis'}
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
                  <th>ID</th>
                  <th>Jenis Kendaraan</th>
                  <th>Golongan Tol</th>
                  <th>BBM</th>
                  <th style={{ textAlign: 'right' }}>Km/Liter</th>
                  <th style={{ textAlign: 'right' }}>Uang Mel</th>
                  <CrudActionsHeader canWrite={canWrite} />
                </tr>
              </thead>
              <tbody>
                {types.map((t) => (
                  <tr key={t.id}>
                    <td>{t.id}</td>
                    <td style={{ fontWeight: 500 }}>{t.name}</td>
                    <td style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{golonganLabel(t)}</td>
                    <td style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{bbmLabel(t)}</td>
                    <td style={{ textAlign: 'right', fontSize: '0.9rem' }}>{formatKmPerLiter(t.km_per_liter)}</td>
                    <td style={{ textAlign: 'right', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>
                      {t.uang_mel_name ? `${t.uang_mel_name} (${formatIDR(t.uang_mel_amount)})` : formatIDR(t.uang_mel_amount || 0)}
                    </td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                        onClick={() => openEdit(t)}
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.4rem 0.6rem' }}
                        onClick={() => handleDelete(t)}
                        title="Hapus"
                      >
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))}
                {types.length === 0 && (
                  <tr>
                    <td colSpan={canWrite ? 7 : 6} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                      Belum ada data jenis
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
                <h2>Edit Jenis Kendaraan</h2>
              </div>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Nama Jenis</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <GolonganSelect
                  value={editTollGolonganId}
                  onChange={setEditTollGolonganId}
                  id="edit_golongan"
                  golonganList={golonganList}
                />
                <BbmSelect
                  value={editBbmId}
                  onChange={setEditBbmId}
                  id="edit_bbm"
                  bbmList={bbmList}
                />
                <UangMelSelect
                  value={editUangMelId}
                  onChange={setEditUangMelId}
                  id="edit_uang_mel"
                  uangMelList={uangMelList}
                />
                <KmPerLiterField
                  value={editKmPerLiter}
                  onChange={setEditKmPerLiter}
                  id="edit_km_per_liter"
                />
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

export default VehicleTypes;
