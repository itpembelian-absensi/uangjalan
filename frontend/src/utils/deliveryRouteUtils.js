export const formatRouteDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

export const todayIso = () => new Date().toISOString().split('T')[0];

export const tomorrowIso = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split('T')[0];
};

export const formatItemQuantity = (qty) => {
  const n = Number(qty);
  if (Number.isNaN(n)) return '-';
  return Number.isInteger(n) ? String(n) : String(n);
};

/** Ambil baris barang dari API atau parse items_summary lama. */
export const getStopItemLines = (stop) => {
  if (stop?.items?.length) {
    return stop.items.map((line) => ({
      item_name: line.item_name,
      quantity: Number(line.quantity),
    }));
  }
  if (!stop?.items_summary) return [];
  return stop.items_summary.split(';').map((part) => {
    const trimmed = part.trim();
    const match = trimmed.match(/^(.+?)\s+x\s+([\d.,]+)\s*$/i);
    if (!match) return { item_name: trimmed, quantity: 0 };
    const qty = parseFloat(match[2].replace(',', '.'));
    return { item_name: match[1].trim(), quantity: Number.isNaN(qty) ? 0 : qty };
  });
};

export const getStopQtyTotal = (stop) => {
  if (stop?.items_qty_total != null && stop.items_qty_total !== '') {
    return Number(stop.items_qty_total);
  }
  return getStopItemLines(stop).reduce((sum, line) => sum + (line.quantity || 0), 0);
};

export const sumStopRowsQty = (stops = []) => stops.reduce((sum, s) => sum + getStopQtyTotal(s), 0);

/** Kelompokkan baris detail stop per nomor rute (urutan API dipertahankan). */
export const groupStopRowsByRoute = (stopRows = []) => {
  const groups = [];
  for (const stop of stopRows) {
    const last = groups[groups.length - 1];
    if (!last || last.route_no !== stop.route_no) {
      groups.push({
        route_no: stop.route_no,
        route_date: stop.route_date,
        vehicle_type_name: stop.vehicle_type_name,
        sale_no: stop.sale_no,
        sale_vehicle_plate: stop.sale_vehicle_plate,
        sale_driver_name: stop.sale_driver_name,
        stops: [stop],
      });
    } else {
      last.stops.push(stop);
    }
  }
  return groups;
};

export const emptyLine = () => ({ item_name: '', quantity: '1' });

export const emptyStop = () => ({ customer_id: '', description: '', entity_code: '', items: [emptyLine()] });

export const defaultRouteForm = () => ({
  route_no: '',
  date: tomorrowIso(),
  vehicle_type_id: '',
  ritase: '1',
  remarks: '',
  stops: [emptyStop()],
});

export const mapStopFromApi = (stop) => ({
  customer_id: String(stop.customer_id),
  description: stop.description || '',
  entity_code: stop.entity_code || '',
  items:
    stop.items?.length > 0
      ? stop.items
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((line) => ({
            item_name: line.item_name || '',
            quantity: String(line.quantity ?? ''),
          }))
      : [emptyLine()],
});

export const buildStopItemsPayload = (items) => {
  const payload = [];
  for (const line of items || []) {
    const name = (line.item_name || '').trim();
    if (!name) continue;
    const qty = parseFloat(String(line.quantity).replace(',', '.'));
    if (Number.isNaN(qty) || qty <= 0) {
      throw new Error(`Quantity barang "${name}" harus lebih dari 0.`);
    }
    payload.push({ item_name: name, quantity: qty });
  }
  return payload;
};
