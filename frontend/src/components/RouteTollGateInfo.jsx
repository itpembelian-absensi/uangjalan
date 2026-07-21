import React, { useState } from 'react';
import SectionSearchSelect from './SectionSearchSelect';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const SOURCE_LABELS = {
  gate: 'BPJT Gerbang',
  route: 'Dari Rute Peta',
  manual: 'Pilih Manual',
  section: 'Estimasi Ruas',
  google: 'Google Maps',
};

const SOURCE_COLORS = {
  gate: { bg: '#ecfdf5', color: '#047857', border: '#a7f3d0' },
  route: { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
  manual: { bg: '#fffbeb', color: '#b45309', border: '#fde68a' },
  section: { bg: '#fffbeb', color: '#b45309', border: '#fde68a' },
  google: { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
};

const normName = (value) => (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');

const groupRate = (rates, codes) => {
  if (!rates) return null;
  for (const code of codes) {
    if (rates[code] != null) return rates[code];
  }
  return null;
};

const gateLabel = (code, name) => {
  if (name && code && name !== code) return `${name} (${code})`;
  return name || code || '—';
};

const sectionRateII = (sec) => {
  const rates = sec?.rates || [];
  const row = rates.find((r) => r.golongan_code === 'II') || rates.find((r) => r.golongan_code === 'III');
  return row?.rate != null ? Number(row.rate) : null;
};

const sectionRouteLabel = (sec, { withRate = true } = {}) => {
  const origin = sec?.origin_name?.trim();
  const dest = sec?.destination_name?.trim();
  const rate = withRate ? sectionRateII(sec) : null;
  const rateSuffix = rate != null ? ` · ${formatIDR(rate)}` : '';

  if (origin && dest) {
    if (origin.toLowerCase() === dest.toLowerCase()) {
      return `${origin} (ruas penuh)${rateSuffix}`;
    }
    return `${origin} → ${dest}${rateSuffix}`;
  }
  if (origin) return `${origin}${rateSuffix}`;
  return `${sec?.name || 'Ruas tol'}${rateSuffix}`;
};

const groupSectionsByNetwork = (sections) => {
  const groups = new Map();
  for (const sec of sections) {
    const network = sec.network?.trim() || 'Lainnya';
    if (!groups.has(network)) groups.set(network, []);
    groups.get(network).push(sec);
  }
  for (const rows of groups.values()) {
    rows.sort((a, b) => {
      const ao = (a.origin_name || '').localeCompare(b.origin_name || '', 'id');
      if (ao !== 0) return ao;
      return (a.destination_name || '').localeCompare(b.destination_name || '', 'id');
    });
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, 'id'));
};

const segmentRouteLabel = (row) => {
  const entry = row.entry_gate_name || row.entry_gate_code;
  const exit = row.exit_gate_name || row.exit_gate_code;
  if (entry && exit) {
    if (entry === exit) return entry;
    return `${entry} → ${exit}`;
  }
  if (row.section_name) return row.section_name;
  return '—';
};



const RouteTollGateInfo = ({
  segments = [],
  tollSource = 'none',
  tollNote = null,
  editable = false,
  tollSections = [],
  onSegmentReplace,
  onSegmentAdd,
  onSegmentRemove,
  onClearAll,
  onFillFromMap,
  tollLoading = false,
}) => {
  const [editingIdx, setEditingIdx] = useState(null);
  const [adding, setAdding] = useState(false);
  const [addPick, setAddPick] = useState('');

  const activeSections = (tollSections || []).filter((s) => s.is_active !== false);

  const resolveSectionId = (row) => {
    if (row.section_id) return row.section_id;
    const entry = (row.entry_gate_name || row.entry_gate_code || '').trim();
    const exit = (row.exit_gate_name || row.exit_gate_code || '').trim();
    if (entry && exit) {
      const gateHit = activeSections.find(
        (sec) =>
          (sec.origin_name || '').trim() === entry && (sec.destination_name || '').trim() === exit
      );
      if (gateHit) return gateHit.id;
    }
    const rowNorm = normName(row.section_name);
    const hit = activeSections.find((sec) => {
      const secNorm = normName(sec.name);
      const routeNorm = normName(sectionRouteLabel(sec, { withRate: false }));
      return (
        secNorm === rowNorm
        || routeNorm === rowNorm
        || rowNorm.includes(secNorm)
        || secNorm.includes(rowNorm)
      );
    });
    return hit?.id ?? null;
  };

  const handlePick = (idx, sectionId) => {
    onSegmentReplace?.(idx, sectionId);
    setEditingIdx(null);
  };

  const handleAdd = async (sectionId) => {
    if (!onSegmentAdd) return;
    await onSegmentAdd(sectionId);
    setAddPick('');
    setAdding(false);
  };

  const handleRemove = (idx) => {
    onSegmentRemove?.(idx);
  };

  const renderAddControls = () => {
    if (!editable) return null;
    return (
      <div style={{ marginTop: segments?.length ? '0.5rem' : 0, display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {adding ? (
          <>
            <div style={{ minWidth: '260px' }}>
              <SectionSearchSelect
                sections={activeSections}
                value={addPick}
                compact
                placeholder="Cari ruas yang akan ditambah…"
                onChange={(id) => {
                  setAddPick(String(id));
                  handleAdd(id);
                }}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem' }}
              onClick={() => {
                setAdding(false);
                setAddPick('');
              }}
            >
              Batal
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              onClick={() => setAdding(true)}
              disabled={!activeSections.length || tollLoading}
            >
              + Tambah asal → tujuan
            </button>
            {segments?.length > 0 && onClearAll && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                onClick={onClearAll}
                disabled={tollLoading}
                title="Kosongkan semua ruas tol"
              >
                Kosongkan ruas
              </button>
            )}
            {onFillFromMap && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{
                  fontSize: '0.8rem',
                  padding: '0.35rem 0.75rem',
                  ...(segments?.length ? {} : { borderColor: '#93c5fd', background: '#eff6ff', color: '#1d4ed8' }),
                }}
                onClick={onFillFromMap}
                disabled={tollLoading}
                title="Hitung ulang ruas/tarif otomatis dari rute peta (BPJT atau Google)"
              >
                {segments?.length ? 'Isi ulang dari rute peta' : 'Refresh otomatis (Google / BPJT)'}
              </button>
            )}
          </>
        )}
        {!activeSections.length && (
          <small style={{ color: '#b45309', fontSize: '0.75rem' }}>
            Master ruas tol kosong — jalankan Impor BPJT di menu Master Ruas Tol.
          </small>
        )}
      </div>
    );
  };

  if (!segments?.length) {
    return (
      <div style={{ marginBottom: '1rem', opacity: tollLoading ? 0.65 : 1 }}>
        <div
          style={{
            marginBottom: editable ? '0.5rem' : 0,
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            border: '1px solid var(--glass-border)',
            background: 'rgba(255,255,255,0.5)',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
          }}
        >
          {tollNote || 'Ruas tol kosong — rute tidak melewati tol, atau dikosongkan manual.'}
          {editable && (
            <span style={{ display: 'block', marginTop: '0.35rem' }}>
              Tambah ruas manual, atau klik <strong>Refresh otomatis (Google / BPJT)</strong> untuk isi ulang dari rute.
            </span>
          )}
        </div>
        {renderAddControls()}
      </div>
    );
  }

  const hasManual = segments.some((row) => row.source === 'manual') || tollSource === 'manual';
  const sourceKey = hasManual
    ? 'manual'
    : tollSource === 'bpjt'
      ? 'gate'
      : tollSource === 'route'
        ? 'route'
        : tollSource;
  const badgeStyle = SOURCE_COLORS[sourceKey] || SOURCE_COLORS.section;
  const oneWayTotal = segments.reduce((sum, row) => sum + (Number(row.one_way_idr) || 0), 0);
  const roundTripTotal = segments.reduce((sum, row) => sum + (Number(row.round_trip_idr) || 0), 0);

  return (
    <div style={{ marginBottom: '1rem', opacity: tollLoading ? 0.65 : 1 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          marginBottom: '0.5rem',
          flexWrap: 'wrap',
        }}
      >
        <p className="form-label" style={{ margin: 0, fontSize: '0.75rem' }}>
          Gerbang Tol Masuk / Keluar &amp; Tarif
        </p>
        <span
          style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            padding: '0.15rem 0.5rem',
            borderRadius: '999px',
            background: badgeStyle.bg,
            color: badgeStyle.color,
            border: `1px solid ${badgeStyle.border}`,
          }}
        >
          {SOURCE_LABELS[sourceKey] || SOURCE_LABELS[segments[0]?.source] || 'Estimasi'}
        </span>
        {editable && (
          <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
            Klik asal → tujuan untuk ubah dari master ruas
          </small>
        )}
      </div>

      <div
        style={{
          border: '1px solid var(--glass-border)',
          borderRadius: '8px',
          overflow: 'auto',
        }}
      >
        <table className="glass-table" style={{ fontSize: '0.85rem', margin: 0, minWidth: '640px' }}>
          <thead>
            <tr>
              <th>Asal → Tujuan</th>
              <th>Gerbang Masuk</th>
              <th>Gerbang Keluar</th>
              <th style={{ textAlign: 'right' }}>Gol I</th>
              <th style={{ textAlign: 'right' }}>Gol II&amp;III</th>
              <th style={{ textAlign: 'right' }}>Gol IV&amp;V</th>
              <th style={{ textAlign: 'right' }}>Satu Arah (Gol II)</th>
              <th style={{ textAlign: 'right' }}>Pulang-Pergi</th>
              {editable && <th style={{ width: '40px' }} />}
            </tr>
          </thead>
          <tbody>
            {segments.map((row, idx) => {
              const rates = row.rates_by_golongan || {};
              const gol1 = groupRate(rates, ['I']);
              const gol23 = groupRate(rates, ['II', 'III']);
              const gol45 = groupRate(rates, ['IV', 'V']);
              const hasGateNames =
                row.entry_gate_name || row.exit_gate_name || row.entry_gate_code || row.exit_gate_code;
              const isEditing = editable && editingIdx === idx;

              return (
                <tr key={`${row.section_name}-${idx}`}>
                  <td style={{ fontWeight: 500, minWidth: '200px' }}>
                    {isEditing ? (
                      <div style={{ minWidth: '240px' }}>
                        <SectionSearchSelect
                          sections={activeSections}
                          value={resolveSectionId(row)}
                          compact
                          onChange={(id) => handlePick(idx, id)}
                        />
                      </div>
                    ) : editable ? (
                      <button
                        type="button"
                        onClick={() => setEditingIdx(idx)}
                        title="Klik untuk ganti asal → tujuan"
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          margin: 0,
                          color: 'var(--accent-color)',
                          fontWeight: 600,
                          cursor: 'pointer',
                          textAlign: 'left',
                          textDecoration: 'underline',
                          textDecorationStyle: 'dotted',
                          fontSize: 'inherit',
                        }}
                      >
                        {segmentRouteLabel(row)}
                      </button>
                    ) : (
                      segmentRouteLabel(row)
                    )}
                    {!isEditing && row.section_name && row.section_name !== segmentRouteLabel(row) && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem', fontWeight: 'normal' }}>
                        {row.section_name}
                      </div>
                    )}
                  </td>
                  <td>
                    {hasGateNames
                      ? gateLabel(row.entry_gate_code, row.entry_gate_name)
                      : row.source === 'section' || row.source === 'manual'
                        ? row.entry_gate_name || '—'
                        : '—'}
                  </td>
                  <td>
                    {hasGateNames
                      ? gateLabel(row.exit_gate_code, row.exit_gate_name)
                      : row.source === 'section' || row.source === 'manual'
                        ? row.exit_gate_name || '—'
                        : '—'}
                  </td>
                  <td style={{ textAlign: 'right' }}>{gol1 != null ? formatIDR(gol1) : '—'}</td>
                  <td style={{ textAlign: 'right' }}>{gol23 != null ? formatIDR(gol23) : '—'}</td>
                  <td style={{ textAlign: 'right' }}>{gol45 != null ? formatIDR(gol45) : '—'}</td>
                  <td style={{ textAlign: 'right' }}>{formatIDR(row.one_way_idr)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600, color: '#dc2626' }}>
                    {formatIDR(row.round_trip_idr)}
                  </td>
                  {editable && (
                    <td style={{ textAlign: 'center' }}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '0.15rem 0.4rem', fontSize: '0.75rem', lineHeight: 1 }}
                        title="Hapus ruas"
                        onClick={() => handleRemove(idx)}
                      >
                        ×
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
          {segments.length >= 1 && (
            <tfoot>
              <tr style={{ background: 'rgba(79, 70, 229, 0.06)' }}>
                <td colSpan={3} style={{ fontWeight: 700 }}>
                  Total ({segments.length} ruas)
                </td>
                <td />
                <td />
                <td />
                <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatIDR(oneWayTotal)}</td>
                <td style={{ textAlign: 'right', fontWeight: 700, color: '#dc2626' }}>
                  {formatIDR(roundTripTotal)}
                </td>
                {editable && <td />}
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {renderAddControls()}

      {segments.some((row) => row.source === 'section' && row.weight_pct != null) && (
        <small style={{ display: 'block', marginTop: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
          Kolom satu arah / pulang-pergi untuk estimasi ruas = tarif proporsional jarak rute (bukan tarif penuh gerbang).
        </small>
      )}

      {tollNote && (
        <small style={{ display: 'block', marginTop: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
          {tollNote}
        </small>
      )}
    </div>
  );
};

export default RouteTollGateInfo;
