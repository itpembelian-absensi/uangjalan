import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Plus, Trash2, Edit2, RefreshCw, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { apiFetch } from '../api';
import {
  useCrudWrite,
  CrudActionsHeader,
  CrudActionsCell,
} from '../components/CrudWriteAccess';
import TablePager from '../components/TablePager';

const PAGE_SIZE = 15;

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const RATE_GROUPS = [
  { key: 'I', codes: ['I'], label: 'Gol I' },
  { key: 'II_III', codes: ['II', 'III'], label: 'Gol II & III' },
  { key: 'IV_V', codes: ['IV', 'V'], label: 'Gol IV & V' },
];

/* ---------- Sortable column definitions ---------- */
const SORT_COLUMNS = [
  { id: 'sort_order', label: 'Urutan' },
  { id: 'network', label: 'Tol Trans' },
  { id: 'name', label: 'Ruas Tol' },
  { id: 'route', label: 'Asal → Tujuan' },
  { id: 'length_km', label: 'Panjang (km)', align: 'right' },
];

const SortIcon = ({ active, dir }) => {
  if (!active) return <ArrowUpDown size={13} style={{ opacity: 0.35, marginLeft: 4 }} />;
  return dir === 'asc'
    ? <ArrowUp size={13} style={{ marginLeft: 4, color: '#4f46e5' }} />
    : <ArrowDown size={13} style={{ marginLeft: 4, color: '#4f46e5' }} />;
};

const SortableTh = ({ column, sortCol, sortDir, onSort, style }) => (
  <th
    style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap', ...style }}
    onClick={() => onSort(column.id)}
    title={`Urutkan berdasarkan ${column.label}`}
  >
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      {column.label}
      <SortIcon active={sortCol === column.id} dir={sortDir} />
    </span>
  </th>
);

