import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Trash2, Edit, RefreshCw, Wallet, AlertCircle, FileBarChart } from 'lucide-react';
import GlassCard from '../components/GlassCard';
import { apiFetch } from '../api';
import { useAuth } from '../auth/AuthContext';
import { formatRouteDate, tomorrowIso } from '../utils/deliveryRouteUtils';

const DeliveryRoutesList = () => {
  const navigate = useNavigate();
  const { hasPermission, canWritePage } = useAuth();
  const canWriteRoutes = canWritePage('/delivery-routes');
  const canGenerateSale =
    hasPermission('sales:write') || hasPermission('delivery_routes:write');
  const showRouteActions = canWriteRoutes || canGenerateSale;
  const [routes, setRoutes] = useState([]);
  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [routesError, setRoutesError] = useState(null);
  const [filterFrom, setFilterFrom] = useState(tomorrowIso);
  const [filterTo, setFilterTo] = useState(tomorrowIso);
  const [filterVehicleType, setFilterVehicleType] = useState('');
  const [generatingId, setGeneratingId] = useState(null);
  const [syncingAll, setSyncingAll] = useState(false);

  const buildListQuery = () => {
    const params = new URLSearchParams();
    if (filterFrom) params.set('from', filterFrom);
    if (filterTo) params.set('to', filterTo);
    if (filterVehicleType) params.set('vehicle_type_id', filterVehicleType);
    const q = params.toString();
    return q ? `?${q}` : '';
  };

  const fetchRoutes = async () => {
    try {
      const dataR = await apiFetch(`/api/delivery-routes${buildListQuery()}`);
      setRoutes(dataR);
      setRoutesError(null);
    } catch (err) {
      setRoutes([]);
      setRoutesError(err.message);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    setRoutesError(null);
    try {
      const dataVt = await apiFetch('/api/vehicle-types');
      setVehicleTypes(Array.isArray(dataVt) ? dataVt : []);
    } catch (err) {
      setVehicleTypes([]);
      setRoutesError(err.message || 'Gagal memuat jenis kendaraan.');
    }
    await fetchRoutes();
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [filterFrom, filterTo, filterVehicleType]);

  const handleDelete = async (route) => {
    if (route.is_finance_paid) {
      alert(
        'Rute dikunci karena uang jalan sudah disetujui dibayar oleh Finance. Hapus transaksi uang jalan di menu Uang Jalan untuk membuka kunci.',
      );
      return;
    }
    const confirmMsg = route.sale_no
      ? `Hapus rute ${route.route_no}? Transaksi uang jalan ${route.sale_no} juga akan dihapus otomatis.`
      : `Hapus rute ${route.route_no}?`;
    if (!window.confirm(confirmMsg)) return;
    try {
      await apiFetch(`/api/delivery-routes/${route.id}`, { method: 'DELETE' });
      await fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleEdit = (route) => {
    if (route.is_finance_paid) {
      alert(
        'Rute dikunci karena uang jalan sudah disetujui dibayar oleh Finance. Hapus transaksi uang jalan di menu Uang Jalan untuk membuka kunci.',
      );
      return;
    }
    navigate(`/delivery-routes/${route.id}/edit`);
  };

  const handleSyncAll = async () => {
    if (!filterFrom || !filterTo) {
      alert('Isi rentang tanggal terlebih dahulu.');
      return;
    }
    const vtLabel = filterVehicleType
      ? vehicleTypes.find((vt) => String(vt.id) === String(filterVehicleType))?.name
      : null;
    const periodLabel = `${filterFrom} s/d ${filterTo}`;
    const scopeLabel = vtLabel ? `${periodLabel} (jenis: ${vtLabel})` : periodLabel;
    const msg =
      `Sync semua transaksi uang jalan untuk periode ${scopeLabel}?\n\n` +
      'Rute yang sudah dibayar Finance akan dilewati. Nominal dihitung ulang dari tarif customer.';
    if (!window.confirm(msg)) return;

    setSyncingAll(true);
    try {
      const result = await apiFetch(`/api/delivery-routes/sync-sales${buildListQuery()}`, {
        method: 'POST',
      });
      await fetchRoutes();

      const errorLines = (result.skipped_errors || [])
        .slice(0, 8)
        .map((item) => `- ${item.route_no}: ${item.reason}`);
      const moreErrors =
        (result.skipped_errors?.length || 0) > 8
          ? `\n...dan ${result.skipped_errors.length - 8} rute lainnya`
          : '';

      alert(
        `Sync selesai.\n\n` +
          `Total rute: ${result.total_routes}\n` +
          `Berhasil: ${result.synced} (baru: ${result.created}, diperbarui: ${result.updated})\n` +
          `Dilewati (Finance): ${result.skipped_locked}\n` +
          `Gagal: ${result.skipped_errors?.length || 0}` +
          (errorLines.length ? `\n\nDetail gagal:\n${errorLines.join('\n')}${moreErrors}` : ''),
      );
    } catch (err) {
      alert(err.message);
    } finally {
      setSyncingAll(false);
    }
  };

  const handleGenerateSale = async (routeId, hasSale) => {
    const msg = hasSale
      ? 'Perbarui transaksi uang jalan dari rute ini? Nominal customer dihitung ulang dari tarif.'
      : 'Buat transaksi uang jalan dari rute ini?';
    if (!window.confirm(msg)) return;
    setGeneratingId(routeId);
    try {
      await apiFetch(`/api/delivery-routes/${routeId}/generate-sale`, { method: 'POST' });
      await fetchData();
      if (window.confirm('Uang jalan berhasil dibuat/diperbarui. Buka halaman Uang Jalan?')) {
        navigate('/sales');
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setGeneratingId(null);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Daftar Rute Pengiriman</h1>
          <p className="page-subtitle">Kelola rute pengiriman dan buat uang jalan dari rute.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={fetchData} disabled={loading}>
            <RefreshCw size={18} className={loading ? 'spin' : ''} />
            Refresh
          </button>
          <Link
            to="/delivery-routes/report"
            className="btn btn-secondary"
            style={{ textDecoration: 'none' }}
          >
            <FileBarChart size={18} /> Laporan Rute
          </Link>
          <Link to="/delivery-routes/new" className="btn btn-primary" style={{ textDecoration: 'none', display: canWriteRoutes ? undefined : 'none' }}>
            <Plus size={18} /> Input Rute
          </Link>
        </div>
      </div>

      {routesError && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5rem',
          }}
        >
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>{routesError}</div>
        </div>
      )}

      <GlassCard title="Daftar Rute">
        <div
          style={{
            display: 'flex',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '1rem',
            alignItems: 'flex-end',
          }}
        >
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
          {canGenerateSale && (
            <button
              type="button"
              className="btn btn-primary"
              style={{ whiteSpace: 'nowrap' }}
              disabled={syncingAll || loading || generatingId !== null}
              title="Buat/perbarui uang jalan untuk semua rute dalam periode filter"
              onClick={handleSyncAll}
            >
              <RefreshCw size={16} className={syncingAll ? 'spin' : ''} />
              {syncingAll ? 'Sync...' : 'Sync Semua'}
            </button>
          )}
        </div>

        <div className="table-container" style={{ padding: 0 }}>
          <table className="glass-table">
            <thead>
              <tr>
                <th>No Rute</th>
                <th>Tanggal</th>
                <th>Jenis Kendaraan</th>
                <th>Rit</th>
                <th>Stop</th>
                <th>Uang Jalan</th>
                <th style={{ textAlign: 'right', minWidth: '220px', display: showRouteActions ? undefined : 'none' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
                    Memuat...
                  </td>
                </tr>
              ) : routes.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                    {routesError ? (
                      'Daftar rute tidak dapat dimuat'
                    ) : (
                      <>
                        Belum ada rute
                        {canWriteRoutes && (
                          <>
                            {' '}
                            — <Link to="/delivery-routes/new">tambah rute pengiriman</Link>
                          </>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              ) : (
                routes.map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600 }}>{r.route_no}</td>
                    <td>{formatRouteDate(r.date)}</td>
                    <td>{r.vehicle_type_name || '-'}</td>
                    <td>
                      <span className="badge badge-blue" style={{ fontWeight: 600 }}>Rit {r.ritase || 1}</span>
                    </td>
                    <td>
                      {r.stops.length} customer
                      {r.stops.some((s) => s.items?.length) && (
                        <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          {r.stops.reduce((sum, s) => sum + (s.items?.length || 0), 0)} barang
                        </span>
                      )}
                    </td>
                    <td>
                      {r.sale_no ? (
                        <span style={{ display: 'inline-flex', flexDirection: 'column', gap: '0.15rem' }}>
                          {canGenerateSale ? (
                            <button
                              type="button"
                              className="btn-link-sale"
                              onClick={() => navigate('/sales')}
                              title="Buka halaman Uang Jalan"
                            >
                              {r.sale_no}
                            </button>
                          ) : (
                            <span style={{ color: 'var(--success-color)' }}>{r.sale_no}</span>
                          )}
                          {(r.sale_vehicle_plate || r.sale_driver_name) && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.35 }}>
                              {r.sale_vehicle_plate && (
                                <span style={{ display: 'block' }}>Kendaraan: {r.sale_vehicle_plate}</span>
                              )}
                              {r.sale_driver_name && (
                                <span style={{ display: 'block' }}>Sopir: {r.sale_driver_name}</span>
                              )}
                            </span>
                          )}
                          {r.is_finance_paid && (
                            <span className="badge-finance-paid" title="Uang jalan sudah disetujui dibayar">
                              Dibayar Finance
                            </span>
                          )}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)' }}>Belum dibuat</span>
                      )}
                    </td>
                    {showRouteActions && (
                    <td style={{ textAlign: 'right' }}>
                      <div
                        style={{
                          display: 'inline-flex',
                          gap: '0.35rem',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          flexWrap: 'nowrap',
                        }}
                      >
                        {canGenerateSale && (
                        <button
                          type="button"
                          className={`btn btn-secondary${r.is_finance_paid ? ' btn-sync-disabled' : ''}`}
                          style={{
                            padding: '0.4rem 0.6rem',
                            fontSize: '0.8rem',
                            whiteSpace: 'nowrap',
                          }}
                          disabled={
                            generatingId === r.id || !canGenerateSale || Boolean(r.is_finance_paid)
                          }
                          title={
                            !canGenerateSale
                              ? 'Tidak ada izin membuat uang jalan'
                              : r.is_finance_paid
                                ? 'Rute dikunci — uang jalan sudah disetujui dibayar Finance.'
                                : r.sale_id
                                  ? 'Perbarui transaksi uang jalan dari perubahan rute'
                                  : 'Buat transaksi uang jalan dari rute'
                          }
                          onClick={() => handleGenerateSale(r.id, Boolean(r.sale_id))}
                        >
                          <Wallet size={14} /> {r.sale_id ? 'Sync' : 'Uang Jalan'}
                        </button>
                        )}
                        {canWriteRoutes && (
                        <div style={{ display: 'inline-flex', gap: '0.35rem', flexShrink: 0 }}>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.4rem 0.6rem' }}
                            disabled={Boolean(r.is_finance_paid)}
                            title={
                              r.is_finance_paid
                                ? 'Rute dikunci — sudah disetujui dibayar Finance'
                                : 'Edit rute'
                            }
                            onClick={() => handleEdit(r)}
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger"
                            style={{ padding: '0.4rem 0.6rem' }}
                            disabled={Boolean(r.is_finance_paid)}
                            title={
                              r.is_finance_paid
                                ? 'Rute dikunci — sudah disetujui dibayar Finance'
                                : 'Hapus rute'
                            }
                            onClick={() => handleDelete(r)}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                        )}
                      </div>
                    </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
};

export default DeliveryRoutesList;
