import React from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

const TablePager = ({ page, pageSize, totalItems, onPageChange, label = 'record' }) => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const rangeStart = totalItems === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const rangeEnd = Math.min(safePage * pageSize, totalItems);

  if (totalItems === 0) return null;

  return (
    <div className="customer-lookup-pager">
      <span className="customer-lookup-range">
        {label} {rangeStart}–{rangeEnd} dari {totalItems.toLocaleString('id-ID')}
        {totalPages > 1 && ` · halaman ${safePage}/${totalPages}`}
      </span>
      <div className="customer-lookup-pager-btns">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={safePage <= 1}
          onClick={() => onPageChange(1)}
          title="Halaman pertama"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          title="Sebelumnya"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
          title="Berikutnya"
        >
          <ChevronRight size={16} />
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange(totalPages)}
          title="Halaman terakhir"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  );
};

export default TablePager;
