import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import SectionLookupModal from './SectionLookupModal';

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
  if (!sec) return '';
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

const SectionSearchSelect = ({
  sections = [],
  value,
  onChange,
  onAfterSelect,
  disabled = false,
  placeholder = 'Klik ikon cari untuk memilih ruas tol',
  compact = false,
}) => {
  const [modalOpen, setModalOpen] = useState(false);

  const selected = useMemo(
    () => sections.find((c) => String(c.id) === String(value)),
    [sections, value],
  );

  const handleSelect = (section) => {
    onChange(String(section.id));
    if (onAfterSelect) {
      requestAnimationFrame(() => onAfterSelect());
    }
  };

  const handleClear = () => {
    onChange('');
  };

  return (
    <>
      <div className="customer-lookup-wrap">
        <div className={`customer-lookup-field${compact ? ' customer-lookup-field--compact' : ''}`}>
          <input
            type="text"
            className="form-input customer-lookup-display"
            readOnly
            disabled={disabled}
            placeholder={placeholder}
            value={selected ? sectionRouteLabel(selected) : ''}
            onClick={() => {
              if (!disabled) setModalOpen(true);
            }}
          />
          <button
            type="button"
            className="customer-lookup-open-btn"
            tabIndex={-1}
            disabled={disabled}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (!disabled) setModalOpen(true);
            }}
            title="Cari ruas tol"
            aria-label="Cari ruas tol"
          >
            <Search size={compact ? 16 : 18} />
          </button>
          {value && !disabled && (
            <button
              type="button"
              className="customer-lookup-clear-btn"
              tabIndex={-1}
              onClick={handleClear}
              aria-label="Hapus pilihan"
            >
              ×
            </button>
          )}
        </div>
      </div>

      <SectionLookupModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        sections={sections}
        onSelect={handleSelect}
      />
    </>
  );
};

export default SectionSearchSelect;
