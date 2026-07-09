import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Plus, Trash2, Edit2, RefreshCw, ArrowUp, ArrowDown, ArrowUpDown, Download, Upload, Search } from 'lucide-react';
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
  const [searchTerm, setSearchTerm] = useState('');
  const [sortCol, setSortCol] = useState('sort_order');
  const [sortDir, setSortDir] = useState('asc');
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

  const handleExportJson = async () => {
    try {
      const data = await apiFetch('/api/toll-data/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ruas_tol_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Gagal export: ' + err.message);
    }
  };

  const handleImportClick = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (!window.confirm('PERINGATAN: Import akan MENGHAPUS seluruh data ruas & gerbang tol yang ada di server dan menggantinya dengan data dari file JSON. Lanjutkan?')) {
      e.target.value = null;
      return;
    }

    setImporting(true);
    setError('');
    setSyncInfo(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      
      await apiFetch('/api/toll-data/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      setSyncInfo({ source_title: 'File JSON', sections: { total: payload.sections.length, created: 0, updated: payload.sections.length } });
      await fetchGolongan();
      await fetchSections();
      alert('Import berhasil.');
    } catch (err) {
      setError('Gagal import: ' + err.message);
    } finally {
      setImporting(false);
      e.target.value = null;
    }
  };

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

  const matchesSearch = (row, term) => {
    if (!term) return true;
    const haystack = [
      row.name,
      row.network,
      row.origin_name,
      row.destination_name,
      routeLabel(row),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return haystack.includes(term);
  };

  const sortedSections = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    const filtered = sections.filter((s) => {
      if (filterNetwork && (s.network || '').trim() !== filterNetwork) return false;
      return matchesSearch(s, term);
    });

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
  }, [sections, filterNetwork, searchTerm, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedSections.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    setPage(1);
  }, [sections.length, filterNetwork, searchTerm]);

  const paginatedSections = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return sortedSections.slice(start, start + PAGE_SIZE);
  }, [sortedSections, safePage]);

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: '300px', maxWidth: '500px' }}>
          <h1 style={{ marginBottom: '0.5rem' }}>Ruas &amp; Tarif Tol</h1>
          <p style={{ margin: 0, lineHeight: '1.4' }}>
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
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'nowrap', alignItems: 'center' }}>
          {canWrite && (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate('/toll-sections/new')}
                style={{ whiteSpace: 'nowrap' }}
              >
                <Plus size={18} /> Tambah Ruas
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSyncBpjt}
                disabled={syncing || importing}
                style={{ whiteSpace: 'nowrap' }}
              >
                <RefreshCw size={18} />
                {syncing ? 'Mengimpor...' : 'Impor BPJT'}
              </button>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleExportJson}
                style={{ whiteSpace: 'nowrap' }}
                title="Unduh data master ke file JSON"
              >
                <Download size={18} /> Export JSON
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleImportClick}
                disabled={importing || syncing}
                style={{ whiteSpace: 'nowrap', color: '#b45309' }}
                title="Unggah dan timpa data master dari file JSON"
              >
                <Upload size={18} /> {importing ? 'Mengimpor JSON...' : 'Import JSON'}
              </button>
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept="application/json"
                onChange={handleFileChange}
              />
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
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem', flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label htmlFor="filter-network" className="form-label" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>
              Jaringan
            </label>
            <select
              id="filter-network"
              className="form-input"
              value={filterNetwork}
              onChange={(e) => {
                setFilterNetwork(e.target.value);
                setPage(1);
              }}
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
          <div style={{ position: 'relative', flex: 1, minWidth: '220px', maxWidth: '360px' }}>
            <Search
              size={18}
              style={{
                position: 'absolute',
                left: '0.75rem',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-secondary)',
                pointerEvents: 'none',
              }}
            />
            <input
              id="search-ruas-tol"
              type="search"
              className="form-input"
              placeholder="Cari ruas tol, asal/tujuan..."
              style={{ paddingLeft: '2.5rem', marginBottom: 0, width: '100%' }}
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
            />
          </div>
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
                  {sections.length === 0
                    ? 'Belum ada ruas tol'
                    : 'Tidak ada ruas tol yang cocok dengan pencarian'}
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
