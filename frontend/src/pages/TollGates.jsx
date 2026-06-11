import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Trash2, Edit2, RefreshCw } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';
import {
  useCrudWrite,
  crudTableGridSpan,
  CrudActionsHeader,
  CrudActionsCell,
} from '../components/CrudWriteAccess';
import TablePager from '../components/TablePager';

const GATES_PAGE_SIZE = 20;
const FARES_PAGE_SIZE = 25;

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0,
  );

const emptyGateForm = () => ({
  section_id: '',
  code: '',
  name: '',
  latitude: '',
  longitude: '',
  sort_order: '',
  is_active: true,
});

const emptyFareForm = () => ({
  entry_gate_id: '',
  exit_gate_id: '',
  golongan_id: '',
  rate: '',
});

const TollGates = () => {
  const canWrite = useCrudWrite();
  const [sections, setSections] = useState([]);
  const [golonganList, setGolonganList] = useState([]);
  const [gates, setGates] = useState([]);
  const [fares, setFares] = useState([]);
  const [filterSection, setFilterSection] = useState('');
  const [gateForm, setGateForm] = useState(emptyGateForm());
  const [fareForm, setFareForm] = useState(emptyFareForm());
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncInfo, setSyncInfo] = useState(null);
  const [gatesPage, setGatesPage] = useState(1);
  const [faresPage, setFaresPage] = useState(1);
  const [editGateId, setEditGateId] = useState(null);
  const [editGateForm, setEditGateForm] = useState(emptyGateForm());
  const [isGateModalOpen, setIsGateModalOpen] = useState(false);

  const fetchAll = async () => {
    const [sec, gol, gts, frs] = await Promise.all([
      apiFetch('/api/toll-sections'),
      apiFetch('/api/toll-golongan'),
      apiFetch(`/api/toll-gates${filterSection ? `?section_id=${filterSection}` : ''}`),
      apiFetch(`/api/toll-gate-fares${filterSection ? `?section_id=${filterSection}` : ''}`),
    ]);
    setSections(sec);
    setGolonganList(gol);
    setGates(gts);
    setFares(frs);
    setError('');
  };

  useEffect(() => {
    fetchAll().catch((err) => setError(err.message));
  }, [filterSection]);

  useEffect(() => {
    setGatesPage(1);
    setFaresPage(1);
  }, [filterSection, gates.length, fares.length]);

  const gatesTotalPages = Math.max(1, Math.ceil(gates.length / GATES_PAGE_SIZE));
  const faresTotalPages = Math.max(1, Math.ceil(fares.length / FARES_PAGE_SIZE));
  const safeGatesPage = Math.min(gatesPage, gatesTotalPages);
  const safeFaresPage = Math.min(faresPage, faresTotalPages);

  const paginatedGates = useMemo(() => {
    const start = (safeGatesPage - 1) * GATES_PAGE_SIZE;
    return gates.slice(start, start + GATES_PAGE_SIZE);
  }, [gates, safeGatesPage]);

  const paginatedFares = useMemo(() => {
    const start = (safeFaresPage - 1) * FARES_PAGE_SIZE;
    return fares.slice(start, start + FARES_PAGE_SIZE);
  }, [fares, safeFaresPage]);

  const gatesInSection = useMemo(() => {
    if (!fareForm.entry_gate_id) return gates;
    const entry = gates.find((g) => String(g.id) === String(fareForm.entry_gate_id));
    if (!entry) return gates;
    return gates.filter((g) => g.section_id === entry.section_id);
  }, [gates, fareForm.entry_gate_id]);

  const handleGateSubmit = async (e) => {
    e.preventDefault();
    if (!gateForm.section_id || !gateForm.code.trim() || !gateForm.name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/toll-gates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section_id: parseInt(gateForm.section_id, 10),
          code: gateForm.code.trim(),
          name: gateForm.name.trim(),
          latitude: gateForm.latitude ? parseFloat(gateForm.latitude) : null,
          longitude: gateForm.longitude ? parseFloat(gateForm.longitude) : null,
          sort_order: parseInt(gateForm.sort_order, 10) || 0,
          is_active: gateForm.is_active,
        }),
      });
      setGateForm(emptyGateForm());
      await fetchAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleFareSubmit = async (e) => {
    e.preventDefault();
    if (!fareForm.entry_gate_id || !fareForm.exit_gate_id || !fareForm.golongan_id || fareForm.rate === '') return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/toll-gate-fares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entry_gate_id: parseInt(fareForm.entry_gate_id, 10),
          exit_gate_id: parseInt(fareForm.exit_gate_id, 10),
          golongan_id: parseInt(fareForm.golongan_id, 10),
          rate: parseFloat(fareForm.rate) || 0,
        }),
      });
      setFareForm(emptyFareForm());
      await fetchAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openEditGate = (row) => {
    if (!canWrite) return;
    setEditGateId(row.id);
    setEditGateForm({
      section_id: String(row.section_id),
      code: row.code,
      name: row.name,
      latitude: row.latitude != null ? String(row.latitude) : '',
      longitude: row.longitude != null ? String(row.longitude) : '',
      sort_order: String(row.sort_order ?? ''),
      is_active: row.is_active,
    });
    setIsGateModalOpen(true);
  };

  const handleEditGateSubmit = async (e) => {
    e.preventDefault();
    if (!editGateId) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/api/toll-gates/${editGateId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section_id: parseInt(editGateForm.section_id, 10),
          code: editGateForm.code.trim(),
          name: editGateForm.name.trim(),
          latitude: editGateForm.latitude ? parseFloat(editGateForm.latitude) : null,
          longitude: editGateForm.longitude ? parseFloat(editGateForm.longitude) : null,
          sort_order: parseInt(editGateForm.sort_order, 10) || 0,
          is_active: editGateForm.is_active,
        }),
      });
      setIsGateModalOpen(false);
      setEditGateId(null);
      await fetchAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSyncBpjtGates = async () => {
    if (
      !window.confirm(
        'Impor matriks gerbang Jabodetabek dari BPJT? Ruas tol harus sudah diimpor dulu. Tarif gerbang ruas yang sama akan diganti.'
      )
    )
      return;
    setSyncing(true);
    setError('');
    setSyncInfo(null);
    try {
      const result = await apiFetch('/api/toll-gates/sync-bpjt-jabodetabek', { method: 'POST' });
      setSyncInfo(result);
      await fetchAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteGate = async (row) => {
    if (!window.confirm(`Hapus gerbang ${row.code}? Tarif terkait ikut terhapus.`)) return;
    try {
      await apiFetch(`/api/toll-gates/${row.id}`, { method: 'DELETE' });
      await fetchAll();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDeleteFare = async (row) => {
    if (!window.confirm(`Hapus tarif ${row.entry_gate_code} → ${row.exit_gate_code}?`)) return;
    try {
      await apiFetch(`/api/toll-gate-fares/${row.id}`, { method: 'DELETE' });
      await fetchAll();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gerbang Tol (BPJT / Jasa Marga)</h1>
          <p className="page-subtitle">
            Isi daftar gerbang dan tarif antar gerbang sesuai publikasi BPJT/Jasa Marga. Perhitungan uang jalan
            memakai pasangan gerbang terdekat gudang → customer, total pulang-pergi × 2.
          </p>
        </div>
        {canWrite && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleSyncBpjtGates}
            disabled={syncing}
            style={{ whiteSpace: 'nowrap' }}
          >
            <RefreshCw size={18} />
            {syncing ? 'Mengimpor BPJT...' : 'Impor Matriks BPJT'}
          </button>
        )}
      </div>

      {syncInfo && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#ecfdf5',
            color: '#065f46',
            border: '1px solid #a7f3d0',
            fontSize: '0.9rem',
          }}
        >
          Matriks gerbang: {syncInfo.sections_imported} ruas, {syncInfo.fares_created} tarif pasangan (
          {syncInfo.gates_created} gerbang baru).{' '}
          {syncInfo.sections_skipped?.length > 0 && (
            <>Ruas dilewati: {syncInfo.sections_skipped.join(', ')}. </>
          )}
          <a href={syncInfo.source_url} target="_blank" rel="noreferrer" style={{ color: '#047857' }}>
            Sumber BPJT
          </a>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: 8, background: '#fef2f2', color: '#991b1b' }}>
          {error}
        </div>
      )}

      <div className="form-group" style={{ maxWidth: 320, marginBottom: '1rem' }}>
        <label className="form-label">Filter ruas tol</label>
        <select className="form-input" value={filterSection} onChange={(e) => setFilterSection(e.target.value)}>
          <option value="">Semua ruas</option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {canWrite && (
        <GlassCard title="Tambah Gerbang">
          <form onSubmit={handleGateSubmit}>
            <div className="grid-cols-2" style={{ gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Ruas Tol</label>
                <select
                  className="form-input"
                  required
                  value={gateForm.section_id}
                  onChange={(e) => setGateForm({ ...gateForm, section_id: e.target.value })}
                >
                  <option value="">-- Pilih ruas --</option>
                  {sections.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Kode Gerbang</label>
                <input
                  className="form-input"
                  required
                  placeholder="Mis. CIKUPA"
                  value={gateForm.code}
                  onChange={(e) => setGateForm({ ...gateForm, code: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Nama Gerbang</label>
                <input
                  className="form-input"
                  required
                  value={gateForm.name}
                  onChange={(e) => setGateForm({ ...gateForm, name: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Urutan</label>
                <input
                  type="number"
                  className="form-input"
                  value={gateForm.sort_order}
                  onChange={(e) => setGateForm({ ...gateForm, sort_order: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Latitude</label>
                <input
                  className="form-input"
                  placeholder="Opsional — untuk deteksi otomatis"
                  value={gateForm.latitude}
                  onChange={(e) => setGateForm({ ...gateForm, latitude: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Longitude</label>
                <input
                  className="form-input"
                  placeholder="Opsional — untuk deteksi otomatis"
                  value={gateForm.longitude}
                  onChange={(e) => setGateForm({ ...gateForm, longitude: e.target.value })}
                />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '1rem' }} disabled={saving}>
              <Plus size={16} /> Simpan Gerbang
            </button>
          </form>
        </GlassCard>
      )}

      <GlassCard title="Daftar Gerbang" style={{ marginTop: '1rem' }}>
        <TablePager
          page={safeGatesPage}
          pageSize={GATES_PAGE_SIZE}
          totalItems={gates.length}
          onPageChange={setGatesPage}
          label="Gerbang"
        />
        <div className="table-container" style={{ padding: 0, marginTop: '0.5rem' }}>
          <table className="glass-table">
            <thead>
              <tr>
                <th>Ruas</th>
                <th>Kode</th>
                <th>Nama</th>
                <th>Koordinat</th>
                <th>Urut</th>
                <th>Status</th>
                <CrudActionsHeader canWrite={canWrite} />
              </tr>
            </thead>
            <tbody>
              {gates.length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 7 : 6} style={{ textAlign: 'center', padding: '1.5rem', opacity: 0.6 }}>
                    Belum ada gerbang — tambahkan dari daftar BPJT/Jasa Marga
                  </td>
                </tr>
              ) : (
                paginatedGates.map((g) => (
                  <tr key={g.id}>
                    <td>{g.section_name || '-'}</td>
                    <td style={{ fontWeight: 600 }}>{g.code}</td>
                    <td>{g.name}</td>
                    <td style={{ fontSize: '0.85rem' }}>
                      {g.latitude != null && g.longitude != null ? `${g.latitude}, ${g.longitude}` : '-'}
                    </td>
                    <td>{g.sort_order}</td>
                    <td>{g.is_active ? 'Aktif' : 'Nonaktif'}</td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button type="button" className="btn btn-secondary" style={{ padding: '0.35rem' }} onClick={() => openEditGate(g)}>
                        <Edit2 size={16} />
                      </button>
                      <button type="button" className="btn btn-danger" style={{ padding: '0.35rem' }} onClick={() => handleDeleteGate(g)}>
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {gates.length > GATES_PAGE_SIZE && (
          <div style={{ marginTop: '0.5rem' }}>
            <TablePager
              page={safeGatesPage}
              pageSize={GATES_PAGE_SIZE}
              totalItems={gates.length}
              onPageChange={setGatesPage}
              label="Gerbang"
            />
          </div>
        )}
      </GlassCard>

      {canWrite && (
        <GlassCard title="Tambah Tarif Antara Gerbang" style={{ marginTop: '1rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 0 }}>
            Salin tarif resmi dari{' '}
            <a href="https://infotol.jasamarga.co.id/" target="_blank" rel="noreferrer">
              Jasa Marga Info Tol
            </a>{' '}
            / BPJT untuk pasangan gerbang masuk → keluar pada ruas yang sama.
          </p>
          <form onSubmit={handleFareSubmit}>
            <div className="grid-cols-2" style={{ gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Gerbang Masuk</label>
                <select
                  className="form-input"
                  required
                  value={fareForm.entry_gate_id}
                  onChange={(e) => setFareForm({ ...fareForm, entry_gate_id: e.target.value, exit_gate_id: '' })}
                >
                  <option value="">-- Pilih --</option>
                  {gates.filter((g) => g.is_active).map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.code} — {g.name} ({g.section_name})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Gerbang Keluar</label>
                <select
                  className="form-input"
                  required
                  value={fareForm.exit_gate_id}
                  onChange={(e) => setFareForm({ ...fareForm, exit_gate_id: e.target.value })}
                >
                  <option value="">-- Pilih --</option>
                  {gatesInSection.filter((g) => g.is_active && String(g.id) !== String(fareForm.entry_gate_id)).map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.code} — {g.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Golongan</label>
                <select
                  className="form-input"
                  required
                  value={fareForm.golongan_id}
                  onChange={(e) => setFareForm({ ...fareForm, golongan_id: e.target.value })}
                >
                  <option value="">-- Pilih --</option>
                  {golonganList.filter((g) => g.is_active).map((g) => (
                    <option key={g.id} value={g.id}>
                      Gol {g.code} — {g.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Tarif (Rp, satu arah)</label>
                <input
                  type="number"
                  min="0"
                  step="500"
                  className="form-input"
                  required
                  value={fareForm.rate}
                  onChange={(e) => setFareForm({ ...fareForm, rate: e.target.value })}
                />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '1rem' }} disabled={saving}>
              <Plus size={16} /> Simpan Tarif
            </button>
          </form>
        </GlassCard>
      )}

      <GlassCard title="Daftar Tarif Gerbang" style={{ marginTop: '1rem' }}>
        <TablePager
          page={safeFaresPage}
          pageSize={FARES_PAGE_SIZE}
          totalItems={fares.length}
          onPageChange={setFaresPage}
          label="Tarif"
        />
        <div className="table-container" style={{ padding: 0, marginTop: '0.5rem' }}>
          <table className="glass-table">
            <thead>
              <tr>
                <th>Ruas</th>
                <th>Masuk</th>
                <th>Keluar</th>
                <th>Gol</th>
                <th style={{ textAlign: 'right' }}>Tarif (1 arah)</th>
                <th style={{ textAlign: 'right' }}>Pulang-pergi (×2)</th>
                <CrudActionsHeader canWrite={canWrite} />
              </tr>
            </thead>
            <tbody>
              {fares.length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 7 : 6} style={{ textAlign: 'center', padding: '1.5rem', opacity: 0.6 }}>
                    Belum ada tarif gerbang
                  </td>
                </tr>
              ) : (
                paginatedFares.map((f) => (
                  <tr key={f.id}>
                    <td>{f.section_name}</td>
                    <td>
                      <strong>{f.entry_gate_code}</strong> — {f.entry_gate_name}
                    </td>
                    <td>
                      <strong>{f.exit_gate_code}</strong> — {f.exit_gate_name}
                    </td>
                    <td>Gol {f.golongan_code}</td>
                    <td style={{ textAlign: 'right' }}>{formatIDR(f.rate)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--accent-color)' }}>
                      {formatIDR(f.rate * 2)}
                    </td>
                    <CrudActionsCell canWrite={canWrite}>
                      <button type="button" className="btn btn-danger" style={{ padding: '0.35rem' }} onClick={() => handleDeleteFare(f)}>
                        <Trash2 size={16} />
                      </button>
                    </CrudActionsCell>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {fares.length > FARES_PAGE_SIZE && (
          <div style={{ marginTop: '0.5rem' }}>
            <TablePager
              page={safeFaresPage}
              pageSize={FARES_PAGE_SIZE}
              totalItems={fares.length}
              onPageChange={setFaresPage}
              label="Tarif"
            />
          </div>
        )}
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.75rem 0 0' }}>
          Ruas tol diatur di <Link to="/toll-sections">Master Ruas Tol</Link>, golongan di{' '}
          <Link to="/toll-golongan">Master Golongan Tol</Link>.
        </p>
      </GlassCard>

      {isGateModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Gerbang</h2>
            <form onSubmit={handleEditGateSubmit}>
              <div className="grid-cols-2" style={{ gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Ruas</label>
                  <select
                    className="form-input"
                    value={editGateForm.section_id}
                    onChange={(e) => setEditGateForm({ ...editGateForm, section_id: e.target.value })}
                  >
                    {sections.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Kode</label>
                  <input className="form-input" value={editGateForm.code} onChange={(e) => setEditGateForm({ ...editGateForm, code: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Nama</label>
                  <input className="form-input" value={editGateForm.name} onChange={(e) => setEditGateForm({ ...editGateForm, name: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Latitude</label>
                  <input className="form-input" value={editGateForm.latitude} onChange={(e) => setEditGateForm({ ...editGateForm, latitude: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Longitude</label>
                  <input className="form-input" value={editGateForm.longitude} onChange={(e) => setEditGateForm({ ...editGateForm, longitude: e.target.value })} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  Simpan
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setIsGateModalOpen(false)}>
                  Batal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default TollGates;
