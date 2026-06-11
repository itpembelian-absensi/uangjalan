import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { ArrowLeft, Save } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';

const RATE_GROUPS = [
  { key: 'I', codes: ['I'], label: 'Gol I' },
  { key: 'II_III', codes: ['II', 'III'], label: 'Gol II & III' },
  { key: 'IV_V', codes: ['IV', 'V'], label: 'Gol IV & V' },
];

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
    rate: existingById[g.id]?.rate != null ? String(existingById[g.id].rate) : '',
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
  network: 'Jabodetabek',
  name: '',
  origin_name: '',
  destination_name: '',
  length_km: '',
  sort_order: '',
  is_active: true,
  rates: buildRatesForm(golonganList),
});

const rateByCode = (rates, code) => rates.find((r) => r.golongan_code === code);

const groupRateValue = (rates, codes) => {
  for (const code of codes) {
    const row = rateByCode(rates, code);
    if (row?.rate !== '' && row?.rate != null) return row.rate;
  }
  return '';
};

const updateGroupRate = (values, onChange, codes, rateValue) => {
  const ids = codes
    .map((code) => rateByCode(values.rates, code)?.golongan_id)
    .filter(Boolean);
  onChange({
    ...values,
    rates: values.rates.map((r) =>
      ids.includes(r.golongan_id) ? { ...r, rate: rateValue } : r
    ),
  });
};

const renderRateGroups = (values, onChange, golonganList) => {
  const availableGroups = RATE_GROUPS.filter((group) =>
    group.codes.some((code) => rateByCode(values.rates, code))
  );

  if (availableGroups.length === 0) {
    return (
      <p style={{ fontSize: '0.9rem', color: '#92400e' }}>
        Belum ada golongan aktif. Tambahkan dulu di{' '}
        <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
          Master Golongan Tol
        </Link>
        .
      </p>
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '0.5rem',
      }}
    >
      {availableGroups.map((group) => (
        <div key={group.key}>
          <label
            className="form-label"
            style={{ fontSize: '0.7rem', marginBottom: '0.25rem', display: 'block' }}
          >
            {group.label}
          </label>
          <input
            type="number"
            className="form-input"
            min="0"
            step="500"
            placeholder="0"
            value={groupRateValue(values.rates, group.codes)}
            onChange={(e) => updateGroupRate(values, onChange, group.codes, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
};

const TollSectionForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);

  const [form, setForm] = useState(emptySectionForm([]));
  const [golonganList, setGolonganList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const gol = await apiFetch('/api/toll-golongan');
        setGolonganList(gol);
        
        if (isEdit) {
          const row = await apiFetch(`/api/toll-sections/${id}`);
          setForm({
            network: row.network || 'Jabodetabek',
            name: row.name,
            origin_name: row.origin_name || '',
            destination_name: row.destination_name || '',
            length_km: String(row.length_km),
            sort_order: String(row.sort_order),
            is_active: row.is_active,
            rates: buildRatesForm(gol, row.rates || []),
          });
        } else {
          setForm(emptySectionForm(gol));
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit]);

  const payloadFromForm = (values) => ({
    network: values.network?.trim() || null,
    name: values.name.trim(),
    origin_name: values.origin_name?.trim() || null,
    destination_name: values.destination_name?.trim() || null,
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
      if (isEdit) {
        await apiFetch(`/api/toll-sections/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payloadFromForm(form)),
        });
      } else {
        await apiFetch('/api/toll-sections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payloadFromForm(form)),
        });
      }
      navigate('/toll-sections');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Memuat data...</div>;
  }

  const activeGolongan = golonganList.filter((g) => g.is_active);

  return (
    <div>
      <div className="page-header" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/toll-sections')}
            style={{ padding: '0.5rem' }}
            title="Kembali"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1>{isEdit ? 'Edit Ruas Tol' : 'Tambah Ruas Tol'}</h1>
            <p>Formulir data ruas & tarif end-to-end</p>
          </div>
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

      <div style={{ maxWidth: '800px' }}>
        <GlassCard>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Tol Trans / Jaringan</label>
              <input
                type="text"
                className="form-input"
                placeholder="Misal: Jabodetabek"
                value={form.network}
                onChange={(e) => setForm({ ...form, network: e.target.value })}
              />
              <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                Kelompok jaringan tol (sesuai acuan BPJT).
              </small>
            </div>

            <div className="form-group">
              <label className="form-label">Nama Ruas Tol</label>
              <input
                type="text"
                className="form-input"
                placeholder="Misal: Jakarta-Bogor-Ciawi, JORR S"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>

            <div className="grid-cols-2" style={{ gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Asal (Acuan Tarif)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Misal: Jakarta, Cawang"
                  value={form.origin_name}
                  onChange={(e) => setForm({ ...form, origin_name: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Tujuan (Acuan Tarif)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Misal: Ciawi, Pluit"
                  value={form.destination_name}
                  onChange={(e) => setForm({ ...form, destination_name: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-cols-2" style={{ gap: '1rem', marginTop: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Panjang Ruas (km)</label>
                <input
                  type="number"
                  className="form-input"
                  min="0.1"
                  step="0.01"
                  value={form.length_km}
                  onChange={(e) => setForm({ ...form, length_km: e.target.value })}
                  required
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Urutan</label>
                <input
                  type="number"
                  className="form-input"
                  min="0"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                />
              </div>
            </div>

            <div
              className="form-group"
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', marginTop: '0.75rem' }}
            >
              <input
                type="checkbox"
                id="is_active"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              <label htmlFor="is_active" style={{ cursor: 'pointer' }}>
                Aktif
              </label>
            </div>

            <div className="form-group" style={{ marginBottom: '2rem' }}>
              <label className="form-label" style={{ marginBottom: '0.25rem' }}>
                Besaran Tarif (Rp) — Acuan Ruas Penuh
              </label>
              <small style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Tarif end-to-end untuk pasangan Asal → Tujuan di atas. Untuk matriks gerbang detail per
                pasangan, kelola di{' '}
                <Link to="/toll-gates" style={{ color: '#4f46e5' }}>
                  Gerbang Tol
                </Link>
                .
              </small>
              {renderRateGroups(form, setForm, golonganList)}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => navigate('/toll-sections')}
              >
                Batal
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving || activeGolongan.length === 0}
              >
                <Save size={18} />
                {saving ? 'Menyimpan...' : 'Simpan'}
              </button>
            </div>
          </form>
        </GlassCard>
      </div>
    </div>
  );
};

export default TollSectionForm;
