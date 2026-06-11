import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, ChevronsLeft, ChevronLeft, ChevronRight, ChevronsRight } from 'lucide-react';

const PAGE_SIZE = 15;

const DEFAULT_SEARCH_FIELD = 'name';

const SEARCH_FIELDS = [
  { id: 'name', label: 'Nama Ruas' },
  { id: 'origin_name', label: 'Gerbang Masuk (Origin)' },
  { id: 'destination_name', label: 'Gerbang Keluar (Destinasi)' },
  { id: 'network', label: 'Jaringan (Network)' },
];

const filterByField = (section, field, term) => {
  if (!term) return true;
  const q = term.trim().toLowerCase();
  
  if (field === 'all') {
    return (
      String(section.name || '').toLowerCase().includes(q) ||
      String(section.origin_name || '').toLowerCase().includes(q) ||
      String(section.destination_name || '').toLowerCase().includes(q) ||
      String(section.network || '').toLowerCase().includes(q)
    );
  }

  const raw = section[field];
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

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const sectionRateII = (sec) => {
  const rates = sec?.rates || [];
  const row = rates.find((r) => r.golongan_code === 'II') || rates.find((r) => r.golongan_code === 'III');
  return row?.rate != null ? Number(row.rate) : null;
};

const sectionRouteLabel = (sec, { withRate = true } = {}) => {
  const origin = sec?.origin_name?.trim();
  const dest = sec?.destination_name?.trim();
  const rate = withRate ? sectionRateII(sec) : null;
  const rateSuffix = rate != null ? ` · ${formatIDR(rate)}` : '';

  if (origin && dest) {
    if (origin.toLowerCase() === dest.toLowerCase()) {
      return `${origin} (ruas penuh)${rateSuffix}`;
    }
    return `${origin} → ${dest}${rateSuffix}`;
  }
  if (origin) return `${origin}${rateSuffix}`;
  return `${sec?.name || 'Ruas tol'}${rateSuffix}`;
};

const SectionLookupModal = ({
  open,
  onClose,
  sections = [],
  onSelect,
  title = 'Pilih Ruas Tol',
}) => {
  const [searchBy, setSearchBy] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [appliedTerm, setAppliedTerm] = useState('');
  const [appliedField, setAppliedField] = useState('all');
  const [page, setPage] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const modalRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setSearchBy('all');
    setSearchInput('');
    setAppliedTerm('');
    setAppliedField('all');
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

  const filtered = useMemo(() => {
    return sections.filter((c) => {
      if (c.is_active === false) return false;
      return filterByField(c, appliedField, appliedTerm);
    }).sort((a, b) => {
      const na = a.network || 'Lainnya';
      const nb = b.network || 'Lainnya';
      if (na !== nb) return na.localeCompare(nb);
      const oa = a.origin_name || '';
      const ob = b.origin_name || '';
      if (oa !== ob) return oa.localeCompare(ob);
      return (a.destination_name || '').localeCompare(b.destination_name || '');
    });
  }, [sections, appliedField, appliedTerm]);

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
    setAppliedField('all');
    setSearchBy('all');
    setPage(1);
  };

  const handleSelect = (section) => {
    onSelect(section);
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
              <option value="all">Semua Kolom</option>
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
                <th>Jaringan (Network)</th>
                <th>Nama Ruas</th>
                <th>Asal &rarr; Tujuan</th>
                <th>Tarif Gol II</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
                    {appliedTerm
                      ? 'Tidak ada data — ubah kata kunci atau klik Bersihkan'
                      : 'Ketik kata kunci lalu klik Cari, atau kosongkan filter untuk menampilkan semua'}
                  </td>
                </tr>
              ) : (
                pageRows.map((c) => {
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
                    title={`Pilih ${c.name || 'ruas'}`}
                  >
                    <td>{c.network || 'Lainnya'}</td>
                    <td>{c.name || '—'}</td>
                    <td>{sectionRouteLabel(c, { withRate: false })}</td>
                    <td>{formatIDR(sectionRateII(c))}</td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <p className="customer-lookup-hint">
          Klik baris ruas untuk memilih. Menampilkan {PAGE_SIZE} baris per halaman. Geser dari judul
          untuk memindahkan jendela. Tutup dengan tombol X.
        </p>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};

export default SectionLookupModal;
