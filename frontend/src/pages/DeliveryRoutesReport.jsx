import React, { useState, useEffect, useCallback } from 'react';
import { Printer, FileText, Download, RefreshCw } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import DeliveryRouteStopDetailTable from '../components/DeliveryRouteStopDetailTable';
import { apiFetch } from '../api';
import { todayIso, formatItemQuantity } from '../utils/deliveryRouteUtils';
import {
  buildReportQuery,
  exportDeliveryRoutePdf,
  exportDeliveryRouteExcel,
  printDeliveryRouteReport,
  formatReportDate,
} from '../utils/deliveryRouteReportExport';

const emptyReport = () => ({ total_routes: 0, total_stops: 0, total_items_qty: 0, routes: [], stop_rows: [] });

const DeliveryRoutesReport = () => {
  const [report, setReport] = useState(emptyReport);
  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [reportError, setReportError] = useState(null);
  const [filterFrom, setFilterFrom] = useState(todayIso);
  const [filterTo, setFilterTo] = useState(todayIso);
  const [filterVehicleType, setFilterVehicleType] = useState('');

  const filterParams = { fromDate: filterFrom, toDate: filterTo, vehicleTypeId: filterVehicleType };

  const fetchReport = async () => {
    try {
      const data = await apiFetch(`/api/reports/delivery-routes${buildReportQuery(filterParams)}`);
      setReport(data);
      setReportError(null);
    } catch (err) {
      setReport(emptyReport());
      setReportError(err.message || 'Gagal memuat laporan rute.');
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const dataVt = await apiFetch('/api/vehicle-types');
      setVehicleTypes(Array.isArray(dataVt) ? dataVt : []);
    } catch {
      setVehicleTypes([]);
    }
    await fetchReport();
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [filterFrom, filterTo, filterVehicleType]);

  const loadReportForExport = useCallback(async () => {
    const data = await apiFetch(`/api/reports/delivery-routes${buildReportQuery(filterParams)}`);
    setReport(data);
    return data;
  }, [filterFrom, filterTo, filterVehicleType]);

  const runExport = async (action) => {
    setExporting(true);
    try {
      const data = await loadReportForExport();
      if (!data.routes?.length && !data.stop_rows?.length) {
        alert('Tidak ada data rute pada filter ini untuk diekspor.');
        return;
      }
      action(data);
    } catch (err) {
      alert(err.message || 'Gagal memuat data laporan.');
    } finally {
      setExporting(false);
    }
  };

  const { routes: reportRoutes, stop_rows, total_routes, total_stops, total_items_qty } = report;

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Laporan Rute</h1>
          <p className="page-subtitle">
            Ringkasan rute pengiriman per periode. Cetak atau unduh PDF dan Excel.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchData} disabled={loading}>
          <RefreshCw size={18} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {reportError && (
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
          {reportError}
        </div>
      )}

      <GlassCard title="Laporan Rute">
        <div
          style={{
            display: 'flex',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '1rem',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', flex: '1 1 400px' }}>
            <div className="form-group" style={{ marginBottom: 0, minWidth: '140px' }}>
              <label className="form-label">Dari tanggal</label>
              <input
                type="date"
                className="form-input"
                value={filterFrom}
                onChange={(e) => setFilterFrom(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0, minWidth: '140px' }}>
              <label className="form-label">Sampai tanggal</label>
              <input
                type="date"
                className="form-input"
                value={filterTo}
                onChange={(e) => setFilterTo(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0, minWidth: '180px' }}>
              <label className="form-label">Jenis Kendaraan</label>
              <select
                className="form-input"
                value={filterVehicleType}
                onChange={(e) => setFilterVehicleType(e.target.value)}
              >
                <option value="">Semua</option>
                {vehicleTypes.map((vt) => (
                  <option key={vt.id} value={vt.id}>
                    {vt.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={exporting || loading}
              onClick={() => runExport((data) => printDeliveryRouteReport(data, filterParams))}
              style={{ background: 'var(--accent-color)', color: 'white', border: 'none' }}
            >
              <Printer size={18} /> Print
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={exporting || loading}
              onClick={() => runExport((data) => exportDeliveryRoutePdf(data, filterParams))}
              style={{ background: '#dc2626', color: 'white', border: 'none' }}
            >
              <FileText size={18} /> PDF
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={exporting || loading}
              onClick={() => runExport((data) => exportDeliveryRouteExcel(data, filterParams))}
            >
              <Download size={18} /> Excel
            </button>
          </div>
        </div>

        <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Periode: {formatReportDate(filterFrom)} — {formatReportDate(filterTo)}
          {filterVehicleType && (
            <>
              {' '}
              | Jenis: {vehicleTypes.find((v) => String(v.id) === String(filterVehicleType))?.name || '-'}
            </>
          )}
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '1rem',
            marginBottom: '1.25rem',
          }}
        >
          <div className="report-stat-card">
            <span>Total Rute</span>
            <strong>{total_routes}</strong>
          </div>
          <div className="report-stat-card">
            <span>Total Customer</span>
            <strong>{total_stops}</strong>
          </div>
          <div className="report-stat-card">
            <span>Total Qty Barang</span>
            <strong>{formatItemQuantity(total_items_qty ?? 0)}</strong>
          </div>
        </div>

        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Ringkasan Rute</h4>
        <div className="table-container" style={{ padding: 0, marginBottom: '1.25rem' }}>
          <table className="glass-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th>No</th>
                <th>Tanggal</th>
                <th>No. Rute</th>
                <th>Jenis Kendaraan</th>
                <th>No. Transaksi</th>
                <th>Jml Cust</th>
                <th>Customer</th>
                <th>Keterangan</th>
              </tr>
            </thead>
            <tbody>
              {reportRoutes.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
                    {loading ? 'Memuat laporan...' : 'Tidak ada data pada periode ini'}
                  </td>
                </tr>
              ) : (
                reportRoutes.map((r, i) => (
                  <tr key={r.id}>
                    <td>{i + 1}</td>
                    <td>{formatReportDate(r.date)}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.route_no}</td>
                    <td>{r.vehicle_type_name}</td>
                    <td>{r.sale_no || '-'}</td>
                    <td style={{ textAlign: 'center', fontWeight: 600 }}>{r.stop_count}</td>
                    <td>{r.customers}</td>
                    <td>{r.remarks || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Detail Customer & Barang</h4>
        <DeliveryRouteStopDetailTable stopRows={stop_rows} loading={loading} />
      </GlassCard>
    </div>
  );
};

export default DeliveryRoutesReport;
