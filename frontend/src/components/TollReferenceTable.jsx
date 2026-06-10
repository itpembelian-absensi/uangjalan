import React from 'react';
import { Link } from 'react-router-dom';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const TollReferenceTable = ({ reference }) => {
  if (!reference?.sections?.length) return null;

  const golongan = reference.golongan?.length
    ? reference.golongan
    : [
        { id: 'II', code: 'II' },
        { id: 'IV', code: 'IV' },
      ];

  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <p className="form-label" style={{ marginBottom: '0.5rem', fontSize: '0.75rem' }}>
        Acuan Tarif Tol (ruas — fallback)
      </p>
      <div
        style={{
          border: '1px solid var(--glass-border)',
          borderRadius: '8px',
          overflow: 'auto',
        }}
      >
        <table className="glass-table" style={{ fontSize: '0.85rem', margin: 0 }}>
          <thead>
            <tr>
              <th>Ruas</th>
              {golongan.map((g) => (
                <th key={g.id} style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  Gol {g.code}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reference.sections.map((row) => (
              <tr key={row.id ?? row.name}>
                <td style={{ fontWeight: 500 }}>{row.name}</td>
                {golongan.map((g) => {
                  const rate = (row.rates || []).find((r) => r.golongan_id === g.id || r.golongan_code === g.code);
                  return (
                    <td key={g.id} style={{ textAlign: 'right' }}>
                      {rate ? formatIDR(rate.rate) : '-'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {reference.note && (
        <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block', marginTop: '0.5rem' }}>
          {reference.note}{' '}
          <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
            Golongan
          </Link>
          {' · '}
          <Link to="/toll-gates" style={{ color: '#4f46e5' }}>
            Gerbang tol
          </Link>
          {' · '}
          <Link to="/toll-sections" style={{ color: '#4f46e5' }}>
            Ruas tol
          </Link>
        </small>
      )}
    </div>
  );
};

export default TollReferenceTable;