/* ---------- Component ---------- */
const TollSections = () => {
  const canWrite = useCrudWrite();
  const navigate = useNavigate();
  const [sections, setSections] = useState([]);
  const [golonganList, setGolonganList] = useState([]);
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncInfo, setSyncInfo] = useState(null);
  const [page, setPage] = useState(1);
  const [filterNetwork, setFilterNetwork] = useState('');
  const [sortCol, setSortCol] = useState('sort_order');
  const [sortDir, setSortDir] = useState('asc');

  const fetchGolongan = async () => {
    const data = await apiFetch('/api/toll-golongan');
    setGolonganList(data);
    return data;
  };

  const fetchSections = async () => {
    const data = await apiFetch('/api/toll-sections');
    setSections(data);
    setError('');
  };

  useEffect(() => {
    (async () => {
      try {
        await fetchGolongan();
        await fetchSections();
      } catch (err) {
        setError(err.message);
      }
    })();
  }, []);

  const handleSyncBpjt = async () => {
    if (!window.confirm('Impor tarif ruas tol Jabodetabek dari BPJT? Data ruas yang sama akan diperbarui.')) return;
    setSyncing(true);
    setError('');
    setSyncInfo(null);
    try {
      const result = await apiFetch('/api/toll-sections/sync-bpjt-jabodetabek', { method: 'POST' });
      setSyncInfo(result);
      await fetchGolongan();
      await fetchSections();
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Hapus ruas tol "${row.name}"?`)) return;
    setError('');
    try {
      await apiFetch(`/api/toll-sections/${row.id}`, { method: 'DELETE' });
      await fetchSections();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSort = useCallback((col) => {
    setSortCol((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setSortDir('asc');
      return col;
    });
    setPage(1);
  }, []);

  const activeGolongan = golonganList.filter((g) => g.is_active);
  const tableGolonganGroups = RATE_GROUPS.map((group) => ({
    ...group,
    golongan: group.codes
      .map((code) => activeGolongan.find((g) => g.code === code))
      .filter(Boolean),
  })).filter((g) => g.golongan.length > 0);

  const rateForGroup = (row, group) => {
    for (const g of group.golongan) {
      const rate = (row.rates || []).find((r) => r.golongan_id === g.id);
      if (rate) return rate.rate;
    }
    return null;
  };

  const routeLabel = (row) => {
    if (row.origin_name && row.destination_name) {
      return `${row.origin_name} → ${row.destination_name}`;
    }
    if (row.origin_name) return row.origin_name;
    if (row.destination_name) return row.destination_name;
    return '—';
  };

  const networkOptions = useMemo(() => {
    const set = new Set(sections.map((s) => (s.network || '').trim()).filter(Boolean));
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [sections]);

  const sortedSections = useMemo(() => {
    const filtered = filterNetwork
      ? sections.filter((s) => (s.network || '').trim() === filterNetwork)
      : sections;

    const cmp = (a, b) => {
      let va, vb;
      switch (sortCol) {
        case 'sort_order':
          va = a.sort_order ?? 0;
          vb = b.sort_order ?? 0;
          return va - vb;
        case 'network':
          va = (a.network || '').toLowerCase();
          vb = (b.network || '').toLowerCase();
          return va.localeCompare(vb, 'id');
        case 'name':
          return (a.name || '').localeCompare(b.name || '', 'id');
        case 'route': {
          const ra = routeLabel(a);
          const rb = routeLabel(b);
          return ra.localeCompare(rb, 'id');
        }
        case 'length_km':
          va = Number(a.length_km) || 0;
          vb = Number(b.length_km) || 0;
          return va - vb;
        default:
          return 0;
      }
    };

    return [...filtered].sort((a, b) => {
      const result = cmp(a, b);
      return sortDir === 'asc' ? result : -result;
    });
  }, [sections, filterNetwork, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedSections.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    setPage(1);
  }, [sections.length, filterNetwork]);

  const paginatedSections = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return sortedSections.slice(start, start + PAGE_SIZE);
  }, [sortedSections, safePage]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Ruas &amp; Tarif Tol</h1>
          <p>
            Master ruas tol sesuai acuan BPJT: jaringan, ruas, asal/tujuan, dan tarif per golongan.
            Matriks gerbang detail di{' '}
            <Link to="/toll-golongan" style={{ color: '#4f46e5' }}>
              Golongan Tol
            </Link>{' '}
            &amp;{' '}
            <Link to="/toll-gates" style={{ color: '#4f46e5' }}>
              Gerbang Tol
            </Link>
            .
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {canWrite && (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate('/toll-sections/new')}
              >
                <Plus size={18} /> Tambah Ruas
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSyncBpjt}
                disabled={syncing}
                style={{ whiteSpace: 'nowrap' }}
              >
                <RefreshCw size={18} />
                {syncing ? 'Mengimpor BPJT...' : 'Impor dari BPJT'}
              </button>
            </>
          )}
        </div>
      </div>

      {syncInfo && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: '#ecfdf5',
            color: '#065f46',
            border: '1px solid #a7f3d0',
            fontSize: '0.9rem',
          }}
        >
          Impor BPJT selesai: {syncInfo.sections?.total ?? syncInfo.total} ruas (
          {syncInfo.sections?.created ?? syncInfo.created} baru,{' '}
          {syncInfo.sections?.updated ?? syncInfo.updated} diperbarui)
          {syncInfo.gates && (
            <>
              {' '}
              · {syncInfo.gates.sections_imported} matriks gerbang, {syncInfo.gates.fares_created}{' '}
              tarif pasangan
            </>
          )}
          . Sumber:{' '}
          <a
            href={syncInfo.sections?.source_page || syncInfo.source_page}
            target="_blank"
            rel="noreferrer"
            style={{ color: '#047857' }}
          >
            {syncInfo.sections?.source_title || syncInfo.source_title || 'BPJT'}
          </a>
          {(syncInfo.sections?.pdf_url || syncInfo.pdf_url) && (
            <>
              {' '}
              ·{' '}
              <a
                href={syncInfo.sections?.pdf_url || syncInfo.pdf_url}
                target="_blank"
                rel="noreferrer"
                style={{ color: '#047857' }}
              >
                PDF resmi
              </a>
            </>
          )}
        </div>
      )}

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

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
          marginBottom: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label htmlFor="filter-network" className="form-label" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>
            Jaringan
          </label>
          <select
            id="filter-network"
            className="form-input"
            value={filterNetwork}
            onChange={(e) => setFilterNetwork(e.target.value)}
            style={{ minWidth: '180px', marginBottom: 0 }}
          >
            <option value="">Semua jaringan</option>
            {networkOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <TablePager
          page={safePage}
          pageSize={PAGE_SIZE}
          totalItems={sortedSections.length}
          onPageChange={setPage}
          label="Ruas"
        />
      </div>

      <div className="table-container glass-panel" style={{ padding: 0, overflowX: 'auto', marginTop: '0.5rem' }}>
        <table className="glass-table">
          <thead>
            <tr>
              {SORT_COLUMNS.map((col) => (
                <SortableTh
                  key={col.id}
                  column={col}
                  sortCol={sortCol}
                  sortDir={sortDir}
                  onSort={handleSort}
                  style={col.align ? { textAlign: col.align } : undefined}
                />
              ))}
              {tableGolonganGroups.map((g) => (
                <th key={g.key} style={{ textAlign: 'right' }}>
                  {g.label}
                </th>
              ))}
              <th>Status</th>
              <CrudActionsHeader canWrite={canWrite} />
            </tr>
          </thead>
          <tbody>
            {paginatedSections.map((row) => (
              <tr key={row.id}>
                <td>{row.sort_order}</td>
                <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {row.network || '—'}
                </td>
                <td style={{ fontWeight: 500 }}>{row.name}</td>
                <td style={{ fontSize: '0.85rem' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                    {routeLabel(row)}
                  </span>
                </td>
                <td style={{ textAlign: 'right' }}>{Number(row.length_km).toLocaleString('id-ID')}</td>
                {tableGolonganGroups.map((g) => {
                  const amount = rateForGroup(row, g);
                  return (
                    <td key={g.key} style={{ textAlign: 'right', fontSize: '0.85rem' }}>
                      {amount != null ? formatIDR(amount) : '-'}
                    </td>
                  );
                })}
                <td>
                  {row.is_active ? (
                    <span className="badge badge-green">Aktif</span>
                  ) : (
                    <span className="badge badge-red">Non-Aktif</span>
                  )}
                </td>
                <CrudActionsCell canWrite={canWrite}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.4rem 0.6rem', marginRight: '0.35rem' }}
                    onClick={() => navigate(`/toll-sections/${row.id}/edit`)}
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    style={{ padding: '0.4rem 0.6rem' }}
                    onClick={() => handleDelete(row)}
                  >
                    <Trash2 size={16} />
                  </button>
                </CrudActionsCell>
              </tr>
            ))}
            {sortedSections.length === 0 && (
              <tr>
                <td
                  colSpan={(canWrite ? 6 : 5) + tableGolonganGroups.length}
                  style={{ textAlign: 'center', opacity: 0.5, padding: '2rem' }}
                >
                  Belum ada ruas tol
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {sortedSections.length > PAGE_SIZE && (
        <div style={{ marginTop: '0.5rem' }}>
          <TablePager
            page={safePage}
            pageSize={PAGE_SIZE}
            totalItems={sortedSections.length}
            onPageChange={setPage}
            label="Ruas"
          />
        </div>
      )}
    </div>
  );
};

export default TollSections;
