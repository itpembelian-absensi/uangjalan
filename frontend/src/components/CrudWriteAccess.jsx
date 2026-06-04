import { usePageWriteAccess } from '../auth/AuthContext';

/** Apakah user boleh create/update/delete di halaman saat ini */
export function useCrudWrite() {
  return usePageWriteAccess();
}

/** Lebar kolom tabel di layout `grid-cols-3` (form 1 + tabel 2, atau tabel penuh). */
export function crudTableGridSpan(canWrite) {
  return canWrite ? 2 : 3;
}

export function CrudActionsHeader({ canWrite, label = 'Aksi', align = 'right' }) {
  if (!canWrite) return null;
  return <th style={{ textAlign: align }}>{label}</th>;
}

export function CrudActionsCell({ canWrite, children, align = 'right' }) {
  if (!canWrite) return null;
  return <td style={{ textAlign: align }}>{children}</td>;
}
