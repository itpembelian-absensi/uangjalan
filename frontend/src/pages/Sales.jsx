import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Trash2,
  Edit,
  Plus,
  AlertCircle,
  RefreshCw,
  X,
  Printer,
  FileDown,
  FileSpreadsheet,
  MapPin,
  Maximize,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  CheckCircle2,
  Lock,
  Undo2,
  ChevronDown,
  ChevronRight,
  Ban,
} from 'lucide-react';
import { apiFetch } from '../api';
import { useAuth } from '../auth/AuthContext';
import { tomorrowIso } from '../utils/deliveryRouteUtils';
import {
  buildSaleDocument,
  buildSaleDocumentFromSaleOut,
  printSaleDocument,
  exportSalePdf,
  exportSaleExcel,
  computeUangJalanTotals,
  printBulkSales,
  exportBulkSalesPdf,
  exportBulkSalesExcel,
} from '../utils/saleExport';
import {
  sumRouteFees,
  getActiveRouteFeeLines,
  defaultRouteFeeFormFields,
  routeFeeAmountsFromApi,
} from '../utils/routeFeeConfig';
import RouteResultModal from '../components/RouteResultModal';
import MultiPointMap from '../components/MultiPointMap';
import RouteKmBreakdown from '../components/RouteKmBreakdown';
import { EMPTY_ROUTE_KM, calcBbmAmount } from '../utils/routeKm';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const formatAmount = (num) =>
  new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(num) || 0);

const RouteFeeBreakdown = ({ lines, style }) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: '1fr auto 4.25rem',
      columnGap: '0.35rem',
      rowGap: '0.15rem',
      fontVariantNumeric: 'tabular-nums',
      ...style,
    }}
  >
    {lines.map((line) => (
      <React.Fragment key={line.label}>
        <span>{line.label}</span>
        <span>Rp</span>
        <span style={{ textAlign: 'right' }}>{formatAmount(line.amount)}</span>
      </React.Fragment>
    ))}
  </div>
);

const parseAmountInput = (val) => {
  if (val === '' || val == null) return '';
  const cleaned = String(val).replace(/[^\d]/g, '');
  return cleaned === '' ? '' : cleaned;
};

const amountToNumber = (val) => {
  if (val === '' || val == null) return 0;
  const n = parseFloat(parseAmountInput(val));
  return Number.isNaN(n) ? 0 : n;
};

const formatDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

const tariffTotal = (row) =>
  (parseFloat(row?.uang_jalan) || 0) + (parseFloat(row?.tambahan_uang_jalan) || 0);

const masterTariffAmount = (t) => {
  if (!t) return 0;
  const component =
    (parseFloat(t.bbm) || 0) +
    (parseFloat(t.tol) || 0) +
    (parseFloat(t.uang_mel) || 0) +
    (parseFloat(t.parkir) || 0) +
    (parseFloat(t.lain_lain) || 0);
  const stored = parseFloat(t.uang_jalan) || 0;
  if (stored > 0 && stored > component) return stored;
  if (component > 0) return component;
  return stored;
};

const getMaxNominal = (details) => {
  const filled = details.filter((d) => d.customer_id);
  const amounts = filled
    .map((d) => parseFloat(d.amount))
    .filter((n) => !Number.isNaN(n));
  return {
    customerCount: filled.length,
    maxNominal: amounts.length > 0 ? Math.max(...amounts) : 0,
  };
};

const saleDetailTotal = (sale) => {
  const amounts = (sale.details || []).map((d) => parseFloat(d.amount) || 0).filter((n) => n > 0);
  const maxNom = amounts.length > 0 ? Math.max(...amounts) : 0;
  const extraAmt = parseFloat(sale.extra_uang_jalan) || 0;
  const routeFeesAmt = sumRouteFees(sale);
  const multi = (sale.details || []).length > 1;
  const baseUJ = multi ? maxNom : (amounts[0] || 0);
  const { total } = computeUangJalanTotals(baseUJ, extraAmt, routeFeesAmt);
  return total;
};

const compareSales = (a, b, key, dir) => {
  const sign = dir === 'asc' ? 1 : -1;
  const nullsLast = (x, y, cmp) => {
    const xEmpty = x == null || x === '';
    const yEmpty = y == null || y === '';
    if (xEmpty && yEmpty) return 0;
    if (xEmpty) return 1;
    if (yEmpty) return -1;
    return sign * cmp(x, y);
  };

  switch (key) {
    case 'sale_no':
      return nullsLast(a.sale_no, b.sale_no, (x, y) =>
        String(x).localeCompare(String(y), 'id', { numeric: true, sensitivity: 'base' }),
      );
    case 'route_no':
      return nullsLast(a.route_no, b.route_no, (x, y) =>
        String(x).localeCompare(String(y), 'id', { numeric: true, sensitivity: 'base' }),
      );
    case 'date': {
      const ad = a.date ? String(a.date) : '';
      const bd = b.date ? String(b.date) : '';
      if (!ad && !bd) return 0;
      if (!ad) return 1;
      if (!bd) return -1;
      return sign * ad.localeCompare(bd);
    }
    case 'vehicle_plate':
      return nullsLast(a.vehicle_plate, b.vehicle_plate, (x, y) =>
        String(x).localeCompare(String(y), 'id', { numeric: true, sensitivity: 'base' }),
      );
    case 'driver_name':
      return nullsLast(a.driver_name, b.driver_name, (x, y) =>
        String(x).localeCompare(String(y), 'id', { sensitivity: 'base' }),
      );
    case 'customer_count': {
      const diff = (a.details?.length || 0) - (b.details?.length || 0);
      return sign * (diff > 0 ? 1 : diff < 0 ? -1 : 0);
    }
    case 'total': {
      const diff = saleDetailTotal(a) - saleDetailTotal(b);
      return sign * (diff > 0 ? 1 : diff < 0 ? -1 : 0);
    }
    default:
      return 0;
  }
};

const SortableTh = ({ label, column, sortKey, sortDir, onSort, align }) => (
  <th style={align ? { textAlign: align } : undefined} className="th-sortable">
    <button
      type="button"
      className="th-sort-btn"
      style={align === 'right' ? { justifyContent: 'flex-end' } : undefined}
      onClick={() => onSort(column)}
    >
      <span>{label}</span>
      {sortKey === column ? (
        sortDir === 'asc' ? <ArrowUp size={14} aria-hidden /> : <ArrowDown size={14} aria-hidden />
      ) : (
        <ArrowUpDown size={14} style={{ opacity: 0.4 }} aria-hidden />
      )}
    </button>
  </th>
);

