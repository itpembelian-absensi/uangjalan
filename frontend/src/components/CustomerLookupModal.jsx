import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, ChevronsLeft, ChevronLeft, ChevronRight, ChevronsRight } from 'lucide-react';

const PAGE_SIZE = 15;

const formatCustomerCoords = (latitude, longitude) => {
  if (latitude == null || longitude == null) return null;
  const lat = Number(latitude);
  const lng = Number(longitude);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  return { lat: lat.toFixed(7), lng: lng.toFixed(7) };
};

const DEFAULT_SEARCH_FIELD = 'name';

const SEARCH_FIELDS = [
  { id: 'code', label: 'Kode Customer' },
  { id: 'name', label: 'Nama Customer' },
  { id: 'city', label: 'Kota/Kabupaten' },
  { id: 'phone', label: 'Telepon' },
];

const filterByField = (customer, field, term) => {
  if (!term) return true;
  const q = term.trim().toLowerCase();
  const raw = customer[field];
  if (raw == null || raw === '') return false;
  return String(raw).toLowerCase().includes(q);
};

const clampModalPosition = (x, y, width, height) => {
  const pad = 12;
  const maxX = Math.max(pad, window.innerWidth - width - pad);
  const maxY = Math.max(pad, window.innerHeight - height - pad);
  return {
    x: Math.min(Math.max(pad, x), maxX),
    y: Math.min(Math.max(pad, y), maxY),
  };
};

const measureCenteredPosition = (el) => {
  const width = el.offsetWidth;
  const height = el.offsetHeight;
  return clampModalPosition(
    (window.innerWidth - width) / 2,
    (window.innerHeight - height) / 2,
    width,
    height,
  );
};

