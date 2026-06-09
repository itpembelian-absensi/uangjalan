import React from 'react';
import { formatReportDate, formatSaleTransactionText } from '../utils/deliveryRouteReportExport';
import { groupStopRowsByRoute, formatItemQuantity, sumStopRowsQty } from '../utils/deliveryRouteUtils';
import { StopItemsNamesCell, StopItemsQtyCell } from './StopItemsCells';

const DeliveryRouteStopDetailTable = ({
  stopRows = [],
  loading = false,
  showSaleNo = false,
  maxHeight = '360px',
}) => {
  const colCount = showSaleNo ? 10 : 9;
  const groups = groupStopRowsByRoute(stopRows);
  let rowNo = 0;

  return (
    <div className="table-container route-stop-detail-table" style={{ padding: 0, maxHeight, overflowY: 'auto' }}>
      <table className="glass-table" style={{ fontSize: '0.85rem' }}>
        <thead>
          <tr>
            <th style={{ width: '40px', textAlign: 'center' }}>No</th>
            <th>No. Rute</th>
            <th>Tanggal</th>
            <th>Rit</th>
            <th>{showSaleNo ? 'Jenis Kendaraan' : 'Jenis'}</th>
            <th style={{ textAlign: 'center' }}>Urut</th>
            <th>Customer</th>
            <th>Barang Dikirim</th>
            <th style={{ textAlign: 'center', minWidth: '72px' }}>Qty</th>
            <th>Nomor SO</th>
            <th>Kode Entity</th>
            {showSaleNo && <th>No. Transaksi</th>}
          </tr>
        </thead>
        {stopRows.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={colCount} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
                {loading ? 'Memuat...' : 'Tidak ada detail customer'}
              </td>
            </tr>
          </tbody>
        ) : (
          groups.map((group, groupIndex) => (
            <tbody key={`${group.route_no}-${groupIndex}`} className="route-stop-group">
              <tr className="route-stop-group-header">
                <td colSpan={colCount}>
                  <div className="route-stop-group-header__inner">
                    <span className="route-stop-group-header__badge">Rute {groupIndex + 1}</span>
                    <strong className="route-stop-group-header__route">{group.route_no}</strong>
                    <span className="route-stop-group-header__meta">
                      {formatReportDate(group.route_date)}
                      {' · '}
                      {group.vehicle_type_name || '-'}
                      {' · '}
                      Rit {group.ritase || 1}
                      {showSaleNo && (group.sale_no || group.sale_vehicle_plate || group.sale_driver_name) && (
                        <>
                          {' · '}
                          <span style={{ fontSize: '0.85em' }}>
                            {[
                              group.sale_no,
                              group.sale_vehicle_plate && `Kendaraan: ${group.sale_vehicle_plate}`,
                              group.sale_driver_name && `Sopir: ${group.sale_driver_name}`,
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </span>
                        </>
                      )}
                      {' · '}
                      {group.stops.length} customer
                      {' · '}
                      <strong>{formatItemQuantity(sumStopRowsQty(group.stops))} qty</strong>
                    </span>
                  </div>
                </td>
              </tr>
              {group.stops.map((s) => {
                rowNo += 1;
                const n = rowNo;
                return (
                  <tr key={`${s.route_no}-${s.stop_order}-${n}`} className="route-stop-group-row">
                    <td style={{ textAlign: 'center' }}>{n}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{s.route_no}</td>
                    <td>{formatReportDate(s.route_date)}</td>
                    <td style={{ textAlign: 'center' }}>{s.ritase || 1}</td>
                    <td>{s.vehicle_type_name || '-'}</td>
                    <td style={{ textAlign: 'center' }}>{s.stop_order}</td>
                    <td>{s.customer_name}</td>
                    <td>
                      <StopItemsNamesCell stop={s} />
                    </td>
                    <td style={{ textAlign: 'center', verticalAlign: 'top' }}>
                      <StopItemsQtyCell stop={s} />
                    </td>
                    <td>{s.description || '-'}</td>
                    <td>{s.entity_code || '-'}</td>
                    {showSaleNo && (
                      <td style={{ whiteSpace: 'pre-line', lineHeight: 1.35, fontSize: '0.8rem' }}>
                        {formatSaleTransactionText(s)}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          ))
        )}
      </table>
    </div>
  );
};

export default DeliveryRouteStopDetailTable;
