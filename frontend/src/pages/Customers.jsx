import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Plus, Trash2, Edit2, Search, MapPin, X, FileSpreadsheet, Download, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import * as XLSX from 'xlsx';
import { apiFetch } from '../api';
import LocationPickerMap from '../components/LocationPickerMap';
import TollEstimateTable from '../components/TollEstimateTable';
import TollReferenceTable from '../components/TollReferenceTable';
import { useCrudWrite, CrudActionsHeader, CrudActionsCell } from '../components/CrudWriteAccess';
import { parseCoordsFromShareText } from '../utils/locationParse';

const formatIDR = (val) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(val);

const parseAmount = (value) => {
  if (value === '' || value == null) return 0;
  const cleaned = String(value).replace(/\./g, '').replace(/,/g, '').trim();
  if (cleaned === '') return 0;
  const num = Number(cleaned);
  return Number.isNaN(num) || num < 0 ? 0 : num;
};

const formatNumberDisplay = (value) => {
  if (value === '' || value == null) return '';
  const num = parseAmount(value);
  if (num === 0) return '';
  return new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(num);
};

const formatCustomerCoords = (latitude, longitude) => {
  if (latitude == null || longitude == null) return null;
  const lat = Number(latitude);
  const lng = Number(longitude);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  return { lat: lat.toFixed(7), lng: lng.toFixed(7) };
};

const compareCustomers = (a, b, key, dir) => {
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
    case 'code':
      return nullsLast(a.code, b.code, (x, y) =>
        String(x).localeCompare(String(y), 'id', { numeric: true, sensitivity: 'base' }),
      );
    case 'name':
      return nullsLast(a.name, b.name, (x, y) =>
        String(x).localeCompare(String(y), 'id', { sensitivity: 'base' }),
      );
    case 'phone':
      return nullsLast(a.phone, b.phone, (x, y) =>
        String(x).localeCompare(String(y), 'id', { numeric: true, sensitivity: 'base' }),
      );
    case 'coords': {
      const aHas = a.latitude != null && a.longitude != null;
      const bHas = b.latitude != null && b.longitude != null;
      if (!aHas && !bHas) return 0;
      if (!aHas) return 1;
      if (!bHas) return -1;
      const latDiff = Number(a.latitude) - Number(b.latitude);
      if (latDiff !== 0) return sign * (latDiff > 0 ? 1 : -1);
      const lngDiff = Number(a.longitude) - Number(b.longitude);
      return sign * (lngDiff > 0 ? 1 : lngDiff < 0 ? -1 : 0);
    }
    case 'is_active': {
      if (a.is_active === b.is_active) return 0;
      return sign * (a.is_active ? -1 : 1);
    }
    default:
      return 0;
  }
};

const normalizeHeaderKey = (key) =>
  key?.toString().trim().toUpperCase().replace(/\s+/g, ' ');

const cellText = (value) => {
  if (value === '' || value == null) return '';
  return String(value).trim();
};

const parseExcelCustomerRows = (sheet) => {
  const matrix = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
  if (!matrix.length) return [];

  const headerRowIndex = matrix.findIndex((row) => {
    const cells = row.map((cell) => normalizeHeaderKey(cell));
    const hasCode = cells.some((c) => c === 'KODE' || c === 'CODE');
    const hasName = cells.some((c) => c === 'NAMA' || c === 'NAME');
    return hasCode && hasName;
  });

  const parseMappedRow = (mapped) => {
    const code = cellText(mapped.KODE ?? mapped.CODE);
    const name = cellText(mapped.NAMA ?? mapped.NAME);
    if (!code || !name) return null;
    if (code === 'KODE' || code === 'CODE' || name === 'NAMA' || name === 'NAME') return null;

    const lat = parseFloat(mapped.LATITUDE ?? mapped.LAT ?? '');
    const lng = parseFloat(mapped.LONGITUDE ?? mapped.LNG ?? mapped.LONG ?? '');

    return {
      code,
      name,
      kelurahan: cellText(mapped.KELURAHAN ?? mapped.VILLAGE) || null,
      kecamatan: cellText(mapped.KECAMATAN ?? mapped.DISTRICT) || null,
      address: cellText(mapped.ALAMAT ?? mapped.ADDRESS) || null,
      city: cellText(mapped.KOTA ?? mapped.CITY) || null,
      phone:
        cellText(
          mapped.TELEPON ??
            mapped.PHONE ??
            mapped.HP ??
            mapped['NO HP'] ??
            mapped['NO TELEPON']
        ) || null,
      email: cellText(mapped.EMAIL ?? mapped['E-MAIL']) || null,
      latitude: Number.isNaN(lat) ? null : lat,
      longitude: Number.isNaN(lng) ? null : lng,
    };
  };

  if (headerRowIndex >= 0) {
    const headers = matrix[headerRowIndex].map((cell) => normalizeHeaderKey(cell));
    const rows = [];
    for (let i = headerRowIndex + 1; i < matrix.length; i += 1) {
      const mapped = {};
      headers.forEach((header, idx) => {
        if (header) mapped[header] = matrix[i][idx];
      });
      const parsed = parseMappedRow(mapped);
      if (parsed) rows.push(parsed);
    }
    return rows;
  }

  const objectRows = XLSX.utils.sheet_to_json(sheet, { defval: '' });
  return objectRows
    .map((row) => {
      const mapped = {};
      Object.keys(row).forEach((k) => {
        mapped[normalizeHeaderKey(k)] = row[k];
      });
      return parseMappedRow(mapped);
    })
    .filter(Boolean);
};

