export const EMPTY_ROUTE_KM = { totalKm: 0, legs: [] };

export const formatKm = (km) =>
  Number(km || 0).toLocaleString('id-ID', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

/** Jarak snapshot (km) dari custom_toll_breakdown customer. */
export function customerRouteDistanceKm(customer) {
  const rows = customer?.custom_toll_breakdown;
  if (!Array.isArray(rows)) return null;
  const meta = rows.find((row) => row && row._route_meta);
  if (!meta) return null;
  const km = Number(meta.distance_km ?? meta.distance_km_route);
  return km > 0 ? km : null;
}

/** BBM master: kolom tarif, atau estimasi dari jarak snapshot. */
export function resolveTariffBbm(tariff, customer, vt) {
  const fromTariff = Number(tariff?.bbm) || 0;
  if (fromTariff > 0) return fromTariff;
  const km = customerRouteDistanceKm(customer);
  if (!(km > 0) || !vt) return 0;
  return calcBbmAmount(km, vt) || 0;
}
export function calcBbmAmount(distanceKm, vt) {
  if (!distanceKm || !vt?.km_per_liter) return null;
  const afterRoundTrip = Number(distanceKm) / Number(vt.km_per_liter) * 2;
  if (vt.bbm_price) {
    return Math.round((afterRoundTrip * Number(vt.bbm_price)) / 1000) * 1000;
  }
  return Math.round(afterRoundTrip);
}

export function routePointLabel(point, index, points) {
  if (!point) return `Titik ${index + 1}`;
  if (point.isWarehouse) return 'Gudang';
  if (point.label) return point.label;
  const warehouseOffset = points[0]?.isWarehouse ? 1 : 0;
  return `Rute ${index - warehouseOffset + 1}`;
}

export function buildRouteKmSummary(points, route) {
  if (!route) return EMPTY_ROUTE_KM;
  const totalKm = Number(route.distance || 0) / 1000;
  const osrmLegs = Array.isArray(route.legs) ? route.legs : [];
  const legs = osrmLegs.map((leg, i) => {
    const from = points[i];
    const to = points[i + 1];
    return {
      fromLabel: routePointLabel(from, i, points),
      toLabel: routePointLabel(to, i + 1, points),
      fromName: from?.name || '',
      toName: to?.name || '',
      distanceKm: Number(leg.distance || 0) / 1000,
    };
  });
  return { totalKm, legs };
}
