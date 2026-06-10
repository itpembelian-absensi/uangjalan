import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import CustomerLookupModal from './CustomerLookupModal';

export const customerLabel = (c) => {
  if (!c) return '';
  const code = c.code?.trim();
  return code ? `${code} — ${c.name}` : c.name || '';
};

export const customerCodeLabel = (c) => {
  if (!c) return '';
  return c.code?.trim() || c.name || '';
};

const CustomerSearchSelect = ({
  customers = [],
  value,
  onChange,
  onAfterSelect,
  disabled = false,
  placeholder = 'Klik ikon cari untuk memilih customer',
  excludeIds = [],
  codeOnly = false,
  showNameBelow = false,
  compact = false,
}) => {
  const [modalOpen, setModalOpen] = useState(false);

  const selected = useMemo(
    () => customers.find((c) => String(c.id) === String(value)),
    [customers, value],
  );

  const handleSelect = (customer) => {
    onChange(String(customer.id));
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
            value={selected ? (codeOnly ? customerCodeLabel(selected) : customerLabel(selected)) : ''}
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
            title="Cari customer"
            aria-label="Cari customer"
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
        {showNameBelow && selected?.name && (
          <div className="customer-lookup-name-below">{selected.name}</div>
        )}
      </div>

      <CustomerLookupModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        customers={customers}
        onSelect={handleSelect}
        excludeIds={excludeIds}
      />
    </>
  );
};

export default CustomerSearchSelect;