/** BBM (Rp) = (jarak km ÷ km/liter master jenis) × 2 × harga BBM */
const calcAutoBbm = (distanceKm, vt) => {
  if (!distanceKm || !vt?.km_per_liter) return null;
  const base = distanceKm / vt.km_per_liter;
  const afterRoundTrip = base * 2;
  if (vt.bbm_price) {
    const rawPrice = afterRoundTrip * vt.bbm_price;
    // Bulatkan ke ribuan terdekat
    return Math.round(rawPrice / 1000) * 1000;
  }
  return Math.round(afterRoundTrip);
};

const tariffRowTotal = (row) =>
  parseAmount(row.bbm)
  + parseAmount(row.tol)
  + parseAmount(row.uang_mel)
  + parseAmount(row.parkir)
  + parseAmount(row.lain_lain);

const masterUangMel = (vehicleType) => String(vehicleType?.uang_mel || 0);

const buildTariffRows = (vehicleTypes, existingTariffs = []) =>
  vehicleTypes.map((t) => {
    const found = existingTariffs.find((x) => x.vehicle_type_id === t.id);
    const hasBreakdown =
      found &&
      (parseAmount(found.bbm) > 0 ||
        parseAmount(found.tol) > 0 ||
        parseAmount(found.uang_mel) > 0 ||
        parseAmount(found.parkir) > 0 ||
        parseAmount(found.lain_lain) > 0);
    return {
      vehicle_type_id: t.id,
      vehicle_type_name: t.name,
      bbm: found?.bbm ? String(found.bbm) : '',
      tol: found?.tol ? String(found.tol) : '',
      uang_mel: masterUangMel(t),
      parkir: found?.parkir ? String(found.parkir) : '',
      lain_lain:
        found?.lain_lain && parseAmount(found.lain_lain) > 0
          ? String(found.lain_lain)
          : !hasBreakdown && found?.uang_jalan
            ? String(found.uang_jalan)
            : '',
    };
  });

const tariffPayloadRows = (rows) =>
  rows.map((row) => {
    const total = tariffRowTotal(row);
    return {
      vehicle_type_id: row.vehicle_type_id,
      bbm: parseAmount(row.bbm),
      tol: parseAmount(row.tol),
      uang_mel: parseAmount(row.uang_mel),
      parkir: parseAmount(row.parkir),
      lain_lain: parseAmount(row.lain_lain),
      uang_jalan: total,
    };
  });

const TariffAmountInput = ({ value, onChange }) => (
  <input
    type="text"
    inputMode="numeric"
    className="form-input"
    style={{ background: 'transparent', padding: '0.35rem 0.45rem', width: '100%' }}
    placeholder="0"
    value={formatNumberDisplay(value)}
    onChange={(e) => {
      const digits = e.target.value.replace(/\D/g, '');
      onChange(digits === '' ? '' : String(parseInt(digits, 10)));
    }}
  />
);

const SortableTh = ({ label, column, sortKey, sortDir, onSort, align }) => (
  <th style={align ? { textAlign: align } : undefined} className="th-sortable">
    <button type="button" className="th-sort-btn" onClick={() => onSort(column)}>
      <span>{label}</span>
      {sortKey === column ? (
        sortDir === 'asc' ? <ArrowUp size={14} aria-hidden /> : <ArrowDown size={14} aria-hidden />
      ) : (
        <ArrowUpDown size={14} style={{ opacity: 0.4 }} aria-hidden />
      )}
    </button>
  </th>
);

const TariffReadonlyAmount = ({ value }) => (
  <div
    style={{
      padding: '0.35rem 0.45rem',
      minHeight: '2.1rem',
      color: parseAmount(value) > 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
      background: 'rgba(0,0,0,0.03)',
      borderRadius: '6px',
      fontSize: '0.85rem',
    }}
  >
    {parseAmount(value) > 0 ? formatNumberDisplay(value) : '-'}
  </div>
);

