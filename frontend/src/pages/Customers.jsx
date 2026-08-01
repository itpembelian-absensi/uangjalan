import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Plus, Trash2, Edit2, Search, MapPin, X, FileSpreadsheet, Download, ArrowUp, ArrowDown, ArrowUpDown, Lock, Unlock, Clock, RefreshCw } from 'lucide-react';
import * as XLSX from 'xlsx';
import { apiFetch } from '../api';
import LocationPickerMap from '../components/LocationPickerMap';
import TollEstimateTable from '../components/TollEstimateTable';
import RouteTollGateInfo from '../components/RouteTollGateInfo';
import { useCrudWrite, CrudActionsHeader, CrudActionsCell } from '../components/CrudWriteAccess';
import TablePager from '../components/TablePager';
import { parseCoordsFromShareText } from '../utils/locationParse';

const formatIDR = (val) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(val);

const normTollName = (value) => (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
const vehicleTollAllowed = (name) => !normTollName(name).includes('viar');

const tollByVehicleFromSegments = (segments, vehicleTypes, distanceKm) => {
  const pickRate = (rates, gol) => {
    if (!rates) return 0;
    if (rates[gol] != null) return rates[gol];
    if (gol === 'III' && rates.II != null) return rates.II;
    if (gol === 'V' && rates.IV != null) return rates.IV;
    return rates.II ?? rates.III ?? rates.IV ?? 0;
  };

  return vehicleTypes
    .map((vt) => {
      const gol = vt.toll_golongan?.code || 'II';
      if (!vehicleTollAllowed(vt.name)) {
        return {
          vehicle_type_id: vt.id,
          vehicle_type_name: vt.name,
          golongan: gol,
          gandar: '-',
          toll_idr: 0,
          rate_per_km: 0,
        };
      }
      const oneWay = (segments || []).reduce((sum, row) => sum + pickRate(row.rates_by_golongan, gol), 0);
      const toll = Math.round(oneWay * 2);
      const rounded = toll > 0 ? Math.ceil(toll / 1000) * 1000 : 0;
      return {
        vehicle_type_id: vt.id,
        vehicle_type_name: vt.name,
        golongan: gol,
        gandar: '-',
        toll_idr: rounded,
        rate_per_km: distanceKm ? Math.round(rounded / distanceKm) : 0,
      };
    })
    .sort((a, b) => a.vehicle_type_name.localeCompare(b.vehicle_type_name));
};

const storedManualTollBreakdown = (value) => {
  if (!Array.isArray(value)) return null;
  const hasExplicitManualMarker = value.some((row) => row?._manual_override === true);
  if (!hasExplicitManualMarker) return null;
  return value.filter((row) => row?.section_id);
};

/** Ruas tol tersimpan untuk ditampilkan saat Finance terkunci (tanpa hitung ulang). */
const storedTollBreakdownForDisplay = (value) => {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (row) =>
      row &&
      (row.section_id || row.entry_gate_name || row.exit_gate_name || row.section_name),
  );
};