const CustomerLookupModal = ({
  open,
  onClose,
  customers = [],
  onSelect,
  excludeIds = [],
  title = 'Pilih Customer',
}) => {
  const [searchBy, setSearchBy] = useState(DEFAULT_SEARCH_FIELD);
  const [searchInput, setSearchInput] = useState('');
  const [appliedTerm, setAppliedTerm] = useState('');
  const [appliedField, setAppliedField] = useState(DEFAULT_SEARCH_FIELD);
  const [page, setPage] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const modalRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setSearchBy(DEFAULT_SEARCH_FIELD);
    setSearchInput('');
    setAppliedTerm('');
    setAppliedField(DEFAULT_SEARCH_FIELD);
    setPage(1);
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !modalRef.current) return;
    const place = () => {
      if (!modalRef.current) return;
      setPosition(measureCenteredPosition(modalRef.current));
    };
    place();
    const raf = requestAnimationFrame(place);
    window.addEventListener('resize', place);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', place);
    };
  }, [open]);

  const excluded = useMemo(() => new Set(excludeIds.map((id) => String(id))), [excludeIds]);

  const filtered = useMemo(() => {
    return customers.filter((c) => {
      if (excluded.has(String(c.id))) return false;
      return filterByField(c, appliedField, appliedTerm);
    });
  }, [customers, excluded, appliedField, appliedTerm]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const rangeStart = filtered.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(safePage * PAGE_SIZE, filtered.length);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const runSearch = () => {
    setAppliedField(searchBy);
    setAppliedTerm(searchInput);
    setPage(1);
  };

  const clearSearch = () => {
    setSearchInput('');
    setAppliedTerm('');
    setAppliedField(DEFAULT_SEARCH_FIELD);
    setSearchBy(DEFAULT_SEARCH_FIELD);
    setPage(1);
  };

  const handleSelect = (customer) => {
    onSelect(customer);
    onClose();
  };

  const handleDragStart = (e) => {
    if (!modalRef.current) return;
    if (e.target.closest('button')) return;

    const modal = modalRef.current;
    const rect = modal.getBoundingClientRect();
    const originX = position.x || rect.left;
    const originY = position.y || rect.top;
    const pointerId = e.pointerId;
    const startX = e.clientX;
    const startY = e.clientY;

    const onPointerMove = (ev) => {
      if (ev.pointerId !== pointerId) return;
      const r = modal.getBoundingClientRect();
      setPosition(
        clampModalPosition(
          originX + (ev.clientX - startX),
          originY + (ev.clientY - startY),
          r.width,
          r.height,
        ),
      );
    };

    const handleEl = e.currentTarget;

    const endDrag = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', endDrag);
      window.removeEventListener('pointercancel', endDrag);
      document.body.classList.remove('customer-lookup-dragging');
      try {
        handleEl.releasePointerCapture(pointerId);
      } catch {
        /* ignore */
      }
    };

    document.body.classList.add('customer-lookup-dragging');
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);

    try {
      handleEl.setPointerCapture(pointerId);
    } catch {
      /* ignore */
    }
    e.preventDefault();
    e.stopPropagation();
  };

  if (!open) return null;

  const modal = (
    <div
      ref={modalRef}
      className="modal-content customer-lookup-modal"
      style={{
        left: position.x,
        top: position.y,
      }}
      role="dialog"
      aria-modal="false"
      aria-labelledby="customer-lookup-title"
    >
      <div
        className="modal-header customer-lookup-drag-handle"
        onPointerDown={handleDragStart}
        title="Tahan dan geser untuk memindahkan jendela"
      >
        <h2 id="customer-lookup-title">{title}</h2>
        <button type="button" className="btn-icon" onClick={onClose} aria-label="Tutup">
          <X size={20} />
        </button>
      </div>

      <div className="modal-body customer-lookup-body">
        <div className="customer-lookup-toolbar">
          <label className="customer-lookup-label">
            Cari berdasarkan
            <select
              className="form-input"
              value={searchBy}
              onChange={(e) => setSearchBy(e.target.value)}
            >
              {SEARCH_FIELDS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          <label className="customer-lookup-label customer-lookup-input-field">
            Kata kunci
            <input
              type="text"
              className="form-input"
              value={searchInput}
              placeholder="Ketik lalu klik Cari..."
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  runSearch();
                }
              }}
            />
          </label>
          <div className="customer-lookup-actions">
            <button type="button" className="btn btn-primary" onClick={runSearch}>
              Cari
            </button>
            <button type="button" className="btn btn-secondary" onClick={clearSearch}>
              Bersihkan
            </button>
          </div>
        </div>

        <div className="customer-lookup-pager">
          <span className="customer-lookup-range">
            Record {rangeStart}..{rangeEnd} of {filtered.length}
          </span>
          <div className="customer-lookup-pager-btns">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={safePage <= 1}
              onClick={() => setPage(1)}
              title="Halaman pertama"
            >
              <ChevronsLeft size={16} />
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              title="Sebelumnya"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              title="Berikutnya"
            >
              <ChevronRight size={16} />
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={safePage >= totalPages}
              onClick={() => setPage(totalPages)}
              title="Halaman terakhir"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>

        <div className="customer-lookup-table-wrap">
          <table className="glass-table customer-lookup-table">
            <thead>
              <tr>
                <th>Kode Customer</th>
                <th>Nama Customer</th>
                <th>Kota/Kabupaten</th>
                <th>Koordinat</th>
                <th>Telepon</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
                    {appliedTerm
                      ? 'Tidak ada data — ubah kata kunci atau klik Bersihkan'
                      : 'Ketik kata kunci lalu klik Cari, atau kosongkan filter untuk menampilkan semua'}
                  </td>
                </tr>
              ) : (
                pageRows.map((c) => {
                  const coords = formatCustomerCoords(c.latitude, c.longitude);
                  return (
                  <tr
                    key={c.id}
                    className="customer-lookup-row customer-lookup-row-selectable"
                    onClick={() => handleSelect(c)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleSelect(c);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    title={`Pilih ${c.name || c.code || 'customer'}`}
                  >
                    <td>{c.code || '—'}</td>
                    <td>{c.name}</td>
                    <td>{c.city || '—'}</td>
                    <td style={{ fontSize: '0.85rem', lineHeight: 1.4, whiteSpace: 'nowrap' }}>
                      {coords ? (
                        <>
                          <span style={{ display: 'block', fontFamily: 'ui-monospace, monospace' }}>{coords.lat}</span>
                          <span style={{ display: 'block', fontFamily: 'ui-monospace, monospace', opacity: 0.85 }}>{coords.lng}</span>
                        </>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)' }}>—</span>
                      )}
                    </td>
                    <td>{c.phone || '—'}</td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <p className="customer-lookup-hint">
          Klik baris customer untuk memilih. Menampilkan {PAGE_SIZE} baris per halaman. Geser dari judul
          untuk memindahkan jendela. Tutup dengan tombol X.
        </p>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};

export default CustomerLookupModal;