const Customers = () => {
  const canWrite = useCrudWrite();
  const [customers, setCustomers] = useState([]);
  const [loadingCustomers, setLoadingCustomers] = useState(true);
  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState('code');
  const [sortDir, setSortDir] = useState('asc');
  const [error, setError] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [parsingShare, setParsingShare] = useState(false);
  const [shareLocationInput, setShareLocationInput] = useState('');
  const [routeInfo, setRouteInfo] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState('');
  const [tollReference, setTollReference] = useState(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [forceToll, setForceToll] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [form, setForm] = useState({
    code: '',
    name: '',
    address: '',
    kelurahan: '',
    kecamatan: '',
    city: '',
    phone: '',
    email: '',
    latitude: '',
    longitude: '',
    is_active: true,
    tariffs: [],
  });

  const fetchCustomers = async () => {
    setLoadingCustomers(true);
    try {
      const data = await apiFetch('/api/customers');
      setCustomers(Array.isArray(data) ? data : []);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingCustomers(false);
    }
  };

  const fetchVehicleTypes = async () => {
    try {
      const data = await apiFetch('/api/vehicle-types');
      setVehicleTypes(data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchCustomers();
    fetchVehicleTypes();
  }, []);

  useEffect(() => {
    if (!isModalOpen) return;
    apiFetch('/api/routing/toll-reference')
      .then(setTollReference)
      .catch(() => setTollReference(null));
  }, [isModalOpen]);

  useEffect(() => {
    const handlePopState = () => {
      if (isModalOpen) {
        setIsModalOpen(false);
        setRouteInfo(null);
        setRouteError('');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isModalOpen]);

  const openModal = async (customer = null) => {
    if (!canWrite) return;
    if (customer) {
      setEditId(customer.id);
      try {
        const full = await apiFetch(`/api/customers/${customer.id}`);
        setForceToll(full.force_toll || false);
        setForm({
          code: full.code || '',
          name: full.name || '',
          address: full.address || '',
          kelurahan: full.kelurahan || '',
          kecamatan: full.kecamatan || '',
          city: full.city || '',
          phone: full.phone || '',
          email: full.email || '',
          latitude: full.latitude != null ? String(full.latitude) : '',
          longitude: full.longitude != null ? String(full.longitude) : '',
          is_active: full.is_active,
          tariffs: buildTariffRows(vehicleTypes, full.tariffs || []),
        });
      } catch (err) {
        alert(err.message);
        return;
      }
    } else {
      setEditId(null);
      setForceToll(false);
      setForm({
        code: '',
        name: '',
        address: '',
        kelurahan: '',
        kecamatan: '',
        city: '',
        phone: '',
        email: '',
        latitude: '',
        longitude: '',
        is_active: true,
        tariffs: buildTariffRows(vehicleTypes),
      });
    }
    setShareLocationInput('');
    if (window.location.hash !== '#modal') {
      window.history.pushState(null, '', window.location.pathname + '#modal');
    }
    setIsModalOpen(true);
  };

  useEffect(() => {
    if (!isModalOpen || editId) return;
    setForm((prev) => ({
      ...prev,
      tariffs: buildTariffRows(vehicleTypes),
    }));
  }, [vehicleTypes, isModalOpen, editId]);

  const hasCoords =
    form.latitude &&
    form.longitude &&
    !Number.isNaN(parseFloat(form.latitude)) &&
    !Number.isNaN(parseFloat(form.longitude));

  const closeModal = () => {
    if (window.location.hash === '#modal') {
      window.history.back();
    } else {
      setIsModalOpen(false);
      setRouteInfo(null);
      setRouteError('');
      setShareLocationInput('');
    }
  };

  const applyCoords = (latitude, longitude) => {
    setForm((prev) => ({
      ...prev,
      latitude: String(latitude),
      longitude: String(longitude),
    }));
  };

  const handleParseShareLocation = async () => {
    const text = shareLocationInput.trim();
    if (!text) return;

    setParsingShare(true);
    setError('');
    try {
      const local = parseCoordsFromShareText(text);
      if (local) {
        applyCoords(local.latitude, local.longitude);
        return;
      }

      const data = await apiFetch('/api/geocode/from-share', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      applyCoords(data.latitude, data.longitude);
    } catch (err) {
      setError(err.message);
    } finally {
      setParsingShare(false);
    }
  };

  const fetchRouteInfo = async () => {
    if (
      !form.latitude ||
      !form.longitude ||
      Number.isNaN(parseFloat(form.latitude)) ||
      Number.isNaN(parseFloat(form.longitude))
    ) {
      setRouteInfo(null);
      return;
    }

    setRouteLoading(true);
    setRouteError('');
    try {
      const body = {
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        name: form.name || 'Customer',
        force_toll: forceToll,
      };
      if (editId) body.customer_id = editId;

      const result = await apiFetch('/api/routing/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setRouteInfo(result);
    } catch (err) {
      setRouteInfo(null);
      setRouteError(err.message);
    } finally {
      setRouteLoading(false);
    }
  };

  useEffect(() => {
    if (!isModalOpen || !hasCoords) {
      setRouteInfo(null);
      setRouteError('');
      return undefined;
    }
    const timer = setTimeout(() => {
      fetchRouteInfo();
    }, 600);
    return () => clearTimeout(timer);
  }, [form.latitude, form.longitude, isModalOpen, form.name, forceToll]);

  useEffect(() => {
    if (!isModalOpen || !routeInfo?.distance_km || vehicleTypes.length === 0) return;
    setForm((prev) => ({
      ...prev,
      tariffs: prev.tariffs.map((row) => {
        const vt = vehicleTypes.find((t) => t.id === row.vehicle_type_id);
        const tollItem = routeInfo.toll_by_vehicle?.find(
          (t) => t.vehicle_type_id === row.vehicle_type_id
        );
        const autoBbm = calcAutoBbm(routeInfo.distance_km, vt);
        return {
          ...row,
          bbm: autoBbm != null ? String(autoBbm) : row.bbm,
          tol: tollItem ? String(Math.round(tollItem.toll_idr)) : row.tol,
          uang_mel: masterUangMel(vt),
        };
      }),
    }));
  }, [routeInfo, isModalOpen, vehicleTypes]);

  useEffect(() => {
    if (!isModalOpen || vehicleTypes.length === 0) return;
    setForm((prev) => ({
      ...prev,
      tariffs: prev.tariffs.map((row) => {
        const vt = vehicleTypes.find((t) => t.id === row.vehicle_type_id);
        return { ...row, uang_mel: masterUangMel(vt) };
      }),
    }));
  }, [vehicleTypes, isModalOpen]);

  const handleGeocode = async () => {
    setGeocoding(true);
    setError('');
    try {
      let data;
      if (editId) {
        await apiFetch(`/api/customers/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: form.code.trim(),
            name: form.name,
            address: form.address || null,
            kelurahan: form.kelurahan || null,
            kecamatan: form.kecamatan || null,
            city: form.city || null,
            phone: form.phone || null,
            email: form.email || null,
            is_active: form.is_active,
            latitude: form.latitude ? parseFloat(form.latitude) : null,
            longitude: form.longitude ? parseFloat(form.longitude) : null,
            tariffs: tariffPayloadRows(form.tariffs),
          }),
        });
        data = await apiFetch(`/api/customers/${editId}/geocode`, { method: 'POST' });
      } else {
        data = await apiFetch('/api/geocode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: form.name,
            address: form.address || null,
            kelurahan: form.kelurahan || null,
            kecamatan: form.kecamatan || null,
            city: form.city || null,
          }),
        });
      }
      applyCoords(data.latitude, data.longitude);
    } catch (err) {
      setError(err.message);
    } finally {
      setGeocoding(false);
    }
  };

  const updateTariff = (typeId, field, value) => {
    setForm((prev) => ({
      ...prev,
      tariffs: prev.tariffs.map((row) =>
        row.vehicle_type_id === typeId ? { ...row, [field]: value } : row
      ),
    }));
  };

  const autoFillBbmTol = () => {
    if (!routeInfo?.distance_km) return;
    setForm((prev) => ({
      ...prev,
      tariffs: prev.tariffs.map((row) => {
        const vt = vehicleTypes.find((t) => t.id === row.vehicle_type_id);
        const tollItem = routeInfo.toll_by_vehicle?.find(
          (t) => t.vehicle_type_id === row.vehicle_type_id
        );
        const autoBbm = calcAutoBbm(routeInfo.distance_km, vt);
        const bbm = autoBbm != null ? String(autoBbm) : row.bbm;
        const tol = tollItem ? String(Math.round(tollItem.toll_idr)) : row.tol;
        return { ...row, bbm, tol, uang_mel: masterUangMel(vt) };
      }),
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.code?.trim()) {
      alert('Kode customer wajib diisi.');
      return;
    }
    if (!form.name?.trim()) {
      alert('Nama customer wajib diisi.');
      return;
    }

    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      address: form.address || null,
      kelurahan: form.kelurahan || null,
      kecamatan: form.kecamatan || null,
      city: form.city || null,
      phone: form.phone || null,
      email: form.email || null,
      is_active: form.is_active,
      force_toll: forceToll,
      latitude: form.latitude ? parseFloat(form.latitude) : null,
      longitude: form.longitude ? parseFloat(form.longitude) : null,
      tariffs: tariffPayloadRows(form.tariffs),
    };

    setError('');
    setIsSubmitting(true);
    try {
      if (editId) {
        await apiFetch(`/api/customers/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch('/api/customers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      closeModal();
      fetchCustomers();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Yakin ingin menghapus data customer ini?')) return;
    try {
      await apiFetch(`/api/customers/${id}`, { method: 'DELETE' });
      fetchCustomers();
    } catch (err) {
      alert(err.message);
    }
  };

  const fileInputRef = useRef(null);

  const handleImportExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    try {
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: 'array' });
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      const customers = parseExcelCustomerRows(sheet);

      if (customers.length === 0) {
        alert(
          'Tidak ditemukan data valid. Pastikan ada baris header KODE & NAMA, lalu isi kode dan nama di setiap baris.'
        );
        return;
      }

      if (!window.confirm(`Ditemukan ${customers.length} baris data customer. Lanjutkan import?`)) return;

      const result = await apiFetch('/api/customers/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customers }),
      });

      setSearchTerm('');
      await fetchCustomers();

      if (!result?.imported) {
        alert(
          `Import selesai, tetapi tidak ada data baru yang tersimpan.\n\n` +
            `✅ Berhasil: ${result?.imported ?? 0}\n` +
            `⏭️ Dilewati (kode duplikat / tidak valid): ${result?.skipped ?? 0}\n\n` +
            `Kemungkinan kode customer sudah ada di database. Gunakan kode unik per baris.`
        );
      } else {
        alert(
          `Import selesai!\n\n` +
            `✅ Berhasil: ${result.imported} customer\n` +
            `⏭️ Dilewati: ${result.skipped} baris`
        );
      }
    } catch (err) {
      alert('Gagal import: ' + err.message);
    }
  };

  const downloadTemplate = () => {
    const header = ['KODE', 'NAMA', 'ALAMAT', 'KELURAHAN', 'KECAMATAN', 'KOTA', 'TELEPON', 'EMAIL', 'LATITUDE', 'LONGITUDE'];
    const example = ['CST-001', 'PT Contoh Jaya', 'Jl. Raya No.1', 'Sukagalih', 'Sukajadi', 'Bandung', '08123456789', 'info@contoh.com', '-6.200000', '106.816666'];
    const ws = XLSX.utils.aoa_to_sheet([header, example]);
    // Set column widths
    ws['!cols'] = header.map((h) => ({ wch: Math.max(h.length + 2, 16) }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Template Customer');
    XLSX.writeFile(wb, 'template_import_customer.xlsx');
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

  const displayCustomers = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    const filtered = customers.filter((c) => {
      if (!term) return true;
      return (
        (c.name && c.name.toLowerCase().includes(term)) ||
        (c.code && c.code.toLowerCase().includes(term))
      );
    });
    return [...filtered].sort((a, b) => compareCustomers(a, b, sortKey, sortDir));
  }, [customers, searchTerm, sortKey, sortDir]);

  return (
    <div>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ background: 'none', WebkitTextFillColor: 'initial', color: 'var(--text-primary)' }}>
            Daftar Customer
          </h1>
          <p>Master data customer. Kode customer harus unik; nama boleh sama.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            style={{ display: 'none' }}
            onChange={handleImportExcel}
          />
          <button
            className="btn btn-secondary"
            onClick={downloadTemplate}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <Download size={18} /> Template
          </button>
          {canWrite && (
            <>
              <button
                className="btn btn-secondary"
                onClick={() => fileInputRef.current?.click()}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
              >
                <FileSpreadsheet size={18} /> Import Excel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => openModal()}
                style={{ background: '#4f46e5' }}
                disabled={vehicleTypes.length === 0}
              >
                <Plus size={18} /> Tambah Customer
              </button>
            </>
          )}
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
          }}
        >
          {error}
        </div>
      )}

      {vehicleTypes.length === 0 && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#fffbeb',
            color: '#92400e',
            border: '1px solid #fde68a',
          }}
        >
          Isi dulu master <strong>Jenis Kendaraan</strong> (Fuso, Tronton, Engkel, dll.).
        </div>
      )}

      <div style={{ marginBottom: '0.75rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
        {loadingCustomers
          ? 'Memuat daftar customer...'
          : `Menampilkan ${displayCustomers.length} dari ${customers.length} customer`}
      </div>

      <div style={{ marginBottom: '1.5rem', maxWidth: '400px', position: 'relative' }}>
        <Search
          size={18}
          style={{
            position: 'absolute',
            left: '1rem',
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--text-secondary)',
          }}
        />
        <input
          type="text"
          className="form-input"
          placeholder="Cari kode atau nama customer..."
          style={{ paddingLeft: '2.8rem', background: 'rgba(255,255,255,0.05)' }}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="table-container glass-panel" style={{ padding: 0 }}>
        <table className="glass-table">
          <thead>
            <tr>
              <SortableTh label="KODE" column="code" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <SortableTh label="NAMA" column="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <SortableTh label="KOORDINAT" column="coords" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <SortableTh label="TELEPON" column="phone" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <th style={{ padding: '1rem', textAlign: 'left', fontWeight: 600, fontSize: '0.75rem', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>TOL</th>
              <SortableTh label="STATUS" column="is_active" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <CrudActionsHeader canWrite={canWrite} label="AKSI" />
            </tr>
          </thead>
          <tbody>
            {loadingCustomers ? (
              <tr>
                <td colSpan={canWrite ? 7 : 6} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                  Memuat data customer...
                </td>
              </tr>
            ) : (
              displayCustomers.map((c) => {
              const coords = formatCustomerCoords(c.latitude, c.longitude);
              return (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>{c.code || '-'}</td>
                <td style={{ fontWeight: 500 }}>{c.name}</td>
                <td style={{ fontSize: '0.85rem', lineHeight: 1.4, whiteSpace: 'nowrap' }}>
                  {coords ? (
                    <>
                      <span style={{ display: 'block', fontFamily: 'ui-monospace, monospace' }}>{coords.lat}</span>
                      <span style={{ display: 'block', fontFamily: 'ui-monospace, monospace', opacity: 0.85 }}>{coords.lng}</span>
                    </>
                  ) : (
                    '-'
                  )}
                </td>
                <td>{c.phone || '-'}</td>
                <td>
                  {c.force_toll ? (
                    <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)' }}>Asumsi Tol</span>
                  ) : (
                    <span className="badge" style={{ background: 'rgba(107, 114, 128, 0.1)', color: '#6b7280', border: '1px solid rgba(107, 114, 128, 0.2)' }}>Normal</span>
                  )}
                </td>
                <td>
                  {c.is_active ? (
                    <span className="badge badge-green">Aktif</span>
                  ) : (
                    <span className="badge badge-red">Non-Aktif</span>
                  )}
                </td>
                <CrudActionsCell canWrite={canWrite}>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '0.4rem', marginRight: '0.5rem', background: 'transparent', border: 'none' }}
                    onClick={() => openModal(c)}
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    className="btn btn-danger"
                    style={{ padding: '0.4rem', background: 'transparent', border: 'none' }}
                    onClick={() => handleDelete(c.id)}
                  >
                    <Trash2 size={16} />
                  </button>
                </CrudActionsCell>
              </tr>
            );
            })
            )}
            {!loadingCustomers && displayCustomers.length === 0 && (
              <tr>
                <td colSpan={canWrite ? 7 : 6} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                  Tidak ada data customer
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {isModalOpen && canWrite && (
        <div className="modal-overlay modal-overlay-full">
          <div className="modal-content modal-content-full" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleSubmit}>
              <div className="modal-header">
                <h2>{editId ? 'Edit Customer' : 'Tambah Customer Baru'}</h2>
                <button type="button" className="btn-icon" onClick={closeModal} aria-label="Tutup">
                  <X size={20} />
                </button>
              </div>
              <div className="modal-body">
                {error && (
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
                    {error}
                  </div>
                )}
                <div className="grid-cols-2" style={{ gap: '1.5rem', alignItems: 'start' }}>
                  <div>
                    <div className="grid-cols-2" style={{ gap: '1rem', marginBottom: '1rem' }}>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Kode <span style={{ color: '#dc2626' }}>*</span>
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          required
                          value={form.code}
                          onChange={(e) => setForm({ ...form, code: e.target.value })}
                        />
                      </div>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Nama
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          required
                          value={form.name}
                          onChange={(e) => setForm({ ...form, name: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label" style={{ textTransform: 'none' }}>
                        Alamat
                      </label>
                      <textarea
                        className="form-input"
                        style={{ background: 'transparent', minHeight: '60px', resize: 'vertical' }}
                        value={form.address}
                        onChange={(e) => setForm({ ...form, address: e.target.value })}
                      />
                    </div>

                    <div className="grid-cols-2" style={{ gap: '1rem', marginBottom: '1rem' }}>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Kelurahan
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          value={form.kelurahan}
                          onChange={(e) => setForm({ ...form, kelurahan: e.target.value })}
                        />
                      </div>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Kecamatan
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          value={form.kecamatan}
                          onChange={(e) => setForm({ ...form, kecamatan: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="grid-cols-2" style={{ gap: '1rem' }}>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Kota/Kabupaten
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          value={form.city}
                          onChange={(e) => setForm({ ...form, city: e.target.value })}
                        />
                      </div>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Telepon
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          value={form.phone}
                          onChange={(e) => setForm({ ...form, phone: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="grid-cols-2" style={{ gap: '1rem', marginTop: '1rem' }}>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ textTransform: 'none' }}>
                          Email
                        </label>
                        <input
                          type="email"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          value={form.email}
                          onChange={(e) => setForm({ ...form, email: e.target.value })}
                        />
                      </div>
                      <div
                        className="form-group"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          marginBottom: 0,
                          marginTop: '1.75rem',
                        }}
                      >
                        <input
                          type="checkbox"
                          id="is_active"
                          checked={form.is_active}
                          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                        />
                        <label htmlFor="is_active" style={{ cursor: 'pointer' }}>
                          Aktif
                        </label>
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label" style={{ textTransform: 'none' }}>
                        Koordinat (Latitude / Longitude)
                      </label>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '0.5rem', alignItems: 'end' }}>
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          placeholder="Latitude"
                          value={form.latitude}
                          onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                        />
                        <input
                          type="text"
                          className="form-input"
                          style={{ background: 'transparent' }}
                          placeholder="Longitude"
                          value={form.longitude}
                          onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                        />
                        <button type="button" className="btn btn-secondary" onClick={handleGeocode} disabled={geocoding}>
                          <MapPin size={16} /> {geocoding ? '...' : 'Geocode'}
                        </button>
                      </div>
                      <small style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', display: 'block', marginTop: '0.35rem' }}>
                        Koordinat dipakai untuk hitung rute gudang → customer di form Uang Jalan. Setelah Geocode, pastikan titik di peta sudah benar — geser manual jika perlu.
                      </small>
                      <div style={{ marginTop: '0.75rem' }}>
                        <label className="form-label" style={{ textTransform: 'none', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                          Share lokasi WA / Google Maps
                        </label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.5rem', alignItems: 'end' }}>
                          <input
                            type="text"
                            className="form-input"
                            style={{ background: 'transparent' }}
                            placeholder="Tempel link share lokasi dari WhatsApp"
                            value={shareLocationInput}
                            onChange={(e) => setShareLocationInput(e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={handleParseShareLocation}
                            disabled={parsingShare || !shareLocationInput.trim()}
                          >
                            <MapPin size={16} /> {parsingShare ? '...' : 'Ambil Koordinat'}
                          </button>
                        </div>
                        <small style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', display: 'block', marginTop: '0.35rem' }}>
                          Mendukung link Google Maps dari WhatsApp (termasuk maps.app.goo.gl) atau koordinat lat, lng.
                        </small>
                      </div>
                    </div>

                    <div className="form-group" style={{ marginTop: '1.25rem', marginBottom: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '0.75rem',
                          marginBottom: '0.5rem',
                          flexWrap: 'wrap',
                        }}
                      >
                        <label className="form-label" style={{ textTransform: 'none', marginBottom: 0 }}>
                          Tarif Uang Jalan per Jenis Kendaraan
                        </label>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                            <input
                              type="checkbox"
                              checked={forceToll}
                              onChange={(e) => setForceToll(e.target.checked)}
                            />
                            Asumsikan lewat jalan Tol
                          </label>
                          {routeInfo && (
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
                              onClick={autoFillBbmTol}
                            >
                              Isi BBM &amp; Tol dari rute
                            </button>
                          )}
                        </div>
                      </div>
                      <div
                        className="table-container"
                        style={{ padding: 0, border: '1px solid var(--glass-border)', borderRadius: '8px', overflowX: 'auto' }}
                      >
                        <table className="glass-table" style={{ fontSize: '0.85rem', minWidth: '840px' }}>
                          <thead>
                            <tr>
                              <th>Jenis</th>
                              <th style={{ width: '110px' }}>BBM (Rp)</th>
                              <th style={{ width: '110px' }}>Tol (Rp)</th>
                              <th style={{ width: '110px' }}>Uang Mel (Rp)</th>
                              <th style={{ width: '110px' }}>Parkir (Rp)</th>
                              <th style={{ width: '110px' }}>Lain-lain (Rp)</th>
                              <th style={{ width: '130px', textAlign: 'right' }}>Uang Jalan (Rp)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {form.tariffs.map((row) => (
                              <tr key={row.vehicle_type_id}>
                                <td style={{ fontWeight: 500, verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                                  {row.vehicle_type_name}
                                </td>
                                <td>
                                  <TariffReadonlyAmount value={row.bbm} />
                                </td>
                                <td>
                                  <TariffReadonlyAmount value={row.tol} />
                                </td>
                                <td>
                                  <TariffReadonlyAmount value={row.uang_mel} />
                                </td>
                                <td>
                                  <TariffAmountInput
                                    value={row.parkir}
                                    onChange={(raw) => updateTariff(row.vehicle_type_id, 'parkir', raw)}
                                  />
                                </td>
                                <td>
                                  <TariffAmountInput
                                    value={row.lain_lain}
                                    onChange={(raw) => updateTariff(row.vehicle_type_id, 'lain_lain', raw)}
                                  />
                                </td>
                                <td
                                  style={{
                                    textAlign: 'right',
                                    fontWeight: 600,
                                    verticalAlign: 'middle',
                                    color: tariffRowTotal(row) > 0 ? 'var(--accent-color)' : 'var(--text-secondary)',
                                  }}
                                >
                                  {tariffRowTotal(row) > 0 ? formatIDR(tariffRowTotal(row)) : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <small style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        BBM &amp; Tol dihitung otomatis dari rute (tidak bisa diubah manual). Uang Mel diisi otomatis dari master jenis kendaraan. Parkir &amp; Lain-lain diisi manual. Uang jalan = BBM + Tol + Uang Mel + Parkir + Lain-lain.
                      </small>
                      
                      <div
                        style={{
                          marginTop: '1.5rem',
                          padding: '1rem',
                          borderRadius: '8px',
                          background: 'rgba(59, 130, 246, 0.05)',
                          border: '1px solid rgba(59, 130, 246, 0.2)',
                          fontSize: '0.85rem',
                          color: 'var(--text-secondary)'
                        }}
                      >
                        <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary)', fontSize: '0.9rem' }}>Rumus Perhitungan Otomatis</h4>
                        <ul style={{ margin: 0, paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          <li>
                            <strong>BBM:</strong> <code>(Jarak km &divide; Konsumsi BBM km/liter) &times; 2 (Pulang Pergi) &times; Harga BBM</code>
                            <br/>
                            <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>*Data Konsumsi &amp; Harga BBM diambil dari Master Jenis Kendaraan.</span>
                          </li>
                          <li>
                            <strong>Tol:</strong> <code>Estimasi API Google Maps</code> atau <code>Acuan Tol Jabodetabek (proporsional jarak)</code> &times; 2 (Pulang Pergi)
                            <br/>
                            <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>*Tarif disesuaikan dengan golongan tiap jenis kendaraan.</span>
                          </li>
                        </ul>
                      </div>

                    </div>
                  </div>

                  <div className="glass-panel" style={{ position: 'sticky', top: 0 }}>
                    <TollReferenceTable reference={tollReference} />

                    <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Peta Lokasi</h3>

                    {routeLoading && (
                      <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                        Menghitung rute gudang → customer...
                      </p>
                    )}

                    {routeError && (
                      <div
                        style={{
                          marginBottom: '1rem',
                          padding: '0.75rem 1rem',
                          borderRadius: '8px',
                          background: '#fffbeb',
                          color: '#92400e',
                          border: '1px solid #fde68a',
                          fontSize: '0.9rem',
                        }}
                      >
                        {routeError}
                      </div>
                    )}

                    {routeInfo && (
                      <>
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(2, 1fr)',
                            gap: '0.75rem',
                            marginBottom: '1rem',
                          }}
                        >
                          <div
                            style={{
                              padding: '0.85rem',
                              borderRadius: '8px',
                              border: '1px solid var(--glass-border)',
                              background: 'rgba(255,255,255,0.5)',
                            }}
                          >
                            <p className="form-label" style={{ marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                              Jarak Gudang → Customer
                            </p>
                            <p style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700 }}>
                              {routeInfo.distance_km.toLocaleString('id-ID')} km
                            </p>
                          </div>
                          <div
                            style={{
                              padding: '0.85rem',
                              borderRadius: '8px',
                              border: '1px solid var(--glass-border)',
                              background: 'rgba(255,255,255,0.5)',
                            }}
                          >
                            <p className="form-label" style={{ marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                              Estimasi Waktu
                            </p>
                            <p style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700 }}>
                              {routeInfo.duration_min.toLocaleString('id-ID')} menit
                            </p>
                          </div>
                        </div>

                        <TollEstimateTable
                          items={routeInfo.toll_by_vehicle}
                          isEstimate={routeInfo.toll_is_estimate}
                        />
                      </>
                    )}

                      <LocationPickerMap
                        key={`${form.latitude}-${form.longitude}-${routeInfo?.geometry?.length || 0}`}
                        latitude={form.latitude}
                        longitude={form.longitude}
                        onLocationChange={(lat, lng) => setForm({ ...form, latitude: String(lat), longitude: String(lng) })}
                        origin={routeInfo?.origin || null}
                        geometry={routeInfo?.geometry || []}
                        height="calc(100vh - 520px)"
                      />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>
                  Batal
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  style={{ background: '#4f46e5' }}
                  disabled={geocoding || routeLoading || isSubmitting}
                >
                  {isSubmitting ? 'Menyimpan...' : (editId ? 'Simpan' : 'Tambah')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Customers;
