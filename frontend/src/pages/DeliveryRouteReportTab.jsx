import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import DeliveryRouteStopDetailTable from '../components/DeliveryRouteStopDetailTable';
import TablePager from '../components/TablePager';
import { Download, Printer, Truck, FileText, ChevronDown, ChevronRight } from 'lucide-react';
import { apiFetch } from '../api';
import {
  buildReportQuery,
  exportDeliveryRoutePdf,
  exportDeliveryRouteExcel,
  printDeliveryRouteReport,
  formatReportDate,
  formatSaleTransactionText,
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
  const [expandedRouteNo, setExpandedRouteNo] = useState(null);

  const PAGE_SIZE = 15;
  const [page, setPage] = useState(1);

  const filterParams = { fromDate, toDate, vehicleTypeId: filterVehicleType };
  const { routes, stop_rows, total_routes, total_stops, total_items_qty } = report;

  const totalPages = Math.max(1, Math.ceil(routes.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    setPage(1);
  }, [routes.length]);

  const paginatedRoutes = React.useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return routes.slice(start, start + PAGE_SIZE);
  }, [routes, safePage]);

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
      setExpandedRouteNo(null);
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

  const toggleRoute = (routeNo) => {
    setExpandedRouteNo((prev) => (prev === routeNo ? null : routeNo));
  };

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

      <GlassCard style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', gap: '1rem' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Ringkasan Rute ({total_routes} data) — klik baris untuk lihat detail
          </h3>
          {routes.length > PAGE_SIZE && (
            <TablePager
              page={safePage}
              pageSize={PAGE_SIZE}
              totalItems={routes.length}
              onPageChange={setPage}
              label="Rute"
            />
          )}
        </div>
        <div className="table-container" style={{ padding: 0 }}>
          <table className="glass-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th style={{ width: '50px', textAlign: 'center' }}>No</th>
                <th style={{ minWidth: '140px', whiteSpace: 'nowrap' }}>Tanggal</th>
                <th>No. Rute</th>
                <th>Jenis Kendaraan</th>
                <th>No. Transaksi</th>
                <th style={{ textAlign: 'center' }}>Jml Cust</th>
                <th>Customer</th>
                <th>Keterangan</th>
              </tr>
            </thead>
            <tbody>
              {paginatedRoutes.map((r, i) => {
                const globalIndex = (safePage - 1) * PAGE_SIZE + i;
                const isExpanded = expandedRouteNo === r.route_no;
                const routeStops = isExpanded
                  ? stop_rows.filter((sr) => sr.route_no === r.route_no)
                  : [];
                return (
                  <React.Fragment key={r.id}>
                    <tr
                      onClick={() => toggleRoute(r.route_no)}
                      style={{
                        cursor: 'pointer',
                        background: isExpanded ? 'var(--bg-secondary)' : undefined,
                        transition: 'background 0.15s',
                      }}
                      title="Klik untuk lihat detail customer & barang"
                    >
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                          {isExpanded
                            ? <ChevronDown size={14} style={{ color: 'var(--accent-color)' }} />
                            : <ChevronRight size={14} style={{ opacity: 0.5 }} />}
                          {globalIndex + 1}
                        </span>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatReportDate(r.date)}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.route_no}</td>
                      <td>{r.vehicle_type_name || '-'}</td>
                      <td style={{ whiteSpace: 'pre-line', lineHeight: 1.35, fontSize: '0.85rem' }}>
                        {formatSaleTransactionText(r)}
                      </td>
                      <td style={{ textAlign: 'center', fontWeight: 600 }}>{r.stop_count}</td>
                      <td>{r.customers}</td>
                      <td>{r.remarks || '-'}</td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan="8" style={{ padding: 0, background: 'var(--bg-secondary)' }}>
                          <div style={{ padding: '0.75rem 1rem' }}>
                            <h4 style={{
                              margin: '0 0 0.5rem',
                              fontSize: '0.8rem',
                              color: 'var(--text-secondary)',
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}>
                              Detail Customer & Barang — {r.route_no}
                            </h4>
                            <DeliveryRouteStopDetailTable
                              stopRows={routeStops}
                              loading={false}
                              showSaleNo
                              maxHeight="none"
                            />
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
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

      {routes.length > PAGE_SIZE && (
        <div style={{ marginTop: '0.5rem', marginBottom: '1.5rem' }}>
          <TablePager
            page={safePage}
            pageSize={PAGE_SIZE}
            totalItems={routes.length}
            onPageChange={setPage}
            label="Rute"
          />
        </div>
      )}
    </>
  );
};

export default DeliveryRouteReportTab;
