import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Plus,
  Trash2,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  Maximize,
  AlertCircle,
  ArrowLeft,
} from 'lucide-react';
import GlassCard from '../components/GlassCard';
import CustomerSearchSelect from '../components/CustomerSearchSelect';
import { apiFetch } from '../api';
import { useCrudWrite } from '../components/CrudWriteAccess';
import MultiPointMap from '../components/MultiPointMap';
import { hasMapCoords } from '../utils/mapIcons';
import {
  defaultRouteForm,
  emptyStop,
  emptyLine,
  mapStopFromApi,
  buildStopItemsPayload,
} from '../utils/deliveryRouteUtils';
import {
  ROUTE_FEE_DEFS,
  getRouteFeeAmount,
  getUangPelabuhanAmount,
  routeFeeFieldsFromApi,
  routeFeePayloadFromForm,
} from '../utils/routeFeeConfig';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const PELABUHAN_TOGGLE = {
  key: 'uang_pelabuhan',
  label: 'Uang Pelabuhan',
  includeKey: 'include_uang_pelabuhan',
  getAmount: (vehicleTypeId, vehicleTypes, _feeMasters, pelabuhanMasters) =>
    getUangPelabuhanAmount(vehicleTypeId, vehicleTypes, pelabuhanMasters),
};

const DeliveryRouteForm = () => {
  const navigate = useNavigate();
  const canWrite = useCrudWrite();
  const { routeId } = useParams();
  const isEdit = Boolean(routeId);
  const editId = isEdit ? parseInt(routeId, 10) : null;

  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [feeMasters, setFeeMasters] = useState({});
  const [pelabuhanMasters, setPelabuhanMasters] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [warehouse, setWarehouse] = useState(null);
  const [warehouseLoadError, setWarehouseLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [routesError, setRoutesError] = useState(null);
  const [customersError, setCustomersError] = useState(null);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
  const [routeDistance, setRouteDistance] = useState(0);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(defaultRouteForm());
  const soInputRefs = useRef([]);

  const focusSoInput = (idx) => {
    requestAnimationFrame(() => soInputRefs.current[idx]?.focus());
  };

  const loadFormData = async () => {
    if (!canWrite) {
      navigate('/delivery-routes', { replace: true });
      return;
    }
    setLoading(true);
    setCustomersError(null);
    setRoutesError(null);

    try {
      const dataC = await apiFetch('/api/customers');
      setCustomers(Array.isArray(dataC) ? dataC : []);
    } catch (err) {
      setCustomers([]);
      setCustomersError(err.message || 'Gagal memuat daftar customer.');
    }

    try {
      const dataVt = await apiFetch('/api/vehicle-types');
      setVehicleTypes(Array.isArray(dataVt) ? dataVt : []);
    } catch (err) {
      setVehicleTypes([]);
      setRoutesError(err.message || 'Gagal memuat jenis kendaraan.');
    }

    try {
      const masterEntries = await Promise.all(
        ROUTE_FEE_DEFS.map(async (fee) => {
          const data = await apiFetch(`/api/route-fees/${fee.apiPath}`);
          return [fee.key, Array.isArray(data) ? data : []];
        })
      );
      setFeeMasters(Object.fromEntries(masterEntries));
    } catch {
      setFeeMasters({});
    }

    try {
      const dataPelabuhan = await apiFetch('/api/uang-pelabuhan');
      setPelabuhanMasters(Array.isArray(dataPelabuhan) ? dataPelabuhan : []);
    } catch {
      setPelabuhanMasters([]);
    }

    try {
      let dataW = await apiFetch('/api/warehouse');
      if (
        !hasMapCoords(dataW.latitude, dataW.longitude) &&
        (dataW.address?.trim() || dataW.city?.trim())
      ) {
        try {
          dataW = await apiFetch('/api/warehouse/geocode', { method: 'POST' });
        } catch {
          // Tetap tampilkan data gudang meski geocode gagal
        }
      }
      setWarehouse(dataW);
      setWarehouseLoadError(null);
    } catch (err) {
      setWarehouse(null);
      setWarehouseLoadError(err.message || 'Gagal memuat data gudang.');
    }

    if (isEdit && editId) {
      try {
        const route = await apiFetch(`/api/delivery-routes/${editId}`);
        if (route.is_finance_paid) {
          alert('Rute dikunci karena uang jalan sudah disetujui dibayar oleh Finance.');
          navigate('/delivery-routes');
          return;
        }
        setForm({
          route_no: route.route_no,
          date: route.date,
          vehicle_type_id: String(route.vehicle_type_id),
          ritase: String(route.ritase || 1),
          remarks: route.remarks || '',
          ...routeFeeFieldsFromApi(route),
          stops: route.stops.length
            ? route.stops.sort((a, b) => a.sort_order - b.sort_order).map(mapStopFromApi)
            : [emptyStop()],
        });
      } catch (err) {
        setRoutesError(err.message || 'Rute tidak ditemukan.');
      }
    } else {
      setForm(defaultRouteForm());
    }

    setLoading(false);
  };

  useEffect(() => {
    loadFormData();
  }, [routeId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.date || !form.vehicle_type_id) {
      alert('Isi tanggal dan jenis kendaraan.');
      return;
    }
    let stopsPayload;
    try {
      stopsPayload = form.stops
        .filter((s) => s.customer_id)
        .map((s) => {
          const items = buildStopItemsPayload(s.items);
          if (items.length === 0) {
            throw new Error('Setiap customer wajib memiliki minimal 1 barang dengan quantity.');
          }
          return {
            customer_id: parseInt(s.customer_id, 10),
            description: s.description?.trim() || null,
            entity_code: s.entity_code?.trim() || null,
            items,
          };
        });
    } catch (err) {
      alert(err.message);
      return;
    }
    if (stopsPayload.length === 0) {
      alert('Minimal 1 customer pada rute.');
      return;
    }

    const seenStops = new Set();
    for (const stop of stopsPayload) {
      const key = `${stop.customer_id}|${(stop.description || '').trim().toLowerCase()}`;
      if (seenStops.has(key)) {
        alert('Customer dengan nomor SO yang sama tidak boleh duplikat pada rute.');
        return;
      }
      seenStops.add(key);
    }

    const payload = {
      route_no: form.route_no || null,
      date: form.date,
      vehicle_type_id: parseInt(form.vehicle_type_id, 10),
      ritase: parseInt(form.ritase, 10) || 1,
      remarks: form.remarks || null,
      ...routeFeePayloadFromForm(form),
      stops: stopsPayload,
    };

    setSaving(true);
    try {
      if (isEdit) {
        await apiFetch(`/api/delivery-routes/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch('/api/delivery-routes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      navigate('/delivery-routes');
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const updateStop = (idx, patch) => {
    const stops = [...form.stops];
    stops[idx] = { ...stops[idx], ...patch };
    setForm({ ...form, stops });
  };

  const addStop = () => setForm({ ...form, stops: [...form.stops, emptyStop()] });

  const removeStop = (idx) => {
    const stops = [...form.stops];
    stops.splice(idx, 1);
    setForm({ ...form, stops: stops.length ? stops : [emptyStop()] });
  };

  const moveStop = (idx, dir) => {
    const stops = [...form.stops];
    const next = idx + dir;
    if (next < 0 || next >= stops.length) return;
    [stops[idx], stops[next]] = [stops[next], stops[idx]];
    setForm({ ...form, stops });
  };

  const updateStopLine = (stopIdx, lineIdx, patch) => {
    const stops = [...form.stops];
    const items = [...(stops[stopIdx].items || [])];
    items[lineIdx] = { ...items[lineIdx], ...patch };
    stops[stopIdx] = { ...stops[stopIdx], items };
    setForm({ ...form, stops });
  };

  const addStopLine = (stopIdx) => {
    const stops = [...form.stops];
    stops[stopIdx] = {
      ...stops[stopIdx],
      items: [...(stops[stopIdx].items || []), emptyLine()],
    };
    setForm({ ...form, stops });
  };

  const removeStopLine = (stopIdx, lineIdx) => {
    const stops = [...form.stops];
    const items = [...(stops[stopIdx].items || [])];
    items.splice(lineIdx, 1);
    stops[stopIdx] = { ...stops[stopIdx], items: items.length ? items : [emptyLine()] };
    setForm({ ...form, stops });
  };

  const hasValidCoords = hasMapCoords;

  const mapPoints = () => {
    const stopPoints = form.stops
      .map((s, idx) => {
        const cust = customers.find((c) => String(c.id) === String(s.customer_id));
        if (!cust || !hasValidCoords(cust.latitude, cust.longitude)) return null;
        return {
          name: cust.name,
          latitude: Number(cust.latitude),
          longitude: Number(cust.longitude),
          isWarehouse: false,
          label: `Stop ${idx + 1}`,
        };
      })
      .filter(Boolean);

    const pts = [...stopPoints];
    if (warehouse && hasValidCoords(warehouse.latitude, warehouse.longitude)) {
      pts.unshift({
        name: warehouse.name || 'Gudang',
        latitude: Number(warehouse.latitude),
        longitude: Number(warehouse.longitude),
        isWarehouse: true,
        label: 'Gudang',
      });
    }
    return pts;
  };

  const points = mapPoints();
  const warehouseOnMap = points.some((p) => p.isWarehouse);
  const warehouseCoordsMissing =
    warehouse && !hasValidCoords(warehouse.latitude, warehouse.longitude);
  const pelabuhanAmount = PELABUHAN_TOGGLE.getAmount(
    form.vehicle_type_id,
    vehicleTypes,
    feeMasters,
    pelabuhanMasters
  );
  const canUsePelabuhan = Boolean(form.vehicle_type_id) && pelabuhanAmount > 0;

  const getRouteFeeAmountForForm = (feeKey) =>
    getRouteFeeAmount(feeKey, form.vehicle_type_id, vehicleTypes, feeMasters);

  const handleVehicleTypeChange = (vehicleTypeId) => {
    const nextPelabuhanAmount = PELABUHAN_TOGGLE.getAmount(
      vehicleTypeId,
      vehicleTypes,
      feeMasters,
      pelabuhanMasters
    );
    setForm((prev) => {
      const next = {
        ...prev,
        vehicle_type_id: vehicleTypeId,
        include_uang_pelabuhan: prev.include_uang_pelabuhan && nextPelabuhanAmount > 0,
      };
      for (const fee of ROUTE_FEE_DEFS) {
        const amount = getRouteFeeAmount(fee.key, vehicleTypeId, vehicleTypes, feeMasters);
        next[`include_${fee.key}`] = amount > 0;
      }
      return next;
    });
  };

  const handlePelabuhanToggle = (checked) => {
    setForm((prev) => ({ ...prev, include_uang_pelabuhan: checked }));
  };

  const handleRouteFeeToggle = (includeKey, checked) => {
    setForm((prev) => ({ ...prev, [includeKey]: checked }));
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">{isEdit ? 'Edit Rute Pengiriman' : 'Input Rute Pengiriman'}</h1>
          <p className="page-subtitle">
            Rute per tanggal dan jenis kendaraan. Sopir ditentukan gudang saat uang jalan dibuat.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Link to="/delivery-routes" className="btn btn-secondary" style={{ textDecoration: 'none' }}>
            <ArrowLeft size={18} /> Kembali ke Daftar
          </Link>
          <button className="btn btn-secondary" onClick={loadFormData} disabled={loading || saving}>
            <RefreshCw size={18} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {(routesError || customersError) && (
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
          <div>
            {customersError && <div>{customersError}</div>}
            {routesError && <div>{routesError}</div>}
          </div>
        </div>
      )}

      <GlassCard title={isEdit ? 'Edit Rute' : 'Form Rute Baru'}>
        {loading ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>Memuat form...</p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '1rem',
                marginBottom: '1rem',
              }}
            >
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Tanggal *</label>
                <input
                  type="date"
                  className="form-input"
                  required
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">No Rute</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Otomatis jika kosong"
                  value={form.route_no}
                  onChange={(e) => setForm({ ...form, route_no: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Jenis Kendaraan *</label>
                <select
                  className="form-input"
                  required
                  value={form.vehicle_type_id}
                  onChange={(e) => handleVehicleTypeChange(e.target.value)}
                >
                  <option value="">-- Pilih jenis kendaraan --</option>
                  {vehicleTypes.map((vt) => (
                    <option key={vt.id} value={vt.id}>
                      {vt.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Ritase</label>
                <select
                  className="form-input"
                  value={form.ritase}
                  onChange={(e) => setForm({ ...form, ritase: e.target.value })}
                >
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <option key={n} value={n}>
                      Rit {n}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 360px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, fontSize: '0.95rem' }}>Urutan pengiriman (customer)</h4>
                  <button type="button" className="btn btn-secondary" onClick={addStop} style={{ fontSize: '0.85rem' }}>
                    <Plus size={16} /> Customer
                  </button>
                </div>
                <table className="glass-table" style={{ fontSize: '0.9rem' }}>
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>#</th>
                      <th>Customer</th>
                      <th>Nomor SO</th>
                      <th>Kode Entity</th>
                      <th style={{ width: '110px' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {form.stops.map((row, idx) => (
                      <React.Fragment key={idx}>
                        <tr className="route-stop-header-row">
                          <td rowSpan={2} style={{ verticalAlign: 'top' }}>
                            {idx + 1}
                          </td>
                          <td>
                            <CustomerSearchSelect
                              customers={customers}
                              value={row.customer_id}
                              onChange={(customerId) => updateStop(idx, { customer_id: customerId })}
                              onAfterSelect={() => focusSoInput(idx)}
                              disabled={customers.length === 0}
                              codeOnly
                              showNameBelow
                              compact
                            />
                          </td>
                          <td>
                            <input
                              ref={(el) => {
                                soInputRefs.current[idx] = el;
                              }}
                              type="text"
                              className="form-input"
                              placeholder="Nomor SO"
                              style={{ padding: '0.35rem 0.5rem', width: '100%' }}
                              value={row.description || ''}
                              onChange={(e) => updateStop(idx, { description: e.target.value })}
                            />
                          </td>
                          <td>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="Kode Entity"
                              style={{ padding: '0.35rem 0.5rem', width: '100%' }}
                              value={row.entity_code || ''}
                              onChange={(e) => updateStop(idx, { entity_code: e.target.value })}
                            />
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '0.25rem' }}>
                              <button
                                type="button"
                                className="btn btn-secondary"
                                style={{ padding: '0.25rem' }}
                                disabled={idx === 0}
                                onClick={() => moveStop(idx, -1)}
                              >
                                <ChevronUp size={16} />
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary"
                                style={{ padding: '0.25rem' }}
                                disabled={idx === form.stops.length - 1}
                                onClick={() => moveStop(idx, 1)}
                              >
                                <ChevronDown size={16} />
                              </button>
                              {form.stops.length > 1 && (
                                <button
                                  type="button"
                                  className="btn btn-danger"
                                  style={{ padding: '0.25rem' }}
                                  onClick={() => removeStop(idx)}
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                        <tr className="route-stop-lines-row">
                          <td colSpan={4}>
                            <div className="route-stop-lines">
                              <div className="route-stop-lines-header">
                                <span>Barang yang dikirim</span>
                                <button
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                                  onClick={() => addStopLine(idx)}
                                >
                                  <Plus size={14} /> Barang
                                </button>
                              </div>
                              <table className="route-stop-lines-table">
                                <thead>
                                  <tr>
                                    <th>Nama Barang</th>
                                    <th style={{ width: '120px' }}>Qty</th>
                                    <th style={{ width: '40px' }}></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(row.items || [emptyLine()]).map((line, lineIdx) => (
                                    <tr key={lineIdx}>
                                      <td>
                                        <input
                                          type="text"
                                          className="form-input"
                                          placeholder="Nama barang"
                                          style={{ padding: '0.35rem 0.5rem', width: '100%' }}
                                          value={line.item_name || ''}
                                          onChange={(e) =>
                                            updateStopLine(idx, lineIdx, { item_name: e.target.value })
                                          }
                                        />
                                      </td>
                                      <td>
                                        <input
                                          type="number"
                                          className="form-input"
                                          min="0.001"
                                          step="any"
                                          placeholder="Qty"
                                          style={{ padding: '0.35rem 0.5rem', width: '100%' }}
                                          value={line.quantity ?? ''}
                                          onChange={(e) =>
                                            updateStopLine(idx, lineIdx, { quantity: e.target.value })
                                          }
                                        />
                                      </td>
                                      <td>
                                        {(row.items || []).length > 1 && (
                                          <button
                                            type="button"
                                            className="btn btn-danger"
                                            style={{ padding: '0.25rem' }}
                                            onClick={() => removeStopLine(idx, lineIdx)}
                                          >
                                            <Trash2 size={14} />
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {points.length > 0 && (
                <div
                  style={{
                    flex: '1 1 280px',
                    position: 'relative',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    minHeight: '240px',
                  }}
                >
                  <MultiPointMap points={points} height={240} onRouteCalculated={setRouteDistance} />
                  <div
                    style={{
                      position: 'absolute',
                      bottom: 10,
                      left: 10,
                      zIndex: 10,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.25rem',
                      fontSize: '0.75rem',
                      background: 'rgba(255,255,255,0.92)',
                      padding: '0.35rem 0.5rem',
                      borderRadius: 6,
                      border: '1px solid #e2e8f0',
                    }}
                  >
                    {warehouseOnMap && (
                      <span>
                        <span className="map-legend-dot map-legend-dot-warehouse" /> Gudang (asal)
                      </span>
                    )}
                    <span>
                      <span className="map-legend-dot map-legend-dot-customer" /> Customer (stop)
                    </span>
                    {routeDistance > 0 && (
                      <span style={{ marginTop: '4px', fontWeight: 600, color: '#1e40af' }}>
                        Jarak Tempuh: {routeDistance.toLocaleString('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsMapFullscreen(true)}
                    style={{
                      position: 'absolute',
                      top: 10,
                      right: 10,
                      zIndex: 10,
                      background: 'white',
                      border: '1px solid #ccc',
                      borderRadius: 4,
                      padding: '4px 8px',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Maximize size={14} /> Perbesar
                  </button>
                </div>
              )}
            </div>

            {warehouseLoadError && (
              <p
                style={{
                  margin: '0.75rem 0 0',
                  fontSize: '0.85rem',
                  color: '#991b1b',
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: 8,
                  padding: '0.5rem 0.75rem',
                }}
              >
                Tidak dapat memuat titik gudang: {warehouseLoadError}
              </p>
            )}

            {warehouseCoordsMissing && !warehouseLoadError && (
              <p
                style={{
                  margin: '0.75rem 0 0',
                  fontSize: '0.85rem',
                  color: '#92400e',
                  background: '#fffbeb',
                  border: '1px solid #fde68a',
                  borderRadius: 8,
                  padding: '0.5rem 0.75rem',
                }}
              >
                Titik gudang belum diatur —{' '}
                <Link to="/warehouse" style={{ color: '#4f46e5' }}>
                  atur koordinat gudang
                </Link>{' '}
                agar muncul sebagai titik asal di peta.
              </p>
            )}

            <div
              style={{
                display: 'flex',
                gap: '1rem',
                marginTop: '1.25rem',
                flexWrap: 'wrap',
                alignItems: 'flex-end',
              }}
            >
              <div className="form-group" style={{ marginBottom: 0, flex: '1 1 280px', minWidth: '200px' }}>
                <label className="form-label">Keterangan</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Catatan untuk rute ini"
                  value={form.remarks}
                  onChange={(e) => setForm({ ...form, remarks: e.target.value })}
                />
              </div>
              <div style={{ flex: '1 1 100%', marginTop: '0.5rem' }}>
                <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem' }}>Biaya Rute</h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                    gap: '1rem',
                  }}
                >
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label
                      className="form-label"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        cursor: canUsePelabuhan ? 'pointer' : 'not-allowed',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={Boolean(form.include_uang_pelabuhan)}
                        disabled={!canUsePelabuhan}
                        onChange={(e) => handlePelabuhanToggle(e.target.checked)}
                      />
                      <span>{PELABUHAN_TOGGLE.label}</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      readOnly
                      value={form.include_uang_pelabuhan && pelabuhanAmount > 0 ? formatIDR(pelabuhanAmount) : '-'}
                      style={{ textAlign: 'right', background: '#f8fafc' }}
                    />
                  </div>
                  {ROUTE_FEE_DEFS.map((fee) => {
                    const includeKey = `include_${fee.key}`;
                    const amount = getRouteFeeAmountForForm(fee.key);
                    const canUse = Boolean(form.vehicle_type_id) && amount > 0;
                    return (
                      <div key={fee.key} className="form-group" style={{ marginBottom: 0 }}>
                        <label
                          className="form-label"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            cursor: canUse ? 'pointer' : 'not-allowed',
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={Boolean(form[includeKey])}
                            disabled={!canUse}
                            onChange={(e) => handleRouteFeeToggle(includeKey, e.target.checked)}
                          />
                          <span>{fee.label}</span>
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          readOnly
                          value={form[includeKey] && amount > 0 ? formatIDR(amount) : '-'}
                          style={{ textAlign: 'right', background: '#f8fafc' }}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', width: '100%' }}>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Menyimpan...' : isEdit ? 'Simpan Perubahan' : 'Simpan Rute'}
                </button>
                <Link to="/delivery-routes" className="btn btn-secondary" style={{ textDecoration: 'none' }}>
                  Batal
                </Link>
              </div>
            </div>
          </form>
        )}
      </GlassCard>

      {isMapFullscreen && (
        <div className="modal-overlay" onClick={() => setIsMapFullscreen(false)}>
          <div
            className="modal-content"
            style={{ maxWidth: '95vw', width: '900px', padding: '1rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <MultiPointMap points={points} height="70vh" onRouteCalculated={setRouteDistance} />
            {routeDistance > 0 && (
              <div style={{ marginTop: '0.5rem', textAlign: 'center', fontWeight: 'bold', color: '#1e40af' }}>
                Total Jarak Tempuh Rute: {routeDistance.toLocaleString('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DeliveryRouteForm;
