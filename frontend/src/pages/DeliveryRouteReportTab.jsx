import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import DeliveryRouteStopDetailTable from '../components/DeliveryRouteStopDetailTable';
import { Download, Printer, Truck, FileText } from 'lucide-react';
import { apiFetch } from '../api';
import {
  buildReportQuery,
  exportDeliveryRoutePdf,
  exportDeliveryRouteExcel,
  printDeliveryRouteReport,
  formatReportDate,
} from '../utils/deliveryRouteReportExport';
import { formatItemQuantity } from '../utils/deliveryRouteUtils';

const DeliveryRouteReportTab = ({ fromDate, toDate }) => {
  const [report, setReport] = useState({
    total_routes: 0,
    total_stops: 0,
    total_items_qty: 0,
    routes: [],
    stop_rows: [],
  });
  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterVehicleType, setFilterVehicleType] = useState('');

  const filterParams = { fromDate, toDate, vehicleTypeId: filterVehicleType };
  const { routes, stop_rows, total_routes, total_stops, total_items_qty } = report;

  useEffect(() => {
    (async () => {
      try {
        const vehicleTypeList = await apiFetch('/api/vehicle-types');
        setVehicleTypes(vehicleTypeList);
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        const data = await apiFetch(`/api/reports/delivery-routes${buildReportQuery(filterParams)}`);
        setReport(data);
      } catch (err) {
        console.error(err);
      }
      setLoading(false);
    };
    fetchReport();
  }, [fromDate, toDate, filterVehicleType]);

  return (
    <>
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
        <button
          className="btn btn-secondary"
          onClick={() => printDeliveryRouteReport(report, filterParams)}
          style={{ background: 'var(--accent-color)', color: 'white', border: 'none' }}
        >
          <Printer size={18} /> Print
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => exportDeliveryRoutePdf(report, filterParams)}
          style={{ background: '#dc2626', color: 'white', border: 'none' }}
        >
          <FileText size={18} /> PDF
        </button>
        <button className="btn btn-secondary" onClick={() => exportDeliveryRouteExcel(report, filterParams)}>
          <Download size={18} /> Excel
        </button>
      </div>

      <GlassCard style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', padding: '0.5rem 0' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 200px' }}>
            <label className="form-label">
              <Truck size={14} /> Jenis Kendaraan
            </label>
            <select className="form-input" value={filterVehicleType} onChange={(e) => setFilterVehicleType(e.target.value)}>
              <option value="">Semua Jenis</option>
              {vehicleTypes.map((vt) => (
                <option key={vt.id} value={vt.id}>
                  {vt.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </GlassCard>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Total Rute
            </p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '2rem', color: 'var(--accent-color)' }}>{total_routes}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Total Customer
            </p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '2rem', color: '#16a34a' }}>{total_stops}</h2>
          </div>
        </GlassCard>
        <GlassCard>
          <div style={{ padding: '0.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Total Qty Barang
            </p>
            <h2 style={{ margin: '0.5rem 0 0', fontSize: '2rem', color: '#7c3aed' }}>
              {formatItemQuantity(total_items_qty ?? 0)}
            </h2>
          </div>
        </GlassCard>
      </div>

      <GlassCard title={`Ringkasan Rute (${total_routes} data)`} style={{ marginBottom: '1.5rem' }}>
        <div className="table-container" style={{ padding: 0 }}>
          <table className="glass-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th style={{ width: '40px', textAlign: 'center' }}>No</th>
                <th>Tanggal</th>
                <th>No. Rute</th>
                <th>Jenis Kendaraan</th>
                <th>No. Transaksi</th>
                <th style={{ textAlign: 'center' }}>Jml Cust</th>
                <th>Customer</th>
                <th>Keterangan</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((r, i) => (
                <tr key={r.id}>
                  <td style={{ textAlign: 'center' }}>{i + 1}</td>
                  <td>{formatReportDate(r.date)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.route_no}</td>
                  <td>{r.vehicle_type_name || '-'}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.sale_no || '-'}</td>
                  <td style={{ textAlign: 'center', fontWeight: 600 }}>{r.stop_count}</td>
                  <td>{r.customers}</td>
                  <td>{r.remarks || '-'}</td>
                </tr>
              ))}
              {routes.length === 0 && (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                    {loading ? 'Memuat data...' : 'Belum ada rute dalam periode ini'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard title={`Detail Customer & Barang (${stop_rows.length} baris)`}>
        <DeliveryRouteStopDetailTable
          stopRows={stop_rows}
          loading={loading}
          showSaleNo
          maxHeight="400px"
        />
      </GlassCard>
    </>
  );
};

export default DeliveryRouteReportTab;
