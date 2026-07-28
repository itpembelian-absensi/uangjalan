import React, { useEffect, useMemo, useState } from 'react';
import GlassCard from '../components/GlassCard';
import TablePager from '../components/TablePager';
import { Download, FileText, Printer, Users } from 'lucide-react';
import { apiFetch } from '../api';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';

const formatIDR = (val) =>
  new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0,
  }).format(Number(val) || 0);

const PAGE_SIZE = 8; // jumlah customer per halaman

const CustomerTariffReportTab = () => {
  const [rows, setRows] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterCustomer, setFilterCustomer] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [filledOnly, setFilledOnly] = useState(true);
  const [page, setPage] = useState(1);

  const fetchReport = async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (filterCustomer) params.set('customer_id', filterCustomer);
      params.set('active_only', activeOnly ? 'true' : 'false');
      params.set('filled_only', filledOnly ? 'true' : 'false');
      const [data, customerList] = await Promise.all([
        apiFetch(`/api/reports/customer-tariffs?${params.toString()}`),
        customers.length ? Promise.resolve(customers) : apiFetch('/api/customers'),
      ]);
      setRows(Array.isArray(data) ? data : []);
      if (!customers.length) setCustomers(Array.isArray(customerList) ? customerList : []);
      setPage(1);
    } catch (err) {
      setError(err.message || 'Gagal memuat laporan tarif.');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterCustomer, activeOnly, filledOnly]);

  const customerCount = useMemo(
    () => new Set(rows.map((r) => r.customer_id)).size,
    [rows]
  );

  const grouped = useMemo(() => {
    const map = new Map();
    for (const r of rows) {
      if (!map.has(r.customer_id)) {
        map.set(r.customer_id, {
          customer_id: r.customer_id,
          customer_code: r.customer_code,
          customer_name: r.customer_name,
          is_active: r.is_active,
          tariffs: [],
        });
      }
      map.get(r.customer_id).tariffs.push(r);
    }
    return Array.from(map.values());
  }, [rows]);

  const totalPages = Math.max(1, Math.ceil(grouped.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginatedGroups = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return grouped.slice(start, start + PAGE_SIZE);
  }, [grouped, safePage]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const tableBody = rows.map((r) => [
    r.customer_code || '-',
    r.customer_name,
    r.vehicle_type_name,
    Number(r.bbm) || 0,
    Number(r.tol) || 0,
    Number(r.uang_mel) || 0,
    Number(r.parkir) || 0,
    Number(r.lain_lain) || 0,
    Number(r.uang_jalan) || 0,
  ]);

  const handleExportExcel = () => {
    const sheetRows = [
      [
        'Kode',
        'Customer',
        'Jenis Kendaraan',
        'BBM',
        'Tol',
        'Uang Mel',
        'Parkir',
        'Lain-lain',
        'Uang Jalan',
      ],
      ...tableBody,
    ];
    const ws = XLSX.utils.aoa_to_sheet(sheetRows);
    ws['!cols'] = [
      { wch: 12 },
      { wch: 36 },
      { wch: 20 },
      { wch: 14 },
      { wch: 14 },
      { wch: 14 },
      { wch: 14 },
      { wch: 14 },
      { wch: 14 },
    ];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Tarif Customer');
    XLSX.writeFile(wb, `tarif-uang-jalan-per-customer.xlsx`);
  };

  const handleExportPdf = () => {
    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    doc.setFontSize(14);
    doc.text('Laporan Tarif Uang Jalan per Customer', 14, 14);
    doc.setFontSize(9);
    doc.text(
      `${customerCount} customer · ${rows.length} baris tarif · ${new Date().toLocaleString('id-ID')}`,
      14,
      20
    );
    autoTable(doc, {
      startY: 24,
      head: [
        [
          'Kode',
          'Customer',
          'Jenis',
          'BBM',
          'Tol',
          'Uang Mel',
          'Parkir',
          'Lain-lain',
          'Uang Jalan',
        ],
      ],
      body: tableBody.map((row) => [
        row[0],
        row[1],
        row[2],
        formatIDR(row[3]),
        formatIDR(row[4]),
        formatIDR(row[5]),
        formatIDR(row[6]),
        formatIDR(row[7]),
        formatIDR(row[8]),
      ]),
      styles: { fontSize: 7, cellPadding: 1.5 },
      headStyles: { fillColor: [37, 99, 235] },
      columnStyles: {
        3: { halign: 'right' },
        4: { halign: 'right' },
        5: { halign: 'right' },
        6: { halign: 'right' },
        7: { halign: 'right' },
        8: { halign: 'right' },
      },
    });
    doc.save('tarif-uang-jalan-per-customer.pdf');
  };

  const handlePrint = () => {
    const htmlGroups = grouped
      .map((g) => {
        const title = g.customer_code
          ? `${g.customer_code} — ${g.customer_name}`
          : g.customer_name;
        const tariffRows = g.tariffs
          .map(
            (r) => `<tr>
              <td>${r.vehicle_type_name}</td>
              <td class="num">${formatIDR(r.bbm)}</td>
              <td class="num">${formatIDR(r.tol)}</td>
              <td class="num">${formatIDR(r.uang_mel)}</td>
              <td class="num">${formatIDR(r.parkir)}</td>
              <td class="num">${formatIDR(r.lain_lain)}</td>
              <td class="num"><strong>${formatIDR(r.uang_jalan)}</strong></td>
            </tr>`
          )
          .join('');
        return `<tbody class="group">
          <tr class="group-head"><td colspan="7">${title}</td></tr>
          ${tariffRows}
        </tbody>`;
      })
      .join('');
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><title>Tarif Uang Jalan per Customer</title>
      <style>
        body { font-family: system-ui, sans-serif; padding: 16px; color: #0f172a; }
        h1 { font-size: 18px; margin: 0 0 4px; }
        .meta { color: #64748b; font-size: 12px; margin-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; }
        th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }
        th { background: #f1f5f9; }
        td.num { text-align: right; white-space: nowrap; }
        tr.group-head td { background: #e2e8f0; font-weight: 700; border-top: 2px solid #64748b; }
        tbody.group { page-break-inside: avoid; }
      </style></head><body>
      <h1>Laporan Tarif Uang Jalan per Customer</h1>
      <div class="meta">${customerCount} customer · ${rows.length} baris tarif</div>
      <table>
        <thead><tr>
          <th>Jenis</th>
          <th>BBM</th><th>Tol</th><th>Uang Mel</th><th>Parkir</th><th>Lain-lain</th><th>Uang Jalan</th>
        </tr></thead>
        ${htmlGroups}
      </table>
      </body></html>`);
    w.document.close();
    w.focus();
    w.print();
  };

  return (
    <>
      <GlassCard style={{ marginBottom: '1.5rem' }}>
        <div
          style={{
            display: 'flex',
            gap: '1rem',
            alignItems: 'flex-end',
            flexWrap: 'wrap',
            padding: '0.5rem 0',
          }}
        >
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 240px' }}>
            <label className="form-label">
              <Users size={14} /> Customer
            </label>
            <select
              className="form-input"
              value={filterCustomer}
              onChange={(e) => setFilterCustomer(e.target.value)}
            >
              <option value="">Semua Customer</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code ? `${c.code} — ${c.name}` : c.name}
                </option>
              ))}
            </select>
          </div>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.85rem',
              marginBottom: '0.35rem',
            }}
          >
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
            />
            Customer aktif saja
          </label>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.85rem',
              marginBottom: '0.35rem',
            }}
          >
            <input
              type="checkbox"
              checked={filledOnly}
              onChange={(e) => setFilledOnly(e.target.checked)}
            />
            Hanya tarif terisi
          </label>
          <div style={{ display: 'flex', gap: '0.5rem', marginLeft: 'auto', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handlePrint}
              disabled={!rows.length}
              style={{ background: 'var(--accent-color)', color: 'white', border: 'none' }}
            >
              <Printer size={16} /> Print
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleExportPdf}
              disabled={!rows.length}
              style={{ background: '#dc2626', color: 'white', border: 'none' }}
            >
              <FileText size={16} /> PDF
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleExportExcel}
              disabled={!rows.length}
            >
              <Download size={16} /> Excel
            </button>
          </div>
        </div>
      </GlassCard>

      {error && (
        <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>
      )}

      <div
        style={{
          display: 'flex',
          gap: '1rem',
          marginBottom: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <GlassCard style={{ flex: '1 1 160px', padding: '0.85rem 1rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Customer</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{customerCount}</div>
        </GlassCard>
        <GlassCard style={{ flex: '1 1 160px', padding: '0.85rem 1rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Baris tarif</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{rows.length}</div>
        </GlassCard>
      </div>

      <GlassCard>
        {loading ? (
          <p style={{ textAlign: 'center', padding: '2rem', opacity: 0.6 }}>Memuat...</p>
        ) : (
          <>
            <div className="table-container" style={{ overflowX: 'auto' }}>
              <table
                className="data-table"
                style={{
                  width: '100%',
                  borderCollapse: 'separate',
                  borderSpacing: 0,
                  minWidth: 780,
                }}
              >
                <thead>
                  <tr>
                    <th style={thStyle}>Jenis Kendaraan</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>BBM</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Tol</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Uang Mel</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Parkir</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Lain-lain</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Uang Jalan</th>
                  </tr>
                </thead>
                {paginatedGroups.map((g, gi) => (
                  <tbody key={g.customer_id}>
                    <tr>
                      <td
                        colSpan={7}
                        style={{
                          padding: '0.7rem 0.85rem',
                          background: gi % 2 === 0 ? '#eef2ff' : '#f1f5f9',
                          borderTop: '3px solid #64748b',
                          borderBottom: '1px solid #cbd5e1',
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: '#0f172a',
                        }}
                      >
                        <span style={{ color: '#2563eb', marginRight: '0.5rem' }}>
                          {g.customer_code || '—'}
                        </span>
                        {g.customer_name}
                        <span
                          style={{
                            marginLeft: '0.65rem',
                            fontWeight: 500,
                            fontSize: '0.75rem',
                            color: '#64748b',
                          }}
                        >
                          {g.tariffs.length} jenis
                        </span>
                      </td>
                    </tr>
                    {g.tariffs.map((r, ri) => (
                      <tr
                        key={`${r.customer_id}-${r.vehicle_type_id}`}
                        style={{
                          background: ri % 2 === 0 ? '#fff' : 'rgba(248,250,252,0.9)',
                        }}
                      >
                        <td style={tdStyle}>{r.vehicle_type_name}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                          {formatIDR(r.bbm)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                          {formatIDR(r.tol)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                          {formatIDR(r.uang_mel)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                          {formatIDR(r.parkir)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                          {formatIDR(r.lain_lain)}
                        </td>
                        <td
                          style={{
                            ...tdStyle,
                            textAlign: 'right',
                            whiteSpace: 'nowrap',
                            fontWeight: 700,
                            color: 'var(--accent-color)',
                          }}
                        >
                          {formatIDR(r.uang_jalan)}
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td
                        colSpan={7}
                        style={{
                          height: 10,
                          borderBottom: '1px dashed #94a3b8',
                          padding: 0,
                          background: 'transparent',
                        }}
                      />
                    </tr>
                  </tbody>
                ))}
                {!paginatedGroups.length && (
                  <tbody>
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', opacity: 0.6, padding: '2rem' }}>
                        Tidak ada data tarif.
                      </td>
                    </tr>
                  </tbody>
                )}
              </table>
            </div>
            <TablePager
              page={safePage}
              pageSize={PAGE_SIZE}
              totalItems={grouped.length}
              onPageChange={setPage}
              label="Customer"
            />
          </>
        )}
      </GlassCard>
    </>
  );
};

const thStyle = {
  padding: '0.65rem 0.75rem',
  borderBottom: '2px solid #cbd5e1',
  background: '#f8fafc',
  fontSize: '0.78rem',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  color: '#475569',
  whiteSpace: 'nowrap',
};

const tdStyle = {
  padding: '0.55rem 0.75rem',
  borderBottom: '1px solid #e2e8f0',
  fontSize: '0.875rem',
  verticalAlign: 'middle',
};

export default CustomerTariffReportTab;