const customTollBreakdownPayload = (routeInfo, manualOverride) => {
  const rows = (routeInfo?.toll_breakdown || []).filter(
    (row) =>
      row &&
      (row.section_id || row.entry_gate_name || row.exit_gate_name || row.section_name),
  );
  // Snapshot ruas selalu disimpan agar saat Finance terkunci tetap bisa ditampilkan.
  if (!rows.length) {
    return manualOverride ? [{ _manual_override: true }] : null;
  }
  if (manualOverride) {
    return rows.map((row) => ({ ...row, _manual_override: true }));
  }
  return rows.map((row) => ({ ...row, _locked_snapshot: true }));
};

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
    case 'is_locked_finance': {
      // Final (2) > Marketing (1) > Open (0) — match badge priority in the LOCK column
      const lockRank = (c) => (c.is_locked_finance ? 2 : c.is_locked_marketing ? 1 : 0);
      const diff = lockRank(a) - lockRank(b);
      if (diff === 0) {
        return String(a.code || '').localeCompare(String(b.code || ''), 'id', {
          numeric: true,
          sensitivity: 'base',
        });
      }
      return sign * (diff > 0 ? -1 : 1);
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

const masterUangMel = (vehicleType) => String(vehicleType?.uang_mel_amount || 0);

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
      tol: vehicleTollAllowed(t.name) && found?.tol ? String(found.tol) : '',
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
    const tol = vehicleTollAllowed(row.vehicle_type_name) ? parseAmount(row.tol) : 0;
    const total = tariffRowTotal({ ...row, tol });
    return {
      vehicle_type_id: row.vehicle_type_id,
      bbm: parseAmount(row.bbm),
      tol,
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
    {parseAmount(value) > 0 ? formatNumberDisplay(value) : '0'}
  </div>
);

import { useAuth } from '../auth/AuthContext';

const Customers = () => {
  const { user, hasPermission } = useAuth();
  // Hak kunci/buka Finance dari Matriks Akses → "Kunci Finance Customer" (Lihat & Edit).
  const canManageFinanceLock = hasPermission('customers:finance_lock');
  const canUnlockFinanceLock = canManageFinanceLock;
  const canWrite = useCrudWrite();
  const location = useLocation();
  const [customers, setCustomers] = useState([]);
  const [loadingCustomers, setLoadingCustomers] = useState(true);
  const [vehicleTypes, setVehicleTypes] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState('code');
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [parsingShare, setParsingShare] = useState(false);
  const [routeInfo, setRouteInfo] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState('');
  const [routeTrigger, setRouteTrigger] = useState(0);
  const [tollSections, setTollSections] = useState([]);
  const [tollManualLoading, setTollManualLoading] = useState(false);
  const [manualTollOverride, setManualTollOverride] = useState(false);
  const [routeRefreshNeeded, setRouteRefreshNeeded] = useState(false);
  const persistedTollBreakdownRef = useRef(null);
  const corridorDebounceRef = useRef(null);
  const corridorFetchSeqRef = useRef(0);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [forceToll, setForceToll] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [isUnlockingAll, setIsUnlockingAll] = useState(false);
  const [isLockingAll, setIsLockingAll] = useState(false);
  const [isRelockingPrevious, setIsRelockingPrevious] = useState(false);
  const [restorePendingCount, setRestorePendingCount] = useState(0);
  const [distanceLoading, setDistanceLoading] = useState(false);

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
    share_location: '',
    is_active: true,
    is_locked_marketing: false,
    is_locked_finance: false,
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

  const fetchRestorePending = async () => {
    if (user?.role !== 'admin') {
      setRestorePendingCount(0);
      return;
    }
    try {
      const data = await apiFetch('/api/customers/lock-restore-status');
      setRestorePendingCount(Number(data?.pending_count) || 0);
    } catch {
      setRestorePendingCount(0);
    }
  };

  const fetchTollSections = async () => {
    try {
      const data = await apiFetch('/api/toll-sections');
      setTollSections(Array.isArray(data) ? data.filter((row) => row.is_active !== false) : []);
    } catch {
      setTollSections([]);
    }
  };

  const fetchManualBreakdownFast = async (sectionIds) => {
    return apiFetch('/api/routing/toll-breakdown/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_ids: sectionIds }),
    });
  };

  const fetchRouteWithSections = async (
    sectionIds,
    { forceAuto = false, distanceProvider = 'osrm' } = {}
  ) => {
    const lat = parseFloat(form.latitude);
    const lng = parseFloat(form.longitude);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return null;

    const body = {
      latitude: lat,
      longitude: lng,
      name: form.name || 'Customer',
      force_toll: forceToll,
      route_profile: 'auto',
      distance_provider:
        distanceProvider === 'google'
          ? 'google'
          : distanceProvider === 'osrm_direct' || distanceProvider === 'direct'
            ? 'osrm_direct'
            : 'osrm',
    };
    if (editId) body.customer_id = editId;
    if (!forceAuto && sectionIds?.length) {
      body.route_profile = 'manual';
      body.section_ids = sectionIds;
    }

    return apiFetch('/api/routing/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  };

  const recalculateDistanceWithProvider = async (provider) => {
    const wantDirect = provider === 'osrm_direct' || provider === 'direct' || provider === 'google';

    // Jika kedua jarak sudah ada dari API, ganti lokal (cepat & pasti terlihat)
    if (
      provider !== 'google' &&
      routeInfo &&
      routeInfo.distance_km_route != null &&
      routeInfo.distance_km_direct != null
    ) {
      const nextKm = wantDirect
        ? Number(routeInfo.distance_km_direct)
        : Number(routeInfo.distance_km_route);
      const nextDur = wantDirect
        ? Number(routeInfo.duration_min_direct ?? routeInfo.duration_min)
        : Number(routeInfo.duration_min_route ?? routeInfo.duration_min);
      const sameKm = Math.abs(Number(routeInfo.distance_km) - nextKm) < 0.05;
      setRouteInfo((prev) => ({
        ...prev,
        distance_km: nextKm,
        duration_min: nextDur,
        distance_source: wantDirect ? 'osrm_direct' : 'osrm',
      }));
      if (sameKm) {
        setRouteError(
          wantDirect
            ? 'Untuk skema ini jarak rute & jarak langsung hampir sama. Selisih jelas saat Manual + koridor gerbang (mis. DU004).'
            : 'Jarak rute OSRM dipakai untuk BBM.'
        );
      } else {
        setRouteError('');
      }
      return;
    }

    const useManual = Boolean(manualTollOverride);
    const sectionIds = useManual
      ? routeInfo?.toll_breakdown
          ?.map((row) => row.section_id)
          .filter((id) => id != null) ||
        persistedTollBreakdownRef.current
          ?.map((row) => row.section_id)
          .filter((id) => id != null) ||
        []
      : [];

    setDistanceLoading(true);
    setRouteError('');
    try {
      const result = await fetchRouteWithSections(sectionIds, {
        forceAuto: !useManual,
        distanceProvider: provider,
      });
      if (!result) {
        setRouteError('Koordinat customer belum valid.');
        return;
      }
      setRouteInfo({
        ...result,
        route_profile: useManual ? 'manual' : result.route_profile || 'auto',
      });
      if (useManual && result.toll_breakdown?.length) {
        persistedTollBreakdownRef.current = result.toll_breakdown;
      }
    } catch (err) {
      setRouteError(err.message || 'Gagal menghitung jarak.');
    } finally {
      setDistanceLoading(false);
    }
  };

  const distanceSourceLabel = (source, viaGates) => {
    if (source === 'google') return 'Google Maps';
    if (source === 'osrm_direct') return 'OSRM langsung (≈ Google)';
    if (viaGates) return 'OSRM koridor';
    return 'OSRM';
  };

  const applyManualTollUpdate = async (sectionIds) => {
    const seq = ++corridorFetchSeqRef.current;
    const prev = routeInfo;
    setManualTollOverride(true);
    setRouteError('');

    // Kosongkan ruas: jangan panggil API manual (min 1 section), jaga override kosong.
    if (!sectionIds?.length) {
      const emptyToll = tollByVehicleFromSegments([], vehicleTypes, prev?.distance_km);
      persistedTollBreakdownRef.current = [];
      setRouteInfo({
        ...prev,
        toll_breakdown: [],
        toll_by_vehicle: emptyToll,
        toll_idr: 0,
        toll_source: 'manual',
        toll_is_estimate: false,
        toll_note: 'Ruas tol dikosongkan. Tambah manual, atau klik Refresh otomatis (Google / BPJT).',
        toll_roads: [],
        route_profile: 'manual',
        route_via_toll_gates: false,
      });

      if (corridorDebounceRef.current) clearTimeout(corridorDebounceRef.current);
      corridorDebounceRef.current = setTimeout(async () => {
        if (seq !== corridorFetchSeqRef.current) return;
        setRouteLoading(true);
        try {
          const result = await fetchRouteWithSections(null, { forceAuto: true });
          if (seq !== corridorFetchSeqRef.current) return;
          const cleared = tollByVehicleFromSegments([], vehicleTypes, result?.distance_km);
          persistedTollBreakdownRef.current = [];
          setManualTollOverride(true);
          setRouteInfo({
            ...result,
            toll_breakdown: [],
            toll_by_vehicle: cleared,
            toll_idr: 0,
            toll_source: 'manual',
            toll_is_estimate: false,
            toll_note: 'Ruas tol dikosongkan. Tambah manual, atau klik Refresh otomatis (Google / BPJT).',
            toll_roads: [],
            route_profile: 'manual',
            route_via_toll_gates: false,
          });
        } catch (err) {
          if (seq === corridorFetchSeqRef.current) setRouteError(err.message);
        } finally {
          if (seq === corridorFetchSeqRef.current) setRouteLoading(false);
        }
      }, 400);
      return;
    }

    const manual = await fetchManualBreakdownFast(sectionIds);
    if (seq !== corridorFetchSeqRef.current) return;

    const breakdown = manual.segments || [];
    if (sectionIds.length > 0 && breakdown.length === 0) {
      setRouteError(
        'Ruas yang dipilih tidak bisa dimuat. Coba pilih ulang dari master, atau refresh halaman.'
      );
      return;
    }
    if (breakdown.length < sectionIds.length) {
      setRouteError(
        `Hanya ${breakdown.length} dari ${sectionIds.length} ruas yang berhasil dimuat. Periksa master ruas tol.`
      );
    }
    const tollByVehicle = tollByVehicleFromSegments(breakdown, vehicleTypes, prev?.distance_km);
    persistedTollBreakdownRef.current = breakdown;
    setRouteInfo({
      ...prev,
      toll_breakdown: breakdown,
      toll_by_vehicle: tollByVehicle,
      toll_idr: tollByVehicle[0]?.toll_idr ?? manual.toll_idr,
      toll_source: 'manual',
      toll_is_estimate: false,
      toll_note: manual.toll_note || prev?.toll_note,
      route_profile: 'manual',
    });

    if (corridorDebounceRef.current) clearTimeout(corridorDebounceRef.current);
    corridorDebounceRef.current = setTimeout(async () => {
      if (seq !== corridorFetchSeqRef.current) return;
      setRouteLoading(true);
      try {
        const result = await fetchRouteWithSections(sectionIds);
        if (seq !== corridorFetchSeqRef.current) return;
        if (result?.toll_breakdown?.length) {
          persistedTollBreakdownRef.current = result.toll_breakdown;
        }
        setRouteInfo(result);
      } catch (err) {
        if (seq === corridorFetchSeqRef.current) setRouteError(err.message);
      } finally {
        if (seq === corridorFetchSeqRef.current) setRouteLoading(false);
      }
    }, 400);
  };

  const replaceTollSegmentAt = async (idx, sectionId) => {
    setTollManualLoading(true);
    setRouteError('');
    try {
      const prev = routeInfo;
      if (!prev?.toll_breakdown?.length) return;
      const sectionIds = prev.toll_breakdown
        .map((row, i) => (i === idx ? sectionId : row.section_id))
        .filter(Boolean);
      await applyManualTollUpdate(sectionIds);
    } catch (err) {
      setRouteError(err.message);
    } finally {
      setTollManualLoading(false);
    }
  };

  const addTollSegment = async (sectionId) => {
    if (!sectionId) return;
    const sid = Number(sectionId);
    if (routeInfo?.toll_breakdown?.some((row) => Number(row.section_id) === sid)) {
      setRouteError('Ruas tol ini sudah ada di tabel.');
      return;
    }
    setTollManualLoading(true);
    setRouteError('');
    try {
      const prev = routeInfo;
      if (!prev) return;
      const sectionIds = [...(prev.toll_breakdown || []).map((row) => row.section_id), sid]
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id) && id > 0);
      await applyManualTollUpdate(sectionIds);
    } catch (err) {
      setRouteError(err.message);
    } finally {
      setTollManualLoading(false);
    }
  };

  const removeTollSegmentAt = async (idx) => {
    const prev = routeInfo;
    if (!prev?.toll_breakdown?.length) return;
    const sectionIds = prev.toll_breakdown
      .filter((_, i) => i !== idx)
      .map((row) => row.section_id)
      .filter(Boolean);
    setTollManualLoading(true);
    setRouteError('');
    try {
      await applyManualTollUpdate(sectionIds);
    } catch (err) {
      setRouteError(err.message);
    } finally {
      setTollManualLoading(false);
    }
  };

  const clearAllTollSegments = async () => {
    setTollManualLoading(true);
    setRouteError('');
    try {
      await applyManualTollUpdate([]);
    } catch (err) {
      setRouteError(err.message);
    } finally {
      setTollManualLoading(false);
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
    fetchRestorePending();
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      if (isModalOpen) {
        setIsModalOpen(false);
        setRouteInfo(null);
        setRouteError('');
        setRouteTrigger(0);
        setManualTollOverride(false);
        persistedTollBreakdownRef.current = null;
        corridorFetchSeqRef.current += 1;
        if (corridorDebounceRef.current) clearTimeout(corridorDebounceRef.current);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isModalOpen]);

  useEffect(() => {
    if (isModalOpen) {
      fetchTollSections();
    }
  }, [isModalOpen]);

  const openModal = async (customer = null) => {
    if (!canWrite) return;
    fetchTollSections();
    setRouteRefreshNeeded(false);
    if (customer) {
      setEditId(customer.id);
      try {
        const full = await apiFetch(`/api/customers/${customer.id}`);
        setForceToll(full.force_toll || false);
        const savedManualBreakdown = storedManualTollBreakdown(full.custom_toll_breakdown);
        persistedTollBreakdownRef.current = savedManualBreakdown;
        setManualTollOverride(savedManualBreakdown != null);
        const financeLocked = Boolean(full.is_locked_finance);
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
          share_location: full.share_location || '',
          is_active: full.is_active,
          is_locked_marketing: full.is_locked_marketing || false,
          is_locked_finance: financeLocked,
          tariffs: buildTariffRows(vehicleTypes, full.tariffs || []),
        });
        // Finance terkunci: jangan hitung ulang — tampilkan snapshot ruas tersimpan.
        if (financeLocked) {
          const lockedSegments = storedTollBreakdownForDisplay(full.custom_toll_breakdown);
          setRouteInfo({
            distance_km: null,
            duration_min: null,
            geometry: [],
            toll_roads: [],
            toll_breakdown: lockedSegments,
            toll_by_vehicle: [],
            toll_idr: 0,
            toll_source: 'locked',
            toll_is_estimate: false,
            toll_note: lockedSegments.length
              ? 'Finance terkunci — menampilkan ruas tol saat dikunci. Buka kunci lalu Refresh untuk hitung ulang.'
              : 'Finance terkunci — ruas tol belum tersimpan di snapshot. Buka kunci lalu klik Refresh rute, BBM & Tol.',
            route_via_toll_gates: false,
          });
          setRouteError('');
        } else {
          setRouteInfo(null);
          setRouteError('');
        }
      } catch (err) {
        alert(err.message);
        return;
      }
    } else {
      setEditId(null);
      setForceToll(false);
      persistedTollBreakdownRef.current = null;
      setManualTollOverride(false);
      setRouteInfo(null);
      setRouteError('');
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
        share_location: '',
        is_active: true,
        is_locked_marketing: false,
        is_locked_finance: false,
        tariffs: buildTariffRows(vehicleTypes),
      });
    }
    if (window.location.hash !== '#modal') {
      window.history.pushState(null, '', window.location.pathname + '#modal');
    }
    setIsModalOpen(true);
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const qEditId = params.get('editId');
    if (qEditId && !isModalOpen && canWrite && customers.length > 0) {
      const targetCustomer = customers.find((c) => String(c.id) === qEditId);
      if (targetCustomer) {
        openModal(targetCustomer);
        window.history.replaceState(null, '', window.location.pathname);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, customers, canWrite, isModalOpen]);

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
      setManualTollOverride(false);
      setRouteRefreshNeeded(false);
      persistedTollBreakdownRef.current = null;
      corridorFetchSeqRef.current += 1;
      if (corridorDebounceRef.current) clearTimeout(corridorDebounceRef.current);
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
    const text = (form.share_location || '').trim();
    if (!text) return;

    setParsingShare(true);
    setError('');
    try {
      const local = parseCoordsFromShareText(text);
      if (local) {
        applyCoords(local.latitude, local.longitude);
        setRouteTrigger(prev => prev + 1);
        return;
      }

      const data = await apiFetch('/api/geocode/from-share', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      applyCoords(data.latitude, data.longitude);
      setRouteTrigger(prev => prev + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setParsingShare(false);
    }
  };

  const fetchRouteInfo = async ({ forceAuto = false } = {}) => {
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
      if (forceAuto) {
        persistedTollBreakdownRef.current = null;
      }

      const keepManualEmpty =
        !forceAuto
        && Array.isArray(persistedTollBreakdownRef.current)
        && persistedTollBreakdownRef.current.length === 0;

      const sectionIds = forceAuto || keepManualEmpty
        ? null
        : persistedTollBreakdownRef.current?.map((row) => row.section_id).filter(Boolean);

      const result = await fetchRouteWithSections(sectionIds, { forceAuto: forceAuto || keepManualEmpty });
      if (forceAuto) {
        setManualTollOverride(false);
      } else if (keepManualEmpty) {
        const cleared = tollByVehicleFromSegments([], vehicleTypes, result?.distance_km);
        persistedTollBreakdownRef.current = [];
        setManualTollOverride(true);
        setRouteInfo({
          ...result,
          toll_breakdown: [],
          toll_by_vehicle: cleared,
          toll_idr: 0,
          toll_source: 'manual',
          toll_is_estimate: false,
          toll_note: 'Ruas tol dikosongkan. Tambah manual, atau klik Refresh otomatis (Google / BPJT).',
          toll_roads: [],
          route_profile: 'manual',
          route_via_toll_gates: false,
        });
        return;
      } else if (sectionIds?.length) {
        setManualTollOverride(true);
        if (result?.toll_breakdown?.length) {
          persistedTollBreakdownRef.current = result.toll_breakdown;
        }
      }
      setRouteInfo(result);
    } catch (err) {
      setRouteInfo(null);
      setRouteError(err.message);
    } finally {
      setRouteLoading(false);
    }
  };

  const refillRouteFromMap = async () => {
    corridorFetchSeqRef.current += 1;
    if (corridorDebounceRef.current) clearTimeout(corridorDebounceRef.current);
    // Lepas kunci kosong manual agar deteksi otomatis (BPJT / Google) aktif lagi
    persistedTollBreakdownRef.current = null;
    setManualTollOverride(false);
    setTollManualLoading(true);
    setRouteError('');
    try {
      await fetchRouteInfo({ forceAuto: true });
    } finally {
      setTollManualLoading(false);
    }
  };

  useEffect(() => {
    if (!isModalOpen || !hasCoords) {
      if (!form.is_locked_finance) {
        setRouteInfo(null);
        setRouteError('');
      }
      return undefined;
    }
    // Finance terkunci / menunggu refresh setelah unlock → jangan auto-hitung.
    if (form.is_locked_finance || routeRefreshNeeded) return undefined;
    const timer = setTimeout(() => {
      fetchRouteInfo();
    }, 1200);
    return () => clearTimeout(timer);
    // is_locked_finance & routeRefreshNeeded sengaja tidak di deps:
    // unlock tidak boleh memicu hitung ulang otomatis (pakai tombol Refresh).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.latitude, form.longitude, isModalOpen, form.name, forceToll, routeTrigger]);

  useEffect(() => {
    if (!isModalOpen || !routeInfo?.distance_km || vehicleTypes.length === 0) return;
    // Jangan timpa tarif tersimpan selama Finance terkunci.
    if (form.is_locked_finance) return;
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
  }, [routeInfo, isModalOpen, vehicleTypes, form.is_locked_finance]);

  useEffect(() => {
    if (!isModalOpen || vehicleTypes.length === 0) return;
    if (form.is_locked_finance) return;
    setForm((prev) => ({
      ...prev,
      tariffs: prev.tariffs.map((row) => {
        const vt = vehicleTypes.find((t) => t.id === row.vehicle_type_id);
        return { ...row, uang_mel: masterUangMel(vt) };
      }),
    }));
  }, [vehicleTypes, isModalOpen, form.is_locked_finance]);

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
            is_locked_marketing: form.is_locked_marketing,
            is_locked_finance: canManageFinanceLock
              ? form.is_locked_finance
              : Boolean(customers.find((c) => c.id === editId)?.is_locked_finance),
            latitude: form.latitude ? parseFloat(form.latitude) : null,
            longitude: form.longitude ? parseFloat(form.longitude) : null,
            tariffs: tariffPayloadRows(form.tariffs),
            custom_toll_breakdown: customTollBreakdownPayload(routeInfo, manualTollOverride),
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
    if (form.is_locked_finance) return;
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

  const handleRefreshRouteBbmTol = async () => {
    if (form.is_locked_finance) return;
    setTollManualLoading(true);
    setRouteError('');
    try {
      await fetchRouteInfo({ forceAuto: true });
      setRouteRefreshNeeded(false);
    } finally {
      setTollManualLoading(false);
    }
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

    setError('');
    setIsSubmitting(true);
    try {
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
        is_locked_marketing: form.is_locked_marketing,
        // Marketing tidak boleh ubah Kunci Finance — kirim status server apa adanya.
        is_locked_finance: canManageFinanceLock
          ? form.is_locked_finance
          : Boolean(customers.find((c) => c.id === editId)?.is_locked_finance),
        force_toll: forceToll,
        latitude: form.latitude ? parseFloat(form.latitude) : null,
        longitude: form.longitude ? parseFloat(form.longitude) : null,
        share_location: form.share_location || null,
        tariffs: tariffPayloadRows(form.tariffs),
        custom_toll_breakdown: customTollBreakdownPayload(routeInfo, manualTollOverride),
      };

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
      alert(err.message);
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

  const handleUnlockFinance = async () => {
    if (!editId) return;
    if (!window.confirm('Buka kunci Finance (Final) untuk customer ini? Kunci Marketing tidak diubah.')) return;
    setError('');
    setIsUnlocking(true);
    try {
      const updated = await apiFetch(`/api/customers/${editId}/unlock-finance`, { method: 'POST' });
      setForm((prev) => ({
        ...prev,
        is_locked_finance: false,
        is_locked_marketing: updated.is_locked_marketing ?? prev.is_locked_marketing,
      }));
      setRouteRefreshNeeded(true);
      setCustomers((prev) =>
        prev.map((c) =>
          c.id === editId
            ? {
                ...c,
                is_locked_finance: false,
                is_locked_marketing: updated.is_locked_marketing ?? c.is_locked_marketing,
                updated_at: updated.updated_at ?? c.updated_at,
                updated_by_name: updated.updated_by_name ?? c.updated_by_name,
              }
            : c
        )
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUnlocking(false);
    }
  };

  const handleUnlockAllCustomers = async () => {
    const lockedCount = customers.filter((c) => c.is_locked_finance).length;
    if (lockedCount === 0) {
      alert('Tidak ada Master Customer yang terkunci Finance.');
      return;
    }
    if (
      !window.confirm(
        `Buka kunci Finance (Final) untuk SEMUA Master Customer?\n\n${lockedCount} customer terkunci Finance akan dibuka.\nKunci Marketing tidak diubah.\n\nDaftar yang dibuka akan disimpan agar bisa dikunci kembali setelah sync (tombol "Kunci Kembali Sebelumnya").`
      )
    ) {
      return;
    }
    setError('');
    setIsUnlockingAll(true);
    try {
      const result = await apiFetch('/api/customers/unlock-all', { method: 'POST' });
      await fetchCustomers();
      setRestorePendingCount(Number(result.restore_pending_count) || 0);
      if (isModalOpen && editId) {
        setForm((prev) => ({
          ...prev,
          is_locked_finance: false,
        }));
        setRouteRefreshNeeded(true);
      }
      alert(result.message || `Berhasil membuka kunci Finance ${result.unlocked_count} customer.`);
    } catch (err) {
      setError(err.message);
      alert(err.message);
    } finally {
      setIsUnlockingAll(false);
    }
  };

  const handleRelockPreviousCustomers = async () => {
    if (restorePendingCount <= 0) {
      alert(
        'Belum ada antrian kunci kembali.\n\n' +
          'Urutan yang benar:\n' +
          '1. Klik "Buka Kunci Finance Semua" (daftar yang terkunci disimpan)\n' +
          '2. Lakukan sync / perubahan massal\n' +
          '3. Baru klik "Kunci Kembali Sebelumnya"\n\n' +
          'Tombol aktif dan menampilkan jumlah (N) setelah langkah 1.'
      );
      return;
    }
    if (
      !window.confirm(
        `Kunci kembali hanya customer yang sebelumnya terkunci Finance?\n\n${restorePendingCount} customer akan dikunci ulang.\nCustomer yang tadinya Open tetap Open.\nKunci Marketing ikut diaktifkan jika belum aktif.`
      )
    ) {
      return;
    }
    setError('');
    setIsRelockingPrevious(true);
    try {
      const result = await apiFetch('/api/customers/relock-previous', { method: 'POST' });
      await fetchCustomers();
      setRestorePendingCount(Number(result.pending_count) || 0);
      if (isModalOpen && editId) {
        try {
          const updated = await apiFetch(`/api/customers/${editId}`);
          setForm((prev) => ({
            ...prev,
            is_locked_finance: !!updated.is_locked_finance,
            is_locked_marketing: !!updated.is_locked_marketing,
          }));
        } catch {
          /* ignore */
        }
      }
      alert(result.message || `Berhasil mengunci kembali ${result.locked_count} customer.`);
    } catch (err) {
      setError(err.message);
      alert(err.message);
    } finally {
      setIsRelockingPrevious(false);
    }
  };

  const handleLockAllCustomers = async () => {
    const unlockedCount = customers.filter((c) => !c.is_locked_finance).length;
    if (unlockedCount === 0) {
      alert('Semua Master Customer sudah terkunci Finance.');
      return;
    }
    if (
      !window.confirm(
        `Kunci Finance (Final) untuk SEMUA Master Customer?\n\n${unlockedCount} customer akan dikunci Finance.\nKunci Marketing ikut diaktifkan jika belum aktif.\nTindakan ini tidak dapat dibatalkan.`
      )
    ) {
      return;
    }
    setError('');
    setIsLockingAll(true);
    try {
      const result = await apiFetch('/api/customers/lock-all', { method: 'POST' });
      await fetchCustomers();
      setRestorePendingCount(0);
      if (isModalOpen && editId) {
        setForm((prev) => ({
          ...prev,
          is_locked_finance: true,
          is_locked_marketing: true,
        }));
      }
      alert(result.message || `Berhasil mengunci Finance ${result.locked_count} customer.`);
    } catch (err) {
      setError(err.message);
      alert(err.message);
    } finally {
      setIsLockingAll(false);
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

  const PAGE_SIZE = 15;
  const totalPages = Math.max(1, Math.ceil(displayCustomers.length / PAGE_SIZE));
  const safePage = Math.max(1, Math.min(page, totalPages));
  const paginatedCustomers = displayCustomers.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE
  );

  return (
    <div>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ background: 'none', WebkitTextFillColor: 'initial', color: 'var(--text-primary)' }}>
            Daftar Customer
          </h1>
          <p>Master data customer. Kode customer harus unik; nama boleh sama.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            style={{ display: 'none' }}
            onChange={handleImportExcel}
          />
          {user?.role === 'admin' && (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleLockAllCustomers}
                disabled={
                  isLockingAll || isUnlockingAll || isRelockingPrevious || loadingCustomers
                }
                title="Kunci Finance (Final) untuk semua Master Customer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  color: '#b45309',
                  borderColor: 'rgba(245, 158, 11, 0.4)',
                  background: 'rgba(245, 158, 11, 0.08)',
                }}
              >
                <Lock size={18} />
                {isLockingAll ? 'Mengunci...' : 'Kunci Finance Semua'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleUnlockAllCustomers}
                disabled={
                  isUnlockingAll || isLockingAll || isRelockingPrevious || loadingCustomers
                }
                title="Buka kunci Finance (Final) untuk semua Master Customer (simpan daftar untuk kunci kembali)"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  color: '#dc2626',
                  borderColor: 'rgba(220, 38, 38, 0.35)',
                  background: 'rgba(220, 38, 38, 0.06)',
                }}
              >
                <Unlock size={18} />
                {isUnlockingAll ? 'Membuka...' : 'Buka Kunci Finance Semua'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleRelockPreviousCustomers}
                disabled={
                  isRelockingPrevious ||
                  isLockingAll ||
                  isUnlockingAll ||
                  loadingCustomers
                }
                title={
                  restorePendingCount > 0
                    ? `Kunci kembali ${restorePendingCount} customer yang sebelumnya terkunci Finance`
                    : 'Belum ada antrian. Klik "Buka Kunci Finance Semua" dulu sebelum sync, lalu tombol ini aktif.'
                }
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  color: restorePendingCount > 0 ? '#047857' : '#6b7280',
                  borderColor:
                    restorePendingCount > 0
                      ? 'rgba(4, 120, 87, 0.35)'
                      : 'rgba(107, 114, 128, 0.35)',
                  background:
                    restorePendingCount > 0
                      ? 'rgba(4, 120, 87, 0.08)'
                      : 'rgba(107, 114, 128, 0.06)',
                }}
              >
                <Lock size={18} />
                {isRelockingPrevious
                  ? 'Mengunci kembali...'
                  : restorePendingCount > 0
                    ? `Kunci Kembali Sebelumnya (${restorePendingCount})`
                    : 'Kunci Kembali Sebelumnya'}
              </button>
            </>
          )}
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

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div style={{ position: 'relative', width: '100%', maxWidth: '400px' }}>
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
            style={{ paddingLeft: '2.8rem', background: 'rgba(255,255,255,0.05)', width: '100%' }}
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <TablePager 
          page={safePage} 
          pageSize={PAGE_SIZE} 
          onPageChange={setPage} 
          totalItems={displayCustomers.length}
          label="customer"
        />
      </div>

      <div className="table-container glass-panel" style={{ padding: 0 }}>
        <table className="glass-table">
          <thead>
            <tr>
              <SortableTh label="KODE" column="code" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <SortableTh label="NAMA" column="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
              <SortableTh label="LOCK" column="is_locked_finance" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
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
                <td colSpan={canWrite ? 8 : 7} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                  Memuat data customer...
                </td>
              </tr>
            ) : (
              paginatedCustomers.map((c) => {
              const coords = formatCustomerCoords(c.latitude, c.longitude);
              return (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>{c.code || '-'}</td>
                <td>
                  <div style={{ fontWeight: 500 }}>{c.name}</div>
                  {c.updated_at && c.updated_by_name && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                      <Clock size={10} />
                      Diperbarui {new Date(c.updated_at).toLocaleString('id-ID')} oleh {c.updated_by_name}
                    </div>
                  )}
                </td>
                <td>
                  {c.is_locked_finance ? (
                    <span className="badge" style={{ background: 'rgba(220, 38, 38, 0.1)', color: '#dc2626', border: '1px solid rgba(220, 38, 38, 0.2)' }}>Final</span>
                  ) : c.is_locked_marketing ? (
                    <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.2)' }}>Marketing</span>
                  ) : (
                    <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)' }}>Open</span>
                  )}
                </td>
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
                <td colSpan={canWrite ? 8 : 7} style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}>
                  Tidak ada data customer
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {isModalOpen && canWrite && (() => {
        const initialCustomer = customers.find(c => c.id === editId);
        const initLockedFinance = initialCustomer?.is_locked_finance || false;
        const initLockedMarketing = initialCustomer?.is_locked_marketing || false;

        return (
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
                <fieldset
                  disabled={
                    (initLockedFinance && !canUnlockFinanceLock)
                    || (user?.role === 'marketing' && form.is_locked_marketing)
                  }
                  style={{ border: 'none', padding: 0, margin: 0 }}
                >
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
                            value={form.share_location}
                            onChange={(e) => setForm({ ...form, share_location: e.target.value })}
                          />
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={handleParseShareLocation}
                            disabled={parsingShare || !(form.share_location || '').trim()}
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
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                            <input
                              type="checkbox"
                              checked={forceToll}
                              onChange={(e) => setForceToll(e.target.checked)}
                              disabled={form.is_locked_finance}
                            />
                            Asumsikan lewat jalan Tol
                          </label>
                          {form.is_locked_finance && (
                            <span style={{ fontSize: '0.8rem', color: '#b45309', fontWeight: 600 }}>
                              Tombol Refresh muncul setelah Buka Kunci Finance
                            </span>
                          )}
                          {routeRefreshNeeded && !form.is_locked_finance && (
                            <button
                              type="button"
                              className="btn btn-primary"
                              style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
                              onClick={handleRefreshRouteBbmTol}
                              disabled={tollManualLoading || routeLoading || !hasCoords}
                            >
                              {tollManualLoading || routeLoading
                                ? 'Refresh...'
                                : 'Refresh rute, BBM & Tol'}
                            </button>
                          )}
                          {routeInfo && !form.is_locked_finance && !routeRefreshNeeded && (
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
                        {form.is_locked_finance
                          ? 'Finance terkunci — BBM, Tol, dan ruas tol tidak dihitung ulang. Buka kunci Finance untuk refresh rute.'
                          : routeRefreshNeeded
                            ? 'Kunci Finance sudah dibuka. Klik "Refresh rute, BBM & Tol" jika ingin menghitung ulang dari rute terbaru.'
                            : 'BBM & Tol dihitung otomatis dari rute (tidak bisa diubah manual). Uang Mel diisi otomatis dari master jenis kendaraan. Parkir & Lain-lain diisi manual. Uang jalan = BBM + Tol + Uang Mel + Parkir + Lain-lain.'}
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

                    {routeInfo && form.is_locked_finance && (
                      <div
                        style={{
                          marginBottom: '0.75rem',
                          padding: '0.65rem 0.85rem',
                          borderRadius: '8px',
                          border: '1px solid #fecaca',
                          background: '#fef2f2',
                          fontSize: '0.85rem',
                          color: '#991b1b',
                        }}
                      >
                        Finance terkunci — BBM/Tol &amp; ruas tidak dihitung ulang. Buka kunci lalu klik Refresh bila perlu update.
                      </div>
                    )}

                    {routeInfo && (
                      <>
                        {routeInfo.distance_km != null && !form.is_locked_finance && (
                        <div className="form-group" style={{ marginBottom: '1rem' }}>
                          <label className="form-label" style={{ fontSize: '0.75rem', marginBottom: '0.35rem' }}>
                            Skema Rute / Koridor Tol
                          </label>
                          <div
                            className="form-input"
                            style={{
                              background: 'rgba(255,255,255,0.6)',
                              color: 'var(--text-secondary)',
                            }}
                          >
                            {manualTollOverride
                              ? 'Manual (ikuti ruas tol yang dipilih)'
                              : 'Otomatis (rute tercepat OSRM)'}
                          </div>
                          <small style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', display: 'block', marginTop: '0.35rem' }}>
                            {manualTollOverride
                              ? 'Tarif tol mengikuti ruas manual. Default jarak = OSRM koridor (ikut peta). Tombol "Jarak langsung" ≈ Google Maps (gratis).'
                              : 'Default jarak = OSRM rute tercepat. Tombol "Jarak langsung" menghitung ulang tanpa memaksa koridor tol.'}
                          </small>
                        </div>
                        )}

                        {routeInfo.distance_km != null && (
                        <>
                        {manualTollOverride && routeInfo.route_via_toll_gates && (
                          <div
                            style={{
                              marginBottom: '0.75rem',
                              padding: '0.65rem 0.85rem',
                              borderRadius: '8px',
                              border: '1px solid #fde68a',
                              background: '#fffbeb',
                              fontSize: '0.85rem',
                              color: '#92400e',
                            }}
                          >
                            Garis biru = jalur via gerbang tol (visual). Garis oranye = ruas tol. Jarak default = OSRM.
                          </div>
                        )}

                        {manualTollOverride && !routeInfo.route_via_toll_gates && (
                          <div
                            style={{
                              marginBottom: '0.75rem',
                              padding: '0.65rem 0.85rem',
                              borderRadius: '8px',
                              border: '1px solid #fde68a',
                              background: '#fffbeb',
                              fontSize: '0.85rem',
                              color: '#92400e',
                            }}
                          >
                            Ruas tol manual aktif. Koordinat gerbang belum lengkap — jarak masih dari rute OSRM langsung.
                          </div>
                        )}

                        {routeInfo.route_selection === 'tol_termurah' && (
                          <div
                            style={{
                              marginBottom: '0.75rem',
                              padding: '0.65rem 0.85rem',
                              borderRadius: '8px',
                              border: '1px solid #bfdbfe',
                              background: '#eff6ff',
                              fontSize: '0.85rem',
                              color: '#1d4ed8',
                            }}
                          >
                            Rute tol termurah dipilih dari{' '}
                            {routeInfo.alternatives_compared || 0} alternatif OSRM.
                            {routeInfo.toll_savings_idr > 0 && (
                              <>
                                {' '}
                                Hemat {formatIDR(routeInfo.toll_savings_idr)} vs rute tercepat.
                              </>
                            )}
                          </div>
                        )}

                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(2, 1fr)',
                            gap: '0.75rem',
                            marginBottom: '0.75rem',
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
                            <p
                              style={{
                                margin: '0.35rem 0 0',
                                fontSize: '0.72rem',
                                color:
                                  routeInfo.distance_source === 'google'
                                    ? '#1d4ed8'
                                    : routeInfo.distance_source === 'osrm_direct'
                                      ? '#0369a1'
                                      : '#64748b',
                                fontWeight: 600,
                              }}
                            >
                              Dipakai BBM:{' '}
                              {distanceSourceLabel(
                                routeInfo.distance_source,
                                routeInfo.route_via_toll_gates
                              )}
                            </p>
                            {(routeInfo.distance_km_route != null ||
                              routeInfo.distance_km_direct != null) && (
                              <div
                                style={{
                                  marginTop: '0.55rem',
                                  paddingTop: '0.45rem',
                                  borderTop: '1px dashed var(--glass-border)',
                                  fontSize: '0.72rem',
                                  color: 'var(--text-secondary)',
                                  lineHeight: 1.45,
                                }}
                              >
                                <div>
                                  Rute/peta:{' '}
                                  <strong>
                                    {(routeInfo.distance_km_route ?? routeInfo.distance_km).toLocaleString('id-ID')} km
                                  </strong>
                                </div>
                                <div>
                                  Langsung ≈ Google:{' '}
                                  <strong>
                                    {(routeInfo.distance_km_direct ?? routeInfo.distance_km).toLocaleString('id-ID')} km
                                  </strong>
                                </div>
                              </div>
                            )}
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

                        <div
                          style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '0.5rem',
                            marginBottom: '1rem',
                          }}
                        >
                          <button
                            type="button"
                            className="btn btn-secondary"
                            disabled={distanceLoading || routeLoading}
                            onClick={() => recalculateDistanceWithProvider('osrm')}
                            title={
                              manualTollOverride
                                ? 'Jarak mengikuti koridor/peta OSRM (default skema manual)'
                                : 'Jarak OSRM rute tercepat (default skema otomatis)'
                            }
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              fontSize: '0.85rem',
                              borderColor:
                                !routeInfo.distance_source ||
                                routeInfo.distance_source === 'osrm'
                                  ? 'rgba(4, 120, 87, 0.4)'
                                  : undefined,
                              background:
                                !routeInfo.distance_source ||
                                routeInfo.distance_source === 'osrm'
                                  ? 'rgba(4, 120, 87, 0.08)'
                                  : undefined,
                              color:
                                !routeInfo.distance_source ||
                                routeInfo.distance_source === 'osrm'
                                  ? '#047857'
                                  : undefined,
                            }}
                          >
                            <RefreshCw size={15} />
                            {distanceLoading &&
                            (!routeInfo.distance_source ||
                              routeInfo.distance_source === 'osrm')
                              ? 'Menghitung...'
                              : manualTollOverride
                                ? 'OSRM koridor (default)'
                                : 'OSRM (default)'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            disabled={distanceLoading || routeLoading}
                            onClick={() => recalculateDistanceWithProvider('osrm_direct')}
                            title="Jarak OSRM langsung — mendekati Google Maps, gratis (tanpa API key)"
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              fontSize: '0.85rem',
                              borderColor:
                                routeInfo.distance_source === 'osrm_direct'
                                  ? 'rgba(3, 105, 161, 0.45)'
                                  : 'rgba(3, 105, 161, 0.3)',
                              background:
                                routeInfo.distance_source === 'osrm_direct'
                                  ? 'rgba(3, 105, 161, 0.1)'
                                  : 'rgba(3, 105, 161, 0.06)',
                              color: '#0369a1',
                            }}
                          >
                            <MapPin size={15} />
                            {distanceLoading && routeInfo.distance_source === 'osrm_direct'
                              ? 'Menghitung...'
                              : 'Jarak langsung (≈ Google)'}
                          </button>
                        </div>
                        </>
                        )}
                        <LocationPickerMap
                          key={`${form.latitude}-${form.longitude}-${routeInfo?.geometry?.length || 0}-${routeInfo?.route_profile || 'auto'}`}
                          latitude={form.latitude}
                          longitude={form.longitude}
                          onLocationChange={(lat, lng) => {
                            if (form.is_locked_finance) return;
                            setForm({ ...form, latitude: String(lat), longitude: String(lng) });
                          }}
                          origin={routeInfo?.origin || null}
                          geometry={routeInfo?.geometry || []}
                          tollRoads={routeInfo?.toll_roads || []}
                          showTollPolylines
                          height="calc(100vh - 520px)"
                        />

                        <RouteTollGateInfo
                          segments={routeInfo.toll_breakdown}
                          tollSource={routeInfo.toll_source}
                          tollNote={routeInfo.toll_note}
                          editable={canWrite && !form.is_locked_finance}
                          tollSections={tollSections}
                          tollLoading={tollManualLoading}
                          onSegmentReplace={replaceTollSegmentAt}
                          onSegmentAdd={addTollSegment}
                          onSegmentRemove={removeTollSegmentAt}
                          onClearAll={clearAllTollSegments}
                          onFillFromMap={refillRouteFromMap}
                        />

                        <TollEstimateTable
                          items={routeInfo.toll_by_vehicle}
                          isEstimate={routeInfo.toll_is_estimate}
                          tollSource={routeInfo.toll_source}
                        />
                      </>
                    )}

                    {!routeInfo && (
                      <LocationPickerMap
                        key={`${form.latitude}-${form.longitude}-empty`}
                        latitude={form.latitude}
                        longitude={form.longitude}
                        onLocationChange={(lat, lng) => setForm({ ...form, latitude: String(lat), longitude: String(lng) })}
                        height="calc(100vh - 520px)"
                      />
                    )}
                  </div>
                </div>
                </fieldset>
              </div>
              <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input 
                      type="checkbox" 
                      id="is_locked_marketing" 
                      checked={form.is_locked_marketing} 
                      disabled={initLockedFinance && !canUnlockFinanceLock}
                      onChange={(e) => setForm({ ...form, is_locked_marketing: e.target.checked })}
                    />
                    <label htmlFor="is_locked_marketing" style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, color: form.is_locked_marketing ? '#dc2626' : 'var(--text-secondary)' }}>
                      Kunci Marketing
                    </label>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      id="is_locked_finance"
                      checked={form.is_locked_finance}
                      disabled={
                        !canManageFinanceLock
                        || (initLockedFinance && !canUnlockFinanceLock)
                        || !form.is_locked_marketing
                      }
                      onChange={(e) => {
                        if (!canManageFinanceLock) return;
                        const next = e.target.checked;
                        if (!next && initLockedFinance && !canUnlockFinanceLock) return;
                        setForm({ ...form, is_locked_finance: next });
                        // Buka kunci via checkbox → tampilkan tombol refresh (jangan auto-recalc).
                        if (!next && initLockedFinance) {
                          setRouteRefreshNeeded(true);
                        }
                        if (next) {
                          setRouteRefreshNeeded(false);
                        }
                      }}
                      title={
                        !canManageFinanceLock
                          ? 'Tidak berwenang. Atur di Matriks Akses → Kunci Finance Customer'
                          : !form.is_locked_marketing
                            ? 'Aktifkan Kunci Marketing terlebih dahulu'
                            : undefined
                      }
                    />
                    <label
                      htmlFor="is_locked_finance"
                      style={{
                        cursor: canManageFinanceLock ? 'pointer' : 'not-allowed',
                        fontSize: '0.9rem',
                        fontWeight: 500,
                        color: form.is_locked_finance ? '#dc2626' : 'var(--text-secondary)',
                        opacity: canManageFinanceLock ? 1 : 0.75,
                      }}
                      title={
                        !canManageFinanceLock
                          ? 'Tidak berwenang. Atur di Matriks Akses → Kunci Finance Customer'
                          : undefined
                      }
                    >
                      Kunci Finance (Final)
                    </label>
                  </div>
                  {canUnlockFinanceLock && editId && initLockedFinance && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{
                        padding: '0.4rem 0.75rem',
                        fontSize: '0.85rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        color: '#dc2626',
                        borderColor: 'rgba(220, 38, 38, 0.35)',
                        background: 'rgba(220, 38, 38, 0.06)',
                      }}
                      disabled={isUnlocking || isSubmitting || isUnlockingAll || isLockingAll}
                      onClick={handleUnlockFinance}
                      title="Buka kunci Finance (Final) — Admin / Finance"
                    >
                      <Unlock size={14} />
                      {isUnlocking ? 'Membuka...' : 'Buka Kunci Finance'}
                    </button>
                  )}
                  {routeRefreshNeeded && !form.is_locked_finance && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      style={{
                        padding: '0.4rem 0.75rem',
                        fontSize: '0.85rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                      disabled={tollManualLoading || routeLoading || !hasCoords || isSubmitting}
                      onClick={handleRefreshRouteBbmTol}
                      title="Hitung ulang rute, ruas tol, BBM & Tol dari peta"
                    >
                      {tollManualLoading || routeLoading ? 'Refresh...' : 'Refresh rute, BBM & Tol'}
                    </button>
                  )}
                </div>
                <button type="button" className="btn btn-secondary" onClick={closeModal}>
                  Batal
                </button>
                {!(initLockedFinance && !canUnlockFinanceLock) && (
                  <button 
                    type="button"
                    className="btn btn-primary" 
                    style={{ background: '#4f46e5' }}
                    disabled={isSubmitting}
                    onClick={handleSubmit}
                  >
                    {isSubmitting ? 'Menyimpan...' : (editId ? 'Simpan' : 'Tambah')}
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
        );
      })()}
    </div>
  );
};

export default Customers;