const emptyDetail = () => ({
  customer_id: '',
  vehicle_type_id: '',
  vehicle_type_name: '',
  amount: '',
});

const Sales = () => {
  const { user, hasPermission, canWritePage } = useAuth();
  const canWrite = canWritePage('/sales');
  const canApprovePayment =
    hasPermission('sales:write') && (user?.role === 'finance' || user?.role === 'admin');

  const [sales, setSales] = useState([]);
  const [financeActionId, setFinanceActionId] = useState(null);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [warehouse, setWarehouse] = useState(null);
  const [vehicleTypes, setVehicleTypes] = useState([]);

  const [filterFrom, setFilterFrom] = useState(tomorrowIso);
  const [filterTo, setFilterTo] = useState(tomorrowIso);
  const [filterSaleNo, setFilterSaleNo] = useState('');

  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const handlePopState = () => {
      if (isModalOpen) {
        setIsModalOpen(false);
        setLinkedRouteId(null);
        setLinkedRouteNo('');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isModalOpen]);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
  const [routeKm, setRouteKm] = useState(EMPTY_ROUTE_KM);
  const handleRouteCalculated = useCallback((summary) => {
    setRouteKm(summary || EMPTY_ROUTE_KM);
  }, []);
  const [isEdit, setIsEdit] = useState(false);
  const [currentId, setCurrentId] = useState(null);
  const [linkedRouteId, setLinkedRouteId] = useState(null);
  const [linkedRouteNo, setLinkedRouteNo] = useState('');

  const [form, setForm] = useState({
    sale_no: '',
    date: new Date().toISOString().split('T')[0],
    vehicle_id: '',
    driver_id: '',
    remarks: '',
    extra_uang_jalan: '',
    ...defaultRouteFeeFormFields(),
    details: [],
  });

  const appliedBbmKeyRef = useRef('');
  const sequentialBbm = useMemo(() => {
    const filled = form.details.filter((d) => d.customer_id && d.vehicle_type_id);
    if (filled.length < 2 || !(routeKm.totalKm > 0)) return null;
    const vt = vehicleTypes.find((t) => String(t.id) === String(filled[0].vehicle_type_id));
    return calcBbmAmount(routeKm.totalKm, vt);
  }, [form.details, vehicleTypes, routeKm.totalKm]);
  const detailIdentity = form.details.map((d) => `${d.customer_id}:${d.vehicle_type_id}`).join(',');

  useEffect(() => {
    if (!isModalOpen) {
      appliedBbmKeyRef.current = '';
    }
  }, [isModalOpen]);

  useEffect(() => {
    if (!isModalOpen || form.is_finance_paid || sequentialBbm == null) return;
    const key = `${detailIdentity}|${sequentialBbm}|${routeKm.totalKm.toFixed(2)}`;
    if (appliedBbmKeyRef.current === key) return;
    appliedBbmKeyRef.current = key;
    setForm((prev) => ({
      ...prev,
      details: prev.details.map((d) => {
        const customer = customers.find((c) => String(c.id) === String(d.customer_id));
        const tariff = (customer?.tariffs || []).find(
          (t) => String(t.vehicle_type_id) === String(d.vehicle_type_id)
        );
        const tariffBbm = Number(tariff?.bbm) || 0;
        if (!(tariffBbm > 0)) return d;
        const other = Math.max(0, masterTariffAmount(tariff) - tariffBbm);
        return { ...d, amount: other + sequentialBbm };
      }),
    }));
  }, [
    isModalOpen,
    form.is_finance_paid,
    sequentialBbm,
    detailIdentity,
    routeKm.totalKm,
    customers,
  ]);

  const [saving, setSaving] = useState(false);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [routeResult, setRouteResult] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);

  const [voidModal, setVoidModal] = useState({ open: false, saleId: null, reason: '' });

  const fetchSales = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterFrom) params.append('from', filterFrom);
      if (filterTo) params.append('to', filterTo);
      if (filterSaleNo) params.append('sale_no', filterSaleNo);
      
      const dataS = await apiFetch(`/api/sales?${params.toString()}`);
      setSales(dataS);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Gagal memuat data uang jalan.');
    } finally {
      setLoading(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterFrom) params.append('from', filterFrom);
      if (filterTo) params.append('to', filterTo);
      if (filterSaleNo) params.append('sale_no', filterSaleNo);

      const [dataS, dataV, dataD, dataC, dataW, dataVt] = await Promise.all([
        apiFetch(`/api/sales?${params.toString()}`),
        apiFetch('/api/vehicles'),
        apiFetch('/api/drivers'),
        apiFetch('/api/customers'),
        apiFetch('/api/warehouse'),
        apiFetch('/api/vehicle-types'),
      ]);

      setSales(dataS);
      setVehicles(dataV);
      setDrivers(dataD);
      setCustomers(dataC);
      setWarehouse(dataW);
      setVehicleTypes(Array.isArray(dataVt) ? dataVt : []);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Koneksi database gagal.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const initialLoadDone = React.useRef(false);
  useEffect(() => {
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      return;
    }
    fetchSales();
  }, [filterFrom, filterTo]);

  const getActiveTariffs = (customerId) => {
    const customer = customers.find((c) => String(c.id) === String(customerId));
    return (customer?.tariffs || []).filter((t) => tariffTotal(t) > 0);
  };

  const inferVehicleTypeId = (customerId, amount) => {
    const customer = customers.find((c) => String(c.id) === String(customerId));
    if (!customer || amount === '' || amount == null) return '';
    const target = parseFloat(amount);
    if (Number.isNaN(target)) return '';
    const matches = (customer.tariffs || []).filter((t) => tariffTotal(t) === target);
    return matches.length === 1 ? String(matches[0].vehicle_type_id) : '';
  };

  const getTariffOptions = (row) => {
    const active = getActiveTariffs(row.customer_id);
    const savedId = row.vehicle_type_id ? String(row.vehicle_type_id) : '';
    if (!savedId) return active;
    if (active.some((t) => String(t.vehicle_type_id) === savedId)) return active;
    return [
      ...active,
      {
        vehicle_type_id: savedId,
        vehicle_type_name: row.vehicle_type_name || `Jenis #${savedId}`,
        uang_jalan: row.amount || 0,
      },
    ];
  };

  const lookupTariffAmount = (customerId, vehicleTypeId) => {
    const customer = customers.find((c) => String(c.id) === String(customerId));
    if (!customer || !vehicleTypeId) return '';
    const tariff = (customer.tariffs || []).find(
      (t) => String(t.vehicle_type_id) === String(vehicleTypeId)
    );
    return tariff && tariffTotal(tariff) > 0 ? String(tariffTotal(tariff)) : '';
  };

  const closeModal = () => {
    if (saving) return;
    if (window.location.hash === '#modal') {
      window.history.back();
    } else {
      setIsModalOpen(false);
      setLinkedRouteId(null);
      setLinkedRouteNo('');
    }
  };

  const fromRoute = Boolean(linkedRouteId);

  const routeVehicleTypeId =
    fromRoute && form.details[0]?.vehicle_type_id ? String(form.details[0].vehicle_type_id) : '';

  const vehicleOptions =
    fromRoute && routeVehicleTypeId
      ? vehicles.filter((v) => String(v.type_id) === routeVehicleTypeId)
      : vehicles;

  const handleApprovePayment = async (sale) => {
    if (sale.is_finance_paid) return;
    const msg = `Setujui pembayaran uang jalan ${sale.sale_no}? Rute terkait akan dikunci dan tidak dapat diubah lagi.`;
    if (!window.confirm(msg)) return;
    setFinanceActionId(sale.id);
    try {
      const updated = await apiFetch(`/api/sales/${sale.id}/finance-approve`, { method: 'POST' });
      setSales((prev) => prev.map((s) => (s.id === sale.id ? updated : s)));
    } catch (err) {
      alert(err.message);
    } finally {
      setFinanceActionId(null);
    }
  };

  const handleUnapprovePayment = async (sale) => {
    if (!sale.is_finance_paid) return;
    const msg = `Batalkan persetujuan pembayaran ${sale.sale_no}? Rute terkait dapat diubah kembali.`;
    if (!window.confirm(msg)) return;
    setFinanceActionId(sale.id);
    try {
      const updated = await apiFetch(`/api/sales/${sale.id}/finance-unapprove`, { method: 'POST' });
      setSales((prev) => prev.map((s) => (s.id === sale.id ? updated : s)));
    } catch (err) {
      alert(err.message);
    } finally {
      setFinanceActionId(null);
    }
  };

  const handleVoidSale = async (e) => {
    e.preventDefault();
    if (!voidModal.saleId || !voidModal.reason || voidModal.reason.length < 3) return;
    try {
      const updated = await apiFetch(`/api/sales/${voidModal.saleId}/void`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ void_reason: voidModal.reason })
      });
      setSales((prev) => prev.map((s) => (s.id === voidModal.saleId ? updated : s)));
      setVoidModal({ open: false, saleId: null, reason: '' });
    } catch (err) {
      alert(err.message);
    }
  };

  const handleEdit = (sale) => {
    setIsEdit(true);
    setCurrentId(sale.id);
    setLinkedRouteId(sale.delivery_route_id || null);
    setLinkedRouteNo(sale.route_no || '');
    setForm({
      sale_no: sale.sale_no,
      date: sale.date,
      vehicle_id: sale.vehicle_id ? String(sale.vehicle_id) : '',
      driver_id: sale.driver_id ? String(sale.driver_id) : '',
      remarks: sale.remarks || '',
      extra_uang_jalan: sale.extra_uang_jalan ? String(sale.extra_uang_jalan) : '',
      ...routeFeeAmountsFromApi(sale),
      is_finance_paid: sale.is_finance_paid,
      details: sale.details.map((d) => {
        let vehicleTypeId =
          d.vehicle_type_id != null && d.vehicle_type_id !== ''
            ? String(d.vehicle_type_id)
            : '';
        if (!vehicleTypeId) {
          vehicleTypeId = inferVehicleTypeId(d.customer_id, d.amount);
        }
        return {
          customer_id: String(d.customer_id),
          vehicle_type_id: vehicleTypeId,
          vehicle_type_name: d.vehicle_type_name || '',
          amount: d.amount ?? '',
        };
      }),
    });
    if (window.location.hash !== '#modal') {
      window.history.pushState(null, '', window.location.pathname + '#modal');
    }
    setIsModalOpen(true);
  };

  const handleDelete = async (sale) => {
    const id = typeof sale === 'object' ? sale.id : sale;
    const locked = typeof sale === 'object' && sale.is_finance_paid;
    const msg = locked
      ? 'Transaksi sudah disetujui dibayar. Menghapusnya akan membuka kunci rute terkait. Lanjutkan?'
      : 'Yakin ingin menghapus transaksi uang jalan ini?';
    if (!window.confirm(msg)) return;
    try {
      await apiFetch(`/api/sales/${id}`, { method: 'DELETE' });
      setSales((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      alert(err.message);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.date) {
      alert('Pilih tanggal.');
      return;
    }

    const validDetails = form.details.filter((d) => d.customer_id && d.vehicle_type_id);
    if (validDetails.length === 0) {
      alert('Minimal masukkan 1 customer dengan jenis kendaraan.');
      return;
    }

    const payload = {
      ...form,
      vehicle_id: form.vehicle_id ? parseInt(form.vehicle_id, 10) : null,
      driver_id: form.driver_id ? parseInt(form.driver_id, 10) : null,
      extra_uang_jalan: parseAmountInput(form.extra_uang_jalan) === ''
        ? 0
        : amountToNumber(form.extra_uang_jalan),
      details: validDetails.map((d) => ({
        customer_id: parseInt(d.customer_id, 10),
        vehicle_type_id: parseInt(d.vehicle_type_id, 10),
        amount: amountToNumber(d.amount),
      })),
    };

    if (!isEdit) {
      alert('Buat transaksi dari menu Rute Pengiriman (tombol Uang Jalan).');
      return;
    }

    setSaving(true);
    try {
      await apiFetch(`/api/sales/${currentId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await fetchData();
      closeModal();
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const updateDetail = (idx, field, val) => {
    const newDetails = [...form.details];
    const row = { ...newDetails[idx], [field]: val };

    if (field === 'customer_id') {
      row.vehicle_type_id = '';
      row.vehicle_type_name = '';
      row.amount = '';
    } else if (field === 'vehicle_type_id') {
      const customer = customers.find((c) => String(c.id) === String(row.customer_id));
      const tariff = (customer?.tariffs || []).find(
        (t) => String(t.vehicle_type_id) === String(val)
      );
      row.vehicle_type_name = tariff?.vehicle_type_name || row.vehicle_type_name;
      const newAmount = lookupTariffAmount(row.customer_id, val);
      if (newAmount !== '') {
        row.amount = newAmount;
      }
    }

    newDetails[idx] = row;
    setForm({ ...form, details: newDetails });
  };

  const addDetailRow = () => {
    setForm({ ...form, details: [...form.details, emptyDetail()] });
  };

  const removeDetailRow = (idx) => {
    const newDetails = [...form.details];
    newDetails.splice(idx, 1);
    setForm({ ...form, details: newDetails });
  };

  const getExportDocument = () => buildSaleDocument(form, { vehicles, drivers, customers });

  const handlePrintForm = () => {
    printSaleDocument(getExportDocument());
  };

  const handleExportPdf = () => {
    exportSalePdf(getExportDocument());
  };

  const handleExportExcel = () => {
    exportSaleExcel(getExportDocument());
  };

  const handleProcessRoute = async (customerId) => {
    if (!customerId) {
      alert('Pilih customer terlebih dahulu.');
      return;
    }
    setRouteLoading(true);
    try {
      const result = await apiFetch('/api/routing/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: parseInt(customerId, 10) }),
      });
      setRouteResult(result);
      await fetchData();
    } catch (err) {
      alert(err.message);
    } finally {
      setRouteLoading(false);
    }
  };

  const handleSort = useCallback(
    (column) => {
      if (sortKey === column) {
        setSortDir((prevDir) => (prevDir === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(column);
        setSortDir('asc');
      }
    },
    [sortKey],
  );

  const displaySales = useMemo(
    () => [...sales].sort((a, b) => compareSales(a, b, sortKey, sortDir)),
    [sales, sortKey, sortDir],
  );

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Uang Jalan</h1>
          <p className="page-subtitle">
            Nominal uang jalan dari rute pengiriman. Rencana perjalanan diatur di{' '}
            <Link to="/delivery-routes">Rute Pengiriman</Link>.
          </p>
        </div>
        <div className="page-header-actions" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary"
            onClick={() => printBulkSales(displaySales, { fromLabel: filterFrom ? formatDate(filterFrom) : '', toLabel: filterTo ? formatDate(filterTo) : '' })}
            disabled={loading || displaySales.length === 0}
            title="Print semua data"
          >
            <Printer size={18} /> Print
          </button>
          <button
            className="btn btn-secondary"
            style={{ background: '#dc2626', color: 'white', border: 'none' }}
            onClick={() => exportBulkSalesPdf(displaySales, { fromLabel: filterFrom ? formatDate(filterFrom) : '', toLabel: filterTo ? formatDate(filterTo) : '' })}
            disabled={loading || displaySales.length === 0}
            title="Export semua ke PDF"
          >
            <FileDown size={18} /> PDF
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => exportBulkSalesExcel(displaySales, { fromLabel: filterFrom ? formatDate(filterFrom) : '', toLabel: filterTo ? formatDate(filterTo) : '' })}
            disabled={loading || displaySales.length === 0}
            title="Export semua ke Excel"
          >
            <FileSpreadsheet size={18} /> Excel
          </button>
          <button className="btn btn-secondary" onClick={fetchSales} disabled={loading}>
            <RefreshCw size={18} className={loading ? 'spin' : ''} />
            Refresh
          </button>
          <Link to="/delivery-routes/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>
            <Plus size={18} /> Rute Pengiriman
          </Link>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-group" style={{ marginBottom: 0, flex: '1 1 150px' }}>
          <label className="form-label">Dari Tanggal</label>
          <input type="date" className="form-input" value={filterFrom} onChange={(e) => setFilterFrom(e.target.value)} />
        </div>
        <div className="form-group" style={{ marginBottom: 0, flex: '1 1 150px' }}>
          <label className="form-label">Sampai Tanggal</label>
          <input type="date" className="form-input" value={filterTo} onChange={(e) => setFilterTo(e.target.value)} />
        </div>
        <div className="form-group" style={{ marginBottom: 0, flex: '2 1 200px' }}>
          <label className="form-label">Nomor Transaksi / Rute</label>
          <input type="text" className="form-input" placeholder="Cari SL-... atau RT-..." value={filterSaleNo} onChange={(e) => setFilterSaleNo(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') fetchSales(); }} />
        </div>
        <div style={{ flex: '0 0 auto' }}>
          <button className="btn btn-primary" onClick={fetchSales} disabled={loading} style={{ height: '40px', padding: '0 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Cari
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <div className="table-container" style={{ padding: 0, width: '100%' }}>
          <table className="glass-table responsive-card-table">
            <thead>
              <tr>
                <SortableTh
                  label="Nomor Transaksi"
                  column="sale_no"
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
                <SortableTh label="Rute" column="route_no" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortableTh label="Tanggal" column="date" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortableTh
                  label="Kendaraan"
                  column="vehicle_plate"
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
                <SortableTh label="Sopir" column="driver_name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortableTh
                  label="Jumlah Cust"
                  column="customer_count"
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
                <SortableTh
                  label="Total Nominal"
                  column="total"
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                  align="right"
                />
                <th>Pembayaran</th>
                <th style={{ textAlign: 'right', minWidth: '160px' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '2rem' }}>
                    Memuat data...
                  </td>
                </tr>
              ) : displaySales.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                    Tidak ada data uang jalan
                  </td>
                </tr>
              ) : (
                <>
                {displaySales.map((s) => {
                  const total = saleDetailTotal(s);
                  const isExpanded = expandedRows.has(s.id);
                  const toggleExpand = () => {
                    setExpandedRows((prev) => {
                      const next = new Set(prev);
                      if (next.has(s.id)) next.delete(s.id);
                      else next.add(s.id);
                      return next;
                    });
                  };
                  const saleDoc = () => buildSaleDocumentFromSaleOut(s);

                  const amounts = (s.details || []).map((d) => parseFloat(d.amount) || 0).filter((n) => n > 0);
                  const maxNom = amounts.length > 0 ? Math.max(...amounts) : 0;
                  const extraAmt = parseFloat(s.extra_uang_jalan) || 0;
                  const routeFeesAmt = sumRouteFees(s);
                  const routeFeeLines = getActiveRouteFeeLines(s);
                  const multi = (s.details || []).length > 1;
                  const baseUJ = multi ? maxNom : (amounts[0] || 0);
                  const { rounding: roundingUJ, total: totalUJ } = computeUangJalanTotals(
                    baseUJ,
                    extraAmt,
                    routeFeesAmt
                  );

                  return (
                    <React.Fragment key={s.id}>
                    <tr style={{ cursor: 'pointer' }} onClick={toggleExpand}>
                      <td data-label="Nomor Transaksi" style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          {s.sale_no}
                        </span>
                      </td>
                      <td data-label="Rute" style={{ whiteSpace: 'nowrap' }}>
                        {s.route_no ? (
                          <Link to="/delivery-routes" onClick={(e) => e.stopPropagation()}>{s.route_no}</Link>
                        ) : (
                          <span style={{ color: 'var(--text-secondary)' }}>Manual</span>
                        )}
                      </td>
                      <td data-label="Tanggal" style={{ whiteSpace: 'nowrap' }}>{formatDate(s.date)}</td>
                      <td data-label="Kendaraan">{s.vehicle_plate || (s.delivery_route_id ? '— belum dipilih' : '—')}</td>
                      <td data-label="Sopir">
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 500 }}>{s.driver_name || (s.delivery_route_id ? '—' : '—')}</span>
                          {s.driver_phone && <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.driver_phone}</span>}
                          {(s.driver_bank_name || s.driver_bank_account) && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                              Rek: {[s.driver_bank_name, s.driver_bank_account].filter(Boolean).join(' ')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td data-label="Customer">
                        <div style={{ fontWeight: 500 }}>{s.details.length} Customer</div>
                        {s.details.length > 0 && (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px', lineHeight: '1.3' }}>
                            {s.details.map((d, idx) => (
                              <React.Fragment key={idx}>
                                {idx > 0 && ', '}
                                {d.customer_name ? (
                                  <Link to={`/customers?editId=${d.customer_id}`} style={{ textDecoration: 'none', color: d.customer_is_locked ? '#3b82f6' : '#ef4444' }} title={d.customer_is_locked ? 'Customer sudah di-lock (finance)' : 'Buka master customer'} onClick={(e) => e.stopPropagation()}>
                                    {d.customer_name} {d.customer_is_locked && <Lock size={10} style={{ display: 'inline', verticalAlign: 'middle', marginBottom: '2px' }} />}
                                  </Link>
                                ) : (
                                  'Tanpa Nama'
                                )}
                              </React.Fragment>
                            ))}
                          </div>
                        )}
                      </td>
                      <td data-label="Total Nominal" style={{ textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap' }}>
                        {s.is_void ? (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                            <span style={{ color: 'var(--text-secondary)', textDecoration: 'line-through' }}>{formatIDR(totalUJ)}</span>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--success-color)' }}>{formatIDR(totalUJ)}</span>
                        )}
                      </td>
                      <td data-label="Pembayaran" style={{ textAlign: 'center' }}>
                        {s.is_void ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '0.25rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, background: '#fee2e2', color: '#b91c1c' }} title={s.void_reason}>
                            <Ban size={12} /> Void
                          </span>
                        ) : s.is_finance_paid ? (
                          <span className="badge-finance-paid" title={s.finance_paid_by_name ? `Oleh ${s.finance_paid_by_name}` : undefined}>
                            <Lock size={12} aria-hidden /> Sudah dibayar
                          </span>
                        ) : (
                          <span className="badge-finance-pending">Menunggu</span>
                        )}
                      </td>
                      <td data-label="Aksi" style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'inline-flex', gap: '0.35rem', justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.35rem 0.45rem' }}
                            onClick={() => printSaleDocument(saleDoc())}
                            title="Print transaksi ini"
                          >
                            <Printer size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.35rem 0.45rem' }}
                            onClick={() => exportSalePdf(saleDoc())}
                            title="Export PDF"
                          >
                            <FileDown size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.35rem 0.45rem' }}
                            onClick={() => exportSaleExcel(saleDoc())}
                            title="Export Excel"
                          >
                            <FileSpreadsheet size={14} />
                          </button>
                          {canApprovePayment && !s.is_finance_paid && !s.is_void && (
                            <button
                              type="button"
                              className="btn btn-primary"
                              style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem', whiteSpace: 'nowrap' }}
                              disabled={financeActionId === s.id}
                              onClick={() => handleApprovePayment(s)}
                              title="Setujui pembayaran uang jalan"
                            >
                              <CheckCircle2 size={14} /> Setujui
                            </button>
                          )}
                          {canApprovePayment && s.is_finance_paid && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-finance-unapprove"
                              style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem', whiteSpace: 'nowrap' }}
                              disabled={financeActionId === s.id}
                              onClick={() => handleUnapprovePayment(s)}
                              title="Batalkan persetujuan pembayaran"
                            >
                              <Undo2 size={14} /> Batalkan
                            </button>
                          )}
                          {!s.is_void && (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.4rem 0.6rem' }}
                            disabled={!canWrite}
                            onClick={() => handleEdit(s)}
                            title={!canWrite ? 'Tidak ada akses edit' : s.is_finance_paid ? 'Edit Kendaraan & Supir (Sudah Dibayar)' : 'Edit'}
                          >
                            <Edit size={16} />
                          </button>
                          )}
                          {canWrite && !s.is_void && !s.is_finance_paid && (user?.role === 'gudang' || user?.role === 'admin') && (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.4rem 0.6rem', color: '#ef4444', borderColor: '#fecaca' }}
                            onClick={() => setVoidModal({ open: true, saleId: s.id, reason: '' })}
                            title="Void Transaksi"
                          >
                            <Ban size={16} />
                          </button>
                          )}
                          {canWrite && !s.is_void && !s.is_finance_paid && (
                          <button
                            type="button"
                            className="btn btn-danger"
                            style={{ padding: '0.4rem 0.6rem' }}
                            onClick={() => handleDelete(s)}
                            title="Hapus"
                          >
                            <Trash2 size={16} />
                          </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="sale-detail-expand-row">
                        <td colSpan="9" style={{ padding: 0, background: 'var(--bg-secondary)' }}>
                          <div style={{
                            padding: '1rem 1.5rem',
                            display: 'flex',
                            gap: '2rem',
                            flexWrap: 'wrap',
                            alignItems: 'flex-start',
                          }}>
                            <div style={{ flex: '1 1 400px', minWidth: '280px' }}>
                              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Detail Customer</h4>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                                <thead>
                                  <tr style={{ borderBottom: '2px solid var(--card-border)' }}>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Customer</th>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Jenis Kendaraan</th>
                                    <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Nominal</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(s.details || []).map((d, di) => (
                                    <tr key={di} style={{ borderBottom: '1px solid var(--card-border)' }}>
                                      <td style={{ padding: '0.4rem 0.5rem' }}>{d.customer_name || '-'}</td>
                                      <td style={{ padding: '0.4rem 0.5rem' }}>{d.vehicle_type_name || '-'}</td>
                                      <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', fontWeight: 500 }}>{formatIDR(d.amount)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            <div style={{
                              flex: '0 0 280px',
                              background: 'var(--bg-primary)',
                              borderRadius: '10px',
                              padding: '1rem 1.25rem',
                              border: '1px solid var(--card-border)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.5rem',
                              fontSize: '0.85rem',
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Uang Jalan</span>
                                <span style={{ fontWeight: 600, color: 'var(--accent-color)' }}>{formatIDR(baseUJ)}</span>
                              </div>
                              {routeFeesAmt > 0 && (
                                <div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Biaya Rute</span>
                                    <span style={{ fontWeight: 600 }}>{formatIDR(routeFeesAmt)}</span>
                                  </div>
                                  {routeFeeLines.length > 0 && (
                                    <RouteFeeBreakdown
                                      lines={routeFeeLines}
                                      style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}
                                    />
                                  )}
                                </div>
                              )}
                              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Uang Jalan Tambahan</span>
                                <span>{formatIDR(extraAmt)}</span>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Pembulatan</span>
                                <span style={{ color: '#7c3aed' }}>{formatIDR(roundingUJ)}</span>
                              </div>
                              <div style={{ borderTop: '2px solid var(--card-border)', paddingTop: '0.5rem', display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ fontWeight: 700 }}>Total Uang Jalan</span>
                                <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--success-color)' }}>{formatIDR(totalUJ)}</span>
                              </div>
                              {s.remarks && (
                                <div style={{ marginTop: '0.25rem', color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.8rem' }}>
                                  Ket: {s.remarks}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                  );
                })}
                <tr style={{ background: 'var(--bg-secondary)', borderTop: '2px solid var(--card-border)' }}>
                  <td colSpan="6" style={{ textAlign: 'right', fontWeight: 700, padding: '1rem' }}>
                    TOTAL KESELURUHAN
                  </td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--success-color)', padding: '1rem', whiteSpace: 'nowrap', fontSize: '1.05rem' }}>
                    {formatIDR(displaySales.reduce((sum, s) => sum + (s.is_void ? 0 : saleDetailTotal(s)), 0))}
                  </td>
                  <td colSpan="2"></td>
                </tr>
                </>
              )}
            </tbody>
          </table>
        </div>

      {isModalOpen && (
        <div className="modal-overlay modal-overlay-full">
          <div className="modal-content modal-content-full" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleSubmit}>
              <div className="modal-header">
                <h3 className="modal-title">Edit Uang Jalan</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <button type="button" className="btn btn-secondary" onClick={handlePrintForm} title="Print">
                    <Printer size={16} /> Print
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleExportPdf} title="Export PDF">
                    <FileDown size={16} /> PDF
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleExportExcel} title="Export Excel">
                    <FileSpreadsheet size={16} /> Excel
                  </button>
                  <button type="button" className="btn-icon" onClick={closeModal}>
                    <X size={20} />
                  </button>
                </div>
              </div>

              <div className="modal-body">
                {fromRoute && (
                  <div
                    style={{
                      marginBottom: '1rem',
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      background: '#eff6ff',
                      border: '1px solid #bfdbfe',
                      fontSize: '0.9rem',
                    }}
                  >
                    Data perjalanan dari rute{' '}
                    <Link to="/delivery-routes"><strong>{linkedRouteNo}</strong></Link>. Ubah
                    tanggal atau daftar customer di menu Rute Pengiriman lalu klik Sync Uang Jalan.
                    Kendaraan dan sopir ditentukan gudang di form ini.
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                  <div className="form-group">
                    <label className="form-label">Tanggal</label>
                    <input
                      type="date"
                      className="form-input"
                      required
                      disabled={fromRoute || form.is_finance_paid}
                      value={form.date}
                      onChange={(e) => setForm({ ...form, date: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Nomor Transaksi (Opsional)</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Auto Generate"
                      disabled={form.is_finance_paid}
                      value={form.sale_no}
                      onChange={(e) => setForm({ ...form, sale_no: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Kendaraan {fromRoute ? '(Gudang)' : ''}</label>
                    <select
                      className="form-input"
                      value={String(form.vehicle_id)}
                      onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}
                    >
                      <option value="">
                        {fromRoute ? '-- Pilih kendaraan (gudang) --' : '-- Pilih Kendaraan --'}
                      </option>
                      {vehicleOptions.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.plate_number}
                          {v.type_name ? ` (${v.type_name})` : ''}
                        </option>
                      ))}
                    </select>
                    {fromRoute && vehicleOptions.length === 0 && (
                      <small style={{ color: 'var(--text-secondary)' }}>
                        Belum ada plat untuk jenis kendaraan rute ini — daftarkan di menu Vehicles.
                      </small>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Sopir {fromRoute ? '(Gudang)' : ''}</label>
                    <select
                      className="form-input"
                      value={String(form.driver_id)}
                      onChange={(e) => setForm({ ...form, driver_id: e.target.value })}
                    >
                      <option value="">{fromRoute ? '-- Pilih sopir (gudang) --' : '-- Pilih Sopir --'}</option>
                      {drivers.map((d) => {
                        const parts = [d.name];
                        if (d.phone) parts.push(d.phone);
                        if (d.bank_name || d.bank_account) {
                          const bankInfo = [d.bank_name, d.bank_account].filter(Boolean).join(' ');
                          parts.push(`(Rek: ${bankInfo})`);
                        }
                        return (
                          <option key={d.id} value={d.id}>
                            {parts.join(' — ')}
                          </option>
                        );
                      })}
                    </select>
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                  <label className="form-label">Keterangan</label>
                  <input
                    type="text"
                    className="form-input"
                    disabled={form.is_finance_paid}
                    value={form.remarks}
                    onChange={(e) => setForm({ ...form, remarks: e.target.value })}
                  />
                </div>

                <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--card-border)', paddingTop: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h4 style={{ margin: 0, fontWeight: 500 }}>Detail Customer</h4>
                    {!fromRoute && !form.is_finance_paid && (
                      <button type="button" className="btn btn-secondary" onClick={addDetailRow} style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                        <Plus size={16} /> Tambah Baris
                      </button>
                    )}
                  </div>

                  <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {fromRoute
                      ? 'Customer dan jenis kendaraan mengikuti rute. Sesuaikan nominal atau uang jalan tambahan di sini.'
                      : 'Pilih customer lalu jenis kendaraan — nominal otomatis dari tarif uang jalan master customer.'}
                  </p>

                  <div className="table-container" style={{ borderRadius: '8px', flex: 1 }}>
                    <table className="glass-table" style={{ fontSize: '0.9rem' }}>
                      <thead>
                        <tr>
                          <th style={{ width: '28%' }}>Customer</th>
                          <th style={{ width: '32%' }}>Jenis Kendaraan</th>
                          <th style={{ width: '20%', textAlign: 'right' }}>Nominal (Rp)</th>
                          <th style={{ width: '90px', textAlign: 'center' }}>Rute</th>
                          <th style={{ width: '80px', textAlign: 'center' }}>Hapus</th>
                        </tr>
                      </thead>
                      <tbody>
                        {form.details.map((row, idx) => {
                          const tariffOptions = getTariffOptions(row);
                          return (
                            <tr key={idx}>
                              <td>
                                <select
                                  className="form-input"
                                  style={{ background: 'transparent', padding: '0.4rem 0.5rem' }}
                                  required
                                  disabled={fromRoute || form.is_finance_paid}
                                  value={String(row.customer_id)}
                                  onChange={(e) => updateDetail(idx, 'customer_id', e.target.value)}
                                >
                                  <option value="">-- Pilih --</option>
                                  {customers.map((c) => (
                                    <option key={c.id} value={c.id}>{c.name}</option>
                                  ))}
                                </select>
                              </td>
                              <td>
                                <select
                                  className="form-input"
                                  style={{ background: 'transparent', padding: '0.4rem 0.5rem' }}
                                  required
                                  value={String(row.vehicle_type_id)}
                                  disabled={fromRoute || !row.customer_id || form.is_finance_paid}
                                  onChange={(e) => updateDetail(idx, 'vehicle_type_id', e.target.value)}
                                >
                                  <option value="">-- Pilih Jenis --</option>
                                  {tariffOptions.map((t) => (
                                    <option key={t.vehicle_type_id} value={String(t.vehicle_type_id)}>
                                      {t.vehicle_type_name} — {formatIDR(tariffTotal(t))}
                                    </option>
                                  ))}
                                </select>
                                {row.customer_id && tariffOptions.length === 0 && (
                                  <small style={{ color: '#fbbf24', display: 'block', marginTop: '4px' }}>
                                    Customer belum punya tarif. Atur di menu Customers.
                                  </small>
                                )}
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <input
                                  type="text"
                                  inputMode="numeric"
                                  className="form-input"
                                  style={{ background: 'transparent', padding: '0.4rem 0.5rem', textAlign: 'right' }}
                                  required
                                  disabled={form.is_finance_paid}
                                  placeholder="0"
                                  value={row.amount === '' ? '' : formatAmount(row.amount)}
                                  onChange={(e) =>
                                    updateDetail(idx, 'amount', parseAmountInput(e.target.value))
                                  }
                                />
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                <button
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{ padding: '0.35rem 0.5rem' }}
                                  disabled={!row.customer_id || routeLoading}
                                  onClick={() => handleProcessRoute(row.customer_id)}
                                  title="Proses rute gudang → customer"
                                >
                                  <MapPin size={16} />
                                </button>
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                {!fromRoute && form.details.length > 1 && (
                                  <button
                                    type="button"
                                    className="btn btn-danger"
                                    disabled={form.is_finance_paid}
                                    onClick={() => removeDetailRow(idx)}
                                    style={{ padding: '0.35rem 0.5rem' }}
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {(() => {
                    const selectedCustomerPoints = form.details
                      .map((d) => customers.find((c) => c.id === Number(d.customer_id)))
                      .filter((c) => c && c.latitude && c.longitude)
                      .map((c, idx) => ({
                        name: c.name,
                        latitude: c.latitude,
                        longitude: c.longitude,
                        isWarehouse: false,
                        label: `Rute ${idx + 1}`,
                      }));

                    if (warehouse && warehouse.latitude && warehouse.longitude) {
                      selectedCustomerPoints.unshift({
                        name: warehouse.name || 'Gudang Utama',
                        latitude: warehouse.latitude,
                        longitude: warehouse.longitude,
                        isWarehouse: true,
                        label: 'Gudang',
                      });
                    }

                    const { customerCount } = getMaxNominal(form.details);
                    const showMap = selectedCustomerPoints.length > 1;
                    const showTotals = customerCount > 0;

                    if (!showMap && !showTotals) return null;

                    const filledDetails = form.details.filter((d) => d.customer_id);
                    const amounts = filledDetails
                      .map((d) => amountToNumber(d.amount))
                      .filter((n) => n > 0);
                    const multiCustomer = filledDetails.length > 1;
                    const baseUangJalan = multiCustomer
                      ? (amounts.length > 0 ? Math.max(...amounts) : 0)
                      : (amounts[0] || 0);
                    const extraAmount = amountToNumber(form.extra_uang_jalan);
                    const routeFeesAmount = sumRouteFees(form);
                    const routeFeeLines = getActiveRouteFeeLines(form);
                    const { rounding: roundingAmount, total: totalUangJalan } = computeUangJalanTotals(
                      baseUangJalan,
                      extraAmount,
                      routeFeesAmount
                    );

                    return (
                      <>
                        <div style={{ display: 'flex', gap: '2rem', marginTop: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                          {/* Kiri: Peta */}
                          {showMap ? (
                            <div style={{ flex: '1 1 400px', minWidth: '300px', border: '1px solid var(--card-border)', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
                              <MultiPointMap
                                points={selectedCustomerPoints}
                                height={260}
                                onRouteCalculated={handleRouteCalculated}
                              />
                              {routeKm.totalKm > 0 && (
                                <div
                                  style={{
                                    position: 'absolute',
                                    bottom: 10,
                                    left: 10,
                                    zIndex: 10,
                                    background: 'rgba(255,255,255,0.94)',
                                    padding: '0.4rem 0.55rem',
                                    borderRadius: 6,
                                    border: '1px solid #e2e8f0',
                                  }}
                                >
                                  <RouteKmBreakdown
                                    totalKm={routeKm.totalKm}
                                    legs={routeKm.legs}
                                    variant="overlay"
                                    bbmAmount={sequentialBbm}
                                  />
                                </div>
                              )}
                              <button
                                type="button"
                                onClick={() => setIsMapFullscreen(true)}
                                style={{
                                  position: 'absolute',
                                  top: '10px',
                                  right: '10px',
                                  zIndex: 10,
                                  background: 'white',
                                  border: '1px solid #ccc',
                                  borderRadius: '4px',
                                  padding: '4px 8px',
                                  cursor: 'pointer',
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  fontSize: '0.8rem',
                                  color: '#333'
                                }}
                              >
                                <Maximize size={14} /> Perbesar
                              </button>
                            </div>
                          ) : (
                            <div style={{ flex: '1 1 400px' }} />
                          )}

                          {/* Kanan: Total */}
                          {showTotals && (
                            <div
                              style={{
                                flex: '0 0 350px',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.75rem',
                              }}
                            >
                              {routeKm.totalKm > 0 && (
                                <div className="form-group" style={{ marginBottom: 0 }}>
                                  <label className="form-label">Jarak Tempuh (berurutan)</label>
                                  <RouteKmBreakdown
                                    totalKm={routeKm.totalKm}
                                    legs={routeKm.legs}
                                    variant="panel"
                                    bbmAmount={sequentialBbm}
                                  />
                                </div>
                              )}
                              <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label">Uang Jalan</label>
                                <input
                                  type="text"
                                  className="form-input"
                                  readOnly
                                  value={formatIDR(baseUangJalan)}
                                  style={{
                                    fontWeight: 600,
                                    color: 'var(--accent-color)',
                                    textAlign: 'right',
                                    background: '#f8fafc',
                                  }}
                                />
                              </div>
                              <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label">Biaya Rute</label>
                                <input
                                  type="text"
                                  className="form-input"
                                  readOnly
                                  value={formatIDR(routeFeesAmount)}
                                  style={{
                                    fontWeight: 600,
                                    textAlign: 'right',
                                    background: '#f8fafc',
                                  }}
                                />
                                {routeFeeLines.length > 0 ? (
                                  <RouteFeeBreakdown
                                    lines={routeFeeLines}
                                    style={{
                                      marginTop: '0.35rem',
                                      fontSize: '0.78rem',
                                      color: 'var(--text-secondary)',
                                    }}
                                  />
                                ) : (
                                  <small style={{ color: 'var(--text-secondary)' }}>
                                    Dari Rute Pengiriman (Uang Pelabuhan, PJR, Forklift Bongkaran, Parkir Liar, Parkir Kawasan).
                                  </small>
                                )}
                              </div>
                              <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label">Uang Jalan Tambahan</label>
                                <input
                                  type="text"
                                  inputMode="numeric"
                                  className="form-input"
                                  style={{ textAlign: 'right' }}
                                  disabled={form.is_finance_paid}
                                  placeholder="0"
                                  value={form.extra_uang_jalan === '' ? '' : formatAmount(form.extra_uang_jalan)}
                                  onChange={(e) =>
                                    setForm({ ...form, extra_uang_jalan: parseAmountInput(e.target.value) })
                                  }
                                />
                              </div>
                              <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label">Pembulatan (Ke Atas Ribuan)</label>
                                <input
                                  type="text"
                                  className="form-input"
                                  readOnly
                                  value={formatIDR(roundingAmount)}
                                  style={{
                                    textAlign: 'right',
                                    background: '#f8fafc',
                                    color: 'var(--text-secondary)',
                                  }}
                                />
                              </div>
                              <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label">Total Uang Jalan</label>
                                <input
                                  type="text"
                                  className="form-input"
                                  readOnly
                                  value={formatIDR(totalUangJalan)}
                                  style={{
                                    fontWeight: 700,
                                    fontSize: '1.1rem',
                                    textAlign: 'right',
                                    background: '#f1f5f9',
                                    color: '#0f172a',
                                  }}
                                />
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Fullscreen Map Modal */}
                        {isMapFullscreen && showMap && (
                          <div style={{
                            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                            zIndex: 9999, background: 'rgba(0,0,0,0.85)', padding: '2rem',
                            display: 'flex', flexDirection: 'column'
                          }}>
                            <div style={{ background: 'var(--bg-primary)', flex: 1, borderRadius: '12px', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
                              <div style={{ padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--card-border)', background: 'var(--bg-secondary)' }}>
                                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <MapPin size={20} color="#2563eb" /> Peta Rute Pengiriman
                                </h3>
                                <button type="button" className="btn btn-secondary" onClick={() => setIsMapFullscreen(false)} style={{ padding: '0.4rem 0.5rem' }}>
                                  <X size={20} />
                                </button>
                              </div>
                              <div style={{ flex: 1, width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
                                <div style={{ flex: 1, minHeight: 0 }}>
                                  <MultiPointMap points={selectedCustomerPoints} height="100%" />
                                </div>
                                {routeKm.totalKm > 0 && (
                                  <div style={{ padding: '0 1rem 1rem' }}>
                                    <RouteKmBreakdown
                                      totalKm={routeKm.totalKm}
                                      legs={routeKm.legs}
                                      variant="panel"
                                      bbmAmount={sequentialBbm}
                                    />
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>

              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeModal} disabled={saving}>
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Menyimpan...' : 'Simpan Uang Jalan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <RouteResultModal
        result={routeResult}
        onClose={() => setRouteResult(null)}
      />
      {/* Void Modal */}
      {voidModal.open && (
        <div className="modal-overlay" onClick={() => setVoidModal({ open: false, saleId: null, reason: '' })}>
          <div className="modal-content" style={{ maxWidth: '400px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Void Transaksi</h2>
              <button className="btn-close" onClick={() => setVoidModal({ open: false, saleId: null, reason: '' })}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <form onSubmit={handleVoidSale}>
                <div className="form-group">
                  <label>Alasan Batal Jalan <span style={{ color: '#ef4444' }}>*</span></label>
                  <textarea
                    className="form-input"
                    rows="3"
                    value={voidModal.reason}
                    onChange={(e) => setVoidModal({ ...voidModal, reason: e.target.value })}
                    placeholder="Masukkan alasan pembatalan..."
                    required
                    minLength={3}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setVoidModal({ open: false, saleId: null, reason: '' })}>
                    Batal
                  </button>
                  <button type="submit" className="btn btn-danger" disabled={voidModal.reason.length < 3}>
                    Void Transaksi
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sales;
