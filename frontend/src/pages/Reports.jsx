import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import { Download, Printer, Calendar, Truck, Users, FileText, MapPinned } from 'lucide-react';
import { apiFetch } from '../api';
import { useAuth } from '../auth/AuthContext';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import DeliveryRouteReportTab from './DeliveryRouteReportTab';
import { computeUangJalanTotals } from '../utils/saleExport';

const formatIDR = (val) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(val) || 0
  );

const formatDate = (d) => {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
};

const enrichSaleReportRow = (s) => {
  if (s.rounding_uang_jalan != null && s.subtotal_uang_jalan != null) {
    return s;
  }
  const { subtotal, rounding, total } = computeUangJalanTotals(s.uang_jalan, s.extra_uang_jalan);
  return {
    ...s,
    subtotal_uang_jalan: subtotal,
    rounding_uang_jalan: rounding,
    total_uang_jalan: total,
  };
};

const Reports = () => {
  const { hasPermission } = useAuth();
  const canSalesReport = hasPermission('reports:read');
  const canRouteReport = hasPermission('delivery_routes:read');

  const [activeTab, setActiveTab] = useState(
    canSalesReport ? 'sales' : canRouteReport ? 'routes' : 'sales'
  );
  const [sales, setSales] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);
  const firstDay = thirtyDaysAgo.toISOString().split('T')[0];
  const lastDay = today.toISOString().split('T')[0];

  const [fromDate, setFromDate] = useState(firstDay);
  const [toDate, setToDate] = useState(lastDay);
  const [filterDriver, setFilterDriver] = useState('');
  const [filterCustomer, setFilterCustomer] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [driverList, customerList] = await Promise.all([
        apiFetch('/api/drivers'),
        apiFetch('/api/customers'),
      ]);
      setDrivers(driverList);
      setCustomers(customerList);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const fetchReport = async () => {
    setLoading(true);
    try {
      let url = '/api/reports/sales?';
      if (fromDate) url += `from=${fromDate}&`;
      if (toDate) url += `to=${toDate}&`;
      if (filterDriver) url += `driver_id=${filterDriver}&`;
      if (filterCustomer) url += `customer_id=${filterCustomer}&`;
      const data = await apiFetch(url);
      setSales((Array.isArray(data) ? data : []).map(enrichSaleReportRow));
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (canSalesReport) fetchData();
  }, [canSalesReport]);

  useEffect(() => {
    if (activeTab === 'sales' && canSalesReport) fetchReport();
  }, [activeTab, fromDate, toDate, filterDriver, filterCustomer, canSalesReport]);

  // Summary calculations
  const totalTransaksi = sales.length;
  const totalBaseUangJalan = sales.reduce((sum, s) => sum + s.uang_jalan, 0);
  const totalExtra = sales.reduce((sum, s) => sum + s.extra_uang_jalan, 0);
  const totalRounding = sales.reduce((sum, s) => sum + (s.rounding_uang_jalan || 0), 0);
  const totalUangJalan = sales.reduce((sum, s) => sum + s.total_uang_jalan, 0);

  // Group by driver
  const driverSummary = {};
  sales.forEach((s) => {
    if (!driverSummary[s.driver_name]) {
      driverSummary[s.driver_name] = { count: 0, total: 0 };
    }
    driverSummary[s.driver_name].count += 1;
    driverSummary[s.driver_name].total += s.total_uang_jalan;
  });

  // Group by customer
  const customerSummary = {};
  sales.forEach((s) => {
    const custs = s.customers.split(', ');
    custs.forEach((c) => {
      if (!customerSummary[c]) {
        customerSummary[c] = { count: 0, total: 0 };
      }
      customerSummary[c].count += 1;
      customerSummary[c].total += s.total_uang_jalan / custs.length;
    });
  });

  const handleExportPdf = () => {
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageWidth = pdf.internal.pageSize.getWidth();
    const marginX = 10;
    const tableWidth = pageWidth - marginX * 2;

    pdf.setFontSize(16);
    pdf.text('Laporan Uang Jalan', pageWidth / 2, 14, { align: 'center' });
    pdf.setFontSize(10);
    pdf.setTextColor(100);
    pdf.text(
      `Periode: ${formatDate(fromDate)} - ${formatDate(toDate)} | Dicetak: ${new Date().toLocaleString('id-ID')}`,
      pageWidth / 2,
      20,
      { align: 'center' }
    );
    pdf.setTextColor(0);

    const summaryCol = tableWidth / 4;

    autoTable(pdf, {
      startY: 26,
      margin: { left: marginX, right: marginX },
      tableWidth,
      body: [
        [
          { content: 'Total Transaksi', styles: { fillColor: [241, 245, 249], fontStyle: 'bold' } },
          { content: String(totalTransaksi), styles: { halign: 'center', fontStyle: 'bold', fontSize: 12 } },
          { content: 'Total Uang Jalan', styles: { fillColor: [241, 245, 249], fontStyle: 'bold' } },
          { content: formatIDR(totalUangJalan), styles: { halign: 'right', fontStyle: 'bold', fontSize: 12 } },
        ],
      ],
      theme: 'grid',
      styles: { fontSize: 10, cellPadding: 4, lineColor: [203, 213, 225], lineWidth: 0.1 },
      columnStyles: {
        0: { cellWidth: summaryCol },
        1: { cellWidth: summaryCol },
        2: { cellWidth: summaryCol },
        3: { cellWidth: summaryCol },
      },
    });

    const detailColumns = {
      0: { cellWidth: 10, halign: 'center' },
      1: { cellWidth: 22, halign: 'center' },
      2: { cellWidth: 30, halign: 'left' },
      3: { cellWidth: 22, halign: 'center' },
      4: { cellWidth: 22, halign: 'left' },
      5: { cellWidth: 40, halign: 'left' },
      6: { cellWidth: 18, halign: 'center' },
      7: { cellWidth: 24, halign: 'right' },
      8: { cellWidth: 22, halign: 'right' },
      9: { cellWidth: 22, halign: 'right' },
      10: { cellWidth: 24, halign: 'right' },
    };

    autoTable(pdf, {
      startY: pdf.lastAutoTable.finalY + 6,
      margin: { left: marginX, right: marginX },
      tableWidth,
      head: [['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis', 'Uang Jalan', 'Tambahan', 'Pembulatan', 'Total']],
      body: sales.map((s, i) => [
        i + 1,
        formatDate(s.date),
        s.sale_no,
        s.vehicle_plate,
        s.driver_name,
        s.customers,
        s.vehicle_type,
        formatIDR(s.uang_jalan),
        formatIDR(s.extra_uang_jalan),
        formatIDR(s.rounding_uang_jalan),
        formatIDR(s.total_uang_jalan),
      ]),
      foot: [
        [
          { content: 'TOTAL', colSpan: 7, styles: { halign: 'right', fontStyle: 'bold' } },
          { content: formatIDR(totalBaseUangJalan), styles: { halign: 'right', fontStyle: 'bold' } },
          { content: formatIDR(totalExtra), styles: { halign: 'right', fontStyle: 'bold' } },
          { content: formatIDR(totalRounding), styles: { halign: 'right', fontStyle: 'bold' } },
          { content: formatIDR(totalUangJalan), styles: { halign: 'right', fontStyle: 'bold' } },
        ],
      ],
      styles: {
        fontSize: 9,
        cellPadding: { top: 3, right: 3, bottom: 3, left: 3 },
        lineColor: [203, 213, 225],
        lineWidth: 0.1,
        overflow: 'linebreak',
      },
      headStyles: {
        fillColor: [51, 65, 85],
        textColor: 255,
        fontStyle: 'bold',
        halign: 'center',
        cellPadding: 4,
      },
      footStyles: {
        fillColor: [241, 245, 249],
        textColor: 20,
        fontStyle: 'bold',
        cellPadding: 4,
      },
      columnStyles: detailColumns,
      didParseCell(data) {
        if (data.section === 'head' && [7, 8, 9, 10].includes(data.column.index)) {
          data.cell.styles.halign = 'right';
        }
      },
    });

    pdf.save(`laporan-uang-jalan-${fromDate}-${toDate}.pdf`);
  };

  const handleExportExcel = () => {
    const rows = [
      ['Laporan Uang Jalan'],
      [`Periode: ${formatDate(fromDate)} - ${formatDate(toDate)}`],
      [`Dicetak: ${new Date().toLocaleString('id-ID')}`],
      [],
      ['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis Kendaraan', 'Uang Jalan', 'Tambahan', 'Pembulatan', 'Total Uang Jalan'],
      ...sales.map((s, i) => [
        i + 1,
        formatDate(s.date),
        s.sale_no,
        s.vehicle_plate,
        s.driver_name,
        s.customers,
        s.vehicle_type,
        s.uang_jalan,
        s.extra_uang_jalan,
        s.rounding_uang_jalan,
        s.total_uang_jalan,
      ]),
      [],
      ['', '', '', '', '', '', 'TOTAL', totalBaseUangJalan, totalExtra, totalRounding, totalUangJalan],
    ];

    const ws = XLSX.utils.aoa_to_sheet(rows);
    ws['!cols'] = [
      { wch: 5 }, { wch: 14 }, { wch: 22 }, { wch: 14 }, { wch: 16 },
      { wch: 28 }, { wch: 16 }, { wch: 16 }, { wch: 14 }, { wch: 12 }, { wch: 18 },
    ];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Laporan');
    XLSX.writeFile(wb, `laporan-uang-jalan-${fromDate}-${toDate}.xlsx`);
  };

  const handlePrint = () => {
    const printWindow = window.open('', '_blank', 'width=1100,height=800');
    if (!printWindow) { alert('Popup diblokir!'); return; }

    const tableRows = sales.map((s, i) => `
      <tr>
        <td style="text-align:center">${i + 1}</td>
        <td style="text-align:center">${formatDate(s.date)}</td>
        <td>${s.sale_no}</td>
        <td style="text-align:center">${s.vehicle_plate}</td>
        <td>${s.driver_name}</td>
        <td>${s.customers}</td>
        <td style="text-align:center">${s.vehicle_type}</td>
        <td class="num">${formatIDR(s.uang_jalan)}</td>
        <td class="num">${formatIDR(s.extra_uang_jalan)}</td>
        <td class="num">${formatIDR(s.rounding_uang_jalan)}</td>
        <td class="num" style="font-weight:600">${formatIDR(s.total_uang_jalan)}</td>
      </tr>
    `).join('');

    printWindow.document.write(`<!DOCTYPE html><html><head>
      <title>Laporan Uang Jalan</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; color: #111; }
        h1 { text-align: center; font-size: 20px; margin-bottom: 4px; }
        .meta { text-align: center; color: #555; margin-bottom: 20px; font-size: 12px; }
        .summary { display: flex; gap: 2rem; margin-bottom: 16px; }
        .summary-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 20px; }
        .summary-card label { font-size: 11px; color: #64748b; text-transform: uppercase; }
        .summary-card h2 { margin: 4px 0 0; font-size: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; table-layout: fixed; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; vertical-align: middle; word-wrap: break-word; }
        th { background: #334155; color: white; }
        th.num, td.num { text-align: right; }
        th.center, td.center { text-align: center; }
        tfoot td { background: #f1f5f9; font-weight: 700; }
        col.no { width: 4%; }
        col.date { width: 9%; }
        col.trx { width: 12%; }
        col.plate { width: 8%; }
        col.driver { width: 9%; }
        col.customer { width: 22%; }
        col.type { width: 8%; }
        col.money { width: 10%; }
        @media print { body { padding: 0; } }
      </style>
    </head><body>
      <h1>Laporan Uang Jalan</h1>
      <p class="meta">Periode: ${formatDate(fromDate)} - ${formatDate(toDate)} | Dicetak: ${new Date().toLocaleString('id-ID')}</p>
      <div class="summary">
        <div class="summary-card"><label>Total Transaksi</label><h2>${totalTransaksi}</h2></div>
        <div class="summary-card"><label>Total Uang Jalan</label><h2>${formatIDR(totalUangJalan)}</h2></div>
        <div class="summary-card"><label>Total Pembulatan</label><h2>${formatIDR(totalRounding)}</h2></div>
      </div>
      <table>
        <colgroup>
          <col class="no" /><col class="date" /><col class="trx" /><col class="plate" />
          <col class="driver" /><col class="customer" /><col class="type" />
          <col class="money" /><col class="money" /><col class="money" /><col class="money" />
        </colgroup>
        <thead><tr><th class="center">No</th><th class="center">Tanggal</th><th>No. Transaksi</th><th class="center">Kendaraan</th><th>Sopir</th><th>Customer</th><th class="center">Jenis</th><th class="num">Uang Jalan</th><th class="num">Tambahan</th><th class="num">Pembulatan</th><th class="num">Total</th></tr></thead>
        <tbody>${tableRows}</tbody>
        <tfoot><tr><td colspan="7" class="num">TOTAL</td><td class="num">${formatIDR(totalBaseUangJalan)}</td><td class="num">${formatIDR(totalExtra)}</td><td class="num">${formatIDR(totalRounding)}</td><td class="num">${formatIDR(totalUangJalan)}</td></tr></tfoot>
      </table>
    </body></html>`);
    printWindow.document.close();
    printWindow.onload = () => { printWindow.focus(); printWindow.print(); };
  };

  const tabStyle = (tab) => ({
    padding: '0.6rem 1.25rem',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.9rem',
    background: activeTab === tab ? 'var(--accent-color)' : 'var(--bg-secondary)',
    color: activeTab === tab ? 'white' : 'var(--text-primary)',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Laporan</h1>
          <p>
            {activeTab === 'routes'
              ? 'Laporan ringkasan dan detail rute pengiriman'
              : 'Laporan ringkasan dan detail transaksi uang jalan'}
          </p>
        </div>
        {activeTab === 'sales' && canSalesReport && (
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button className="btn btn-secondary" onClick={handlePrint}
              style={{ background: 'var(--accent-color)', color: 'white', border: 'none' }}>
              <Printer size={18} /> Print
            </button>
            <button className="btn btn-secondary" onClick={handleExportPdf}
              style={{ background: '#dc2626', color: 'white', border: 'none' }}>
              <FileText size={18} /> PDF
            </button>
            <button className="btn btn-secondary" onClick={handleExportExcel}>
              <Download size={18} /> Excel
            </button>
          </div>
        )}
      </div>

      {(canSalesReport && canRouteReport) && (
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button type="button" style={tabStyle('sales')} onClick={() => setActiveTab('sales')}>
            <FileText size={16} /> Uang Jalan
          </button>
          <button type="button" style={tabStyle('routes')} onClick={() => setActiveTab('routes')}>
            <MapPinned size={16} /> Rute Pengiriman
          </button>
        </div>
      )}

      <GlassCard style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', padding: '0.5rem 0' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 180px' }}>
            <label className="form-label"><Calendar size={14} /> Dari Tanggal</label>
            <input type="date" className="form-input" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 180px' }}>
            <label className="form-label"><Calendar size={14} /> Sampai Tanggal</label>
            <input type="date" className="form-input" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </div>
          {activeTab === 'sales' && canSalesReport && (
            <>
              <div className="form-group" style={{ marginBottom: 0, flex: '1 1 200px' }}>
                <label className="form-label"><Truck size={14} /> Sopir</label>
                <select className="form-input" value={filterDriver} onChange={(e) => setFilterDriver(e.target.value)}>
                  <option value="">Semua Sopir</option>
                  {drivers.map((d) => {
                    const bankInfo = [d.bank_name, d.bank_account].filter(Boolean).join(' ');
                    const label = bankInfo ? `${d.name} (Rek: ${bankInfo})` : d.name;
                    return <option key={d.id} value={d.id}>{label}</option>;
                  })}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0, flex: '1 1 200px' }}>
                <label className="form-label"><Users size={14} /> Customer</label>
                <select className="form-input" value={filterCustomer} onChange={(e) => setFilterCustomer(e.target.value)}>
                  <option value="">Semua Customer</option>
                  {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </>
          )}
        </div>
      </GlassCard>

      {activeTab === 'routes' && canRouteReport && (
        <DeliveryRouteReportTab fromDate={fromDate} toDate={toDate} />
      )}

      {activeTab === 'sales' && canSalesReport && (
        <>
      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Transaksi</p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '2rem', backgroundImage: 'none', WebkitTextFillColor: 'initial', color: 'var(--accent-color)' }}>{totalTransaksi}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Uang Jalan</p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '1.6rem', backgroundImage: 'none', WebkitTextFillColor: 'initial', color: '#16a34a' }}>{formatIDR(totalUangJalan)}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Tambahan</p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '1.6rem', backgroundImage: 'none', WebkitTextFillColor: 'initial', color: '#ea580c' }}>{formatIDR(totalExtra)}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Pembulatan</p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '1.6rem', backgroundImage: 'none', WebkitTextFillColor: 'initial', color: '#7c3aed' }}>{formatIDR(totalRounding)}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Jumlah Sopir</p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '2rem', backgroundImage: 'none', WebkitTextFillColor: 'initial', color: 'var(--text-primary)' }}>{Object.keys(driverSummary).length}</h2>
          </div>
        </GlassCard>
      </div>

      {/* Ringkasan per Sopir & Customer */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <GlassCard title="Ringkasan per Sopir">
          <div className="table-container" style={{ padding: 0, maxHeight: '280px', overflowY: 'auto' }}>
            <table className="glass-table" style={{ fontSize: '0.85rem' }}>
              <thead><tr><th>Sopir</th><th style={{ textAlign: 'center' }}>Trip</th><th style={{ textAlign: 'right' }}>Total</th></tr></thead>
              <tbody>
                {Object.entries(driverSummary)
                  .sort((a, b) => b[1].total - a[1].total)
                  .map(([name, data]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td style={{ textAlign: 'center' }}>{data.count}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatIDR(data.total)}</td>
                    </tr>
                  ))}
                {Object.keys(driverSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard title="Ringkasan per Customer">
          <div className="table-container" style={{ padding: 0, maxHeight: '280px', overflowY: 'auto' }}>
            <table className="glass-table" style={{ fontSize: '0.85rem' }}>
              <thead><tr><th>Customer</th><th style={{ textAlign: 'center' }}>Trip</th><th style={{ textAlign: 'right' }}>Total</th></tr></thead>
              <tbody>
                {Object.entries(customerSummary)
                  .sort((a, b) => b[1].total - a[1].total)
                  .map(([name, data]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td style={{ textAlign: 'center' }}>{data.count}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatIDR(data.total)}</td>
                    </tr>
                  ))}
                {Object.keys(customerSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>

      {/* Detail Table */}
      <GlassCard title={`Detail Transaksi (${totalTransaksi} data)`}>
        <div className="table-container" style={{ padding: 0 }}>
          <table className="glass-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th style={{ width: '40px', textAlign: 'center' }}>No</th>
                <th>Tanggal</th>
                <th>No. Transaksi</th>
                <th>Kendaraan</th>
                <th>Sopir</th>
                <th>Customer</th>
                <th>Jenis</th>
                <th style={{ textAlign: 'right' }}>Uang Jalan</th>
                <th style={{ textAlign: 'right' }}>Tambahan</th>
                <th style={{ textAlign: 'right' }}>Pembulatan</th>
                <th style={{ textAlign: 'right' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s, i) => (
                <tr key={s.id}>
                  <td style={{ textAlign: 'center' }}>{i + 1}</td>
                  <td>{formatDate(s.date)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{s.sale_no}</td>
                  <td>{s.vehicle_plate}</td>
                  <td>{s.driver_name}</td>
                  <td>{s.customers}</td>
                  <td>{s.vehicle_type}</td>
                  <td style={{ textAlign: 'right' }}>{formatIDR(s.uang_jalan)}</td>
                  <td style={{ textAlign: 'right' }}>{formatIDR(s.extra_uang_jalan)}</td>
                  <td style={{ textAlign: 'right', color: '#7c3aed' }}>{formatIDR(s.rounding_uang_jalan)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatIDR(s.total_uang_jalan)}</td>
                </tr>
              ))}
              {sales.length === 0 && (
                <tr>
                  <td colSpan="11" style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                    {loading ? 'Memuat data...' : 'Belum ada transaksi dalam periode ini'}
                  </td>
                </tr>
              )}
            </tbody>
            {sales.length > 0 && (
              <tfoot>
                <tr style={{ fontWeight: 700, background: 'var(--bg-secondary)' }}>
                  <td colSpan="7" style={{ textAlign: 'right' }}>TOTAL</td>
                  <td style={{ textAlign: 'right' }}>{formatIDR(totalBaseUangJalan)}</td>
                  <td style={{ textAlign: 'right' }}>{formatIDR(totalExtra)}</td>
                  <td style={{ textAlign: 'right', color: '#7c3aed' }}>{formatIDR(totalRounding)}</td>
                  <td style={{ textAlign: 'right', fontSize: '1rem' }}>{formatIDR(totalUangJalan)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </GlassCard>
        </>
      )}

      {!canSalesReport && !canRouteReport && (
        <GlassCard>
          <p style={{ textAlign: 'center', padding: '2rem', opacity: 0.6 }}>Anda tidak memiliki akses ke laporan.</p>
        </GlassCard>
      )}
    </div>
  );
};

export default Reports;
