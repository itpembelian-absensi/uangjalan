import React from 'react';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const TollEstimateTable = ({ items, isEstimate = true, tollSource = null }) => {
  if (!items?.length) return null;

  const sourceLabel =
    tollSource === 'bpjt'
      ? '(BPJT Gerbang)'
      : tollSource === 'google'
        ? '(Google Maps)'
        : isEstimate
          ? '(Acuan Jabodetabek)'
          : '(Google Maps)';

  return (
    <div style={{ marginBottom: '1rem' }}>
      <p className="form-label" style={{ marginBottom: '0.5rem', fontSize: '0.75rem' }}>
        Estimasi Tol per Jenis Kendaraan {sourceLabel}
      </p>
      <div
        style={{
          border: '1px solid var(--glass-border)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <table className="glass-table" style={{ fontSize: '0.85rem', margin: 0 }}>
          <thead>
            <tr>
              <th>Jenis Kendaraan</th>
              <th style={{ width: '110px' }}>Golongan</th>
              <th style={{ width: '100px' }}>Gandar</th>
              <th style={{ textAlign: 'right', width: '140px' }}>Tarif Tol</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.vehicle_type_id}>
                <td style={{ fontWeight: 500 }}>{row.vehicle_type_name}</td>
                <td>Gol {row.golongan}</td>
                <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{row.gandar}</td>
                <td style={{ textAlign: 'right', fontWeight: 700, color: '#dc2626' }}>
                  {formatIDR(row.toll_idr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
        Golongan II &amp; III tarif sama. Grand Max, Engkel, Double, Fuso = Gol II (2 gandar). Tronton = Gol III (3 gandar).
      </small>
    </div>
  );
};

export default TollEstimateTable;
