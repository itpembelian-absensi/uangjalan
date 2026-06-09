import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import {
  groupStopRowsByRoute,
  formatItemQuantity,
  getStopItemLines,
  getStopQtyTotal,
  sumStopRowsQty,
} from './deliveryRouteUtils';

const saleGroupMeta = (group) => {
  const parts = [];
  if (group.sale_no) parts.push(group.sale_no);
  if (group.sale_vehicle_plate) parts.push(`Kendaraan: ${group.sale_vehicle_plate}`);
  if (group.sale_driver_name) parts.push(`Sopir: ${group.sale_driver_name}`);
  return parts.length ? ` · ${parts.join(' · ')}` : '';
};

export const formatStopItemsNamesExport = (stop) => {
  const lines = getStopItemLines(stop);
  if (!lines.length) return '-';
  return lines.map((line) => line.item_name).join('\n');
};

export const formatStopItemsQtyExport = (stop) => {
  const lines = getStopItemLines(stop);
  if (!lines.length) return '-';
  return lines.map((line) => formatItemQuantity(line.quantity)).join('\n');
};

export const formatReportDate = (d) => {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

export const formatSaleTransactionText = (row) => {
  if (!row?.sale_no && !row?.sale_vehicle_plate && !row?.sale_driver_name) return '-';
  const lines = [];
  if (row.sale_no) lines.push(row.sale_no);
  if (row.sale_vehicle_plate) lines.push(`Kendaraan: ${row.sale_vehicle_plate}`);
  if (row.sale_driver_name) lines.push(`Sopir: ${row.sale_driver_name}`);
  return lines.join('\n');
};

export const formatSaleTransactionHtml = (row) => {
  if (!row?.sale_no && !row?.sale_vehicle_plate && !row?.sale_driver_name) return '-';
  const parts = [];
  if (row.sale_no) parts.push(`<span style="font-family:monospace">${row.sale_no}</span>`);
  if (row.sale_vehicle_plate) {
    parts.push(`<span style="font-size:0.9em;color:#64748b">Kendaraan: ${row.sale_vehicle_plate}</span>`);
  }
  if (row.sale_driver_name) {
    parts.push(`<span style="font-size:0.9em;color:#64748b">Sopir: ${row.sale_driver_name}</span>`);
  }
  return parts.join('<br/>');
};

const buildStopDetailPdfBody = (stopRows) => {
  const body = [];
  groupStopRowsByRoute(stopRows).forEach((group, groupIndex) => {
    body.push([
      {
        content: `Rute ${groupIndex + 1}: ${group.route_no} · ${formatReportDate(group.route_date)} · ${group.vehicle_type_name || '-'}${saleGroupMeta(group)} · ${group.stops.length} customer`,
        colSpan: 9,
        styles: {
          fillColor: [226, 232, 240],
          textColor: [15, 23, 42],
          fontStyle: 'bold',
          fontSize: 8,
          halign: 'left',
          cellPadding: { top: 4, bottom: 3, left: 4, right: 4 },
          lineWidth:
            groupIndex === 0
              ? { top: 0.1, bottom: 0.2 }
              : { top: 1.2, bottom: 0.2 },
          lineColor:
            groupIndex === 0
              ? { top: [203, 213, 225], bottom: [203, 213, 225] }
              : { top: [37, 99, 235], bottom: [203, 213, 225] },
        },
      },
    ]);
    group.stops.forEach((s) => {
      body.push([
        s.route_no,
        formatReportDate(s.route_date),
        `Rit ${s.ritase || 1}`,
        s.vehicle_type_name,
        s.stop_order,
        s.customer_name,
        formatStopItemsNamesExport(s),
        formatStopItemsQtyExport(s),
        s.description || '-',
        s.entity_code || '-',
      ]);
    });
  });
  return body;
};

const routeStopFieldSummary = (routeNo, stopRows, field) => {
  const parts = stopRows
    .filter((s) => s.route_no === routeNo)
    .sort((a, b) => a.stop_order - b.stop_order)
    .map((s) => (s[field] != null && s[field] !== '' ? String(s[field]).trim() : ''))
    .filter(Boolean);
  return parts.length ? parts.join('; ') : '-';
};

export const buildReportQuery = ({ fromDate, toDate, vehicleTypeId }) => {
  const params = new URLSearchParams();
  if (fromDate) params.set('from', fromDate);
  if (toDate) params.set('to', toDate);
  if (vehicleTypeId) params.set('vehicle_type_id', vehicleTypeId);
  const q = params.toString();
  return q ? `?${q}` : '';
};

export const exportDeliveryRoutePdf = (report, { fromDate, toDate }) => {
  const { routes = [], stop_rows = [], total_routes = 0, total_stops = 0, total_items_qty = 0 } = report;
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const marginX = 6;
  const tableWidth = pageWidth - marginX * 2;
  const summaryStatCol = tableWidth / 6;
  const routeSummaryWidths = {
    0: 24,
    1: 32,
    2: 16,
    3: 26,
    4: 12,
    5: 60,
    6: 32,
    7: 32,
    8: tableWidth - (24 + 32 + 16 + 26 + 12 + 60 + 32 + 32),
  };
  const stopDetailWidths = {
    0: 32,
    1: 24,
    2: 14,
    3: 24,
    4: 10,
    5: 44,
    6: 58,
    7: 16,
    8: 30,
    9: tableWidth - (32 + 24 + 14 + 24 + 10 + 44 + 58 + 16 + 30),
  };

  pdf.setFontSize(16);
  pdf.text('Laporan Rute Pengiriman', pageWidth / 2, 14, { align: 'center' });
  pdf.setFontSize(10);
  pdf.setTextColor(100);
  pdf.text(
    `Periode: ${formatReportDate(fromDate)} - ${formatReportDate(toDate)} | Dicetak: ${new Date().toLocaleString('id-ID')}`,
    pageWidth / 2,
    20,
    { align: 'center' },
  );
  pdf.setTextColor(0);

  autoTable(pdf, {
    startY: 26,
    margin: { left: marginX, right: marginX },
    tableWidth,
    body: [
      [
        { content: 'Total Rute', styles: { fillColor: [241, 245, 249], fontStyle: 'bold' } },
        { content: String(total_routes), styles: { halign: 'center', fontStyle: 'bold', fontSize: 12 } },
        { content: 'Total Customer', styles: { fillColor: [241, 245, 249], fontStyle: 'bold' } },
        { content: String(total_stops), styles: { halign: 'center', fontStyle: 'bold', fontSize: 12 } },
        { content: 'Total Qty Barang', styles: { fillColor: [241, 245, 249], fontStyle: 'bold' } },
        {
          content: formatItemQuantity(total_items_qty),
          styles: { halign: 'center', fontStyle: 'bold', fontSize: 12 },
        },
      ],
    ],
    theme: 'grid',
    styles: { fontSize: 10, cellPadding: 4, lineColor: [203, 213, 225], lineWidth: 0.1 },
    columnStyles: {
      0: { cellWidth: summaryStatCol },
      1: { cellWidth: summaryStatCol },
      2: { cellWidth: summaryStatCol },
      3: { cellWidth: summaryStatCol },
      4: { cellWidth: summaryStatCol },
      5: { cellWidth: summaryStatCol },
    },
  });

  autoTable(pdf, {
    startY: pdf.lastAutoTable.finalY + 6,
    margin: { left: marginX, right: marginX },
    tableWidth,
    head: [
      [
        'Tanggal',
        'No. Rute',
        'Rit',
        'Jenis Kendaraan',
        'Jml Cust',
        'Customer',
        'Nomor SO',
        'Kode Entity',
        'Keterangan',
      ],
    ],
    body: routes.map((r) => [
      formatReportDate(r.date),
      r.route_no,
      `Rit ${r.ritase || 1}`,
      r.vehicle_type_name,
      r.stop_count,
      r.customers,
      routeStopFieldSummary(r.route_no, stop_rows, 'description'),
      routeStopFieldSummary(r.route_no, stop_rows, 'entity_code'),
      r.remarks || '-',
    ]),
    foot: [
      [
        { content: 'TOTAL CUSTOMER', colSpan: 3, styles: { halign: 'right', fontStyle: 'bold' } },
        { content: String(total_stops), styles: { halign: 'center', fontStyle: 'bold' } },
        { content: '', colSpan: 4 },
      ],
    ],
    styles: {
      fontSize: 8,
      cellPadding: 2.5,
      lineColor: [203, 213, 225],
      lineWidth: 0.1,
      overflow: 'linebreak',
    },
    headStyles: {
      fillColor: [51, 65, 85],
      textColor: 255,
      fontStyle: 'bold',
      halign: 'center',
      cellPadding: 3,
    },
    footStyles: {
      fillColor: [241, 245, 249],
      textColor: 20,
      fontStyle: 'bold',
      cellPadding: 3,
    },
    columnStyles: {
      0: { cellWidth: routeSummaryWidths[0], halign: 'center' },
      1: { cellWidth: routeSummaryWidths[1] },
      2: { cellWidth: routeSummaryWidths[2], halign: 'center' },
      3: { cellWidth: routeSummaryWidths[3] },
      4: { cellWidth: routeSummaryWidths[4], halign: 'center' },
      5: { cellWidth: routeSummaryWidths[5] },
      6: { cellWidth: routeSummaryWidths[6] },
      7: { cellWidth: routeSummaryWidths[7] },
      8: { cellWidth: routeSummaryWidths[8] },
    },
  });

  if (stop_rows.length > 0) {
    autoTable(pdf, {
      startY: pdf.lastAutoTable.finalY + 8,
      margin: { left: marginX, right: marginX },
      tableWidth,
      head: [
        [
          'No. Rute',
          'Tanggal',
          'Rit',
          'Jenis Kendaraan',
          'Urut',
          'Customer',
          'Barang',
          'Qty',
          'Nomor SO',
          'Kode Entity',
        ],
      ],
      body: buildStopDetailPdfBody(stop_rows),
      styles: {
        fontSize: 8,
        cellPadding: 2.5,
        lineColor: [203, 213, 225],
        lineWidth: 0.1,
        overflow: 'linebreak',
      },
      headStyles: {
        fillColor: [71, 85, 105],
        textColor: 255,
        fontStyle: 'bold',
        halign: 'center',
        cellPadding: 3,
      },
      columnStyles: {
        0: { cellWidth: stopDetailWidths[0] },
        1: { cellWidth: stopDetailWidths[1], halign: 'center' },
        2: { cellWidth: stopDetailWidths[2], halign: 'center' },
        3: { cellWidth: stopDetailWidths[3] },
        4: { cellWidth: stopDetailWidths[4], halign: 'center' },
        5: { cellWidth: stopDetailWidths[5] },
        6: { cellWidth: stopDetailWidths[6] },
        7: { cellWidth: stopDetailWidths[7], halign: 'center' },
        8: { cellWidth: stopDetailWidths[8] },
        9: { cellWidth: stopDetailWidths[9] },
      },
    });
  }

  pdf.save(`laporan-rute-pengiriman-${fromDate || 'all'}-${toDate || 'all'}.pdf`);
};

export const exportDeliveryRouteExcel = (report, { fromDate, toDate }) => {
  const { routes = [], stop_rows = [], total_routes = 0, total_stops = 0, total_items_qty = 0 } = report;

  const summarySheet = [
    ['Laporan Rute Pengiriman'],
    [`Periode: ${formatReportDate(fromDate)} - ${formatReportDate(toDate)}`],
    [`Dicetak: ${new Date().toLocaleString('id-ID')}`],
    [],
    ['Total Rute', total_routes],
    ['Total Customer', total_stops],
    ['Total Qty Barang', total_items_qty],
    [],
    ['No', 'Tanggal', 'No. Rute', 'Rit', 'Jenis Kendaraan', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Jumlah Customer', 'Customer', 'Keterangan'],
    ...routes.map((r, i) => [
      i + 1,
      formatReportDate(r.date),
      r.route_no,
      `Rit ${r.ritase || 1}`,
      r.vehicle_type_name,
      r.sale_no || '',
      r.sale_vehicle_plate || '',
      r.sale_driver_name || '',
      r.stop_count,
      r.customers,
      r.remarks || '',
    ]),
  ];

  const detailSheet = [
    ['Detail Customer per Rute'],
    [`Periode: ${formatReportDate(fromDate)} - ${formatReportDate(toDate)}`],
    [],
    [
      'No',
      'No. Rute',
      'Tanggal',
      'Rit',
      'Jenis Kendaraan',
      'Urutan',
      'Customer',
      'Barang Dikirim',
      'Qty',
      'Total Qty',
      'Nomor SO',
      'Kode Entity',
      'No. Transaksi',
      'Kendaraan',
      'Sopir',
      'Keterangan Rute',
    ],
    ...(() => {
      const rows = [];
      let n = 0;
      groupStopRowsByRoute(stop_rows).forEach((group, gi) => {
        rows.push([
          '',
          `Rute ${gi + 1}: ${group.route_no}`,
          formatReportDate(group.route_date),
          `Rit ${group.ritase || 1}`,
          group.vehicle_type_name || '',
          '',
          `${group.stops.length} customer`,
          '',
          formatItemQuantity(sumStopRowsQty(group.stops)),
          '',
          '',
          '',
          group.sale_no || '',
          group.sale_vehicle_plate || '',
          group.sale_driver_name || '',
          '',
        ]);
        group.stops.forEach((s) => {
          n += 1;
          rows.push([
            n,
            s.route_no,
            formatReportDate(s.route_date),
            `Rit ${s.ritase || 1}`,
            s.vehicle_type_name,
            s.stop_order,
            s.customer_name,
            formatStopItemsNamesExport(s) === '-' ? '' : formatStopItemsNamesExport(s),
            formatStopItemsQtyExport(s) === '-' ? '' : formatStopItemsQtyExport(s),
            getStopQtyTotal(s),
            s.description || '',
            s.entity_code || '',
            s.sale_no || '',
            s.sale_vehicle_plate || '',
            s.sale_driver_name || '',
            s.remarks || '',
          ]);
        });
      });
      return rows;
    })(),
  ];

  const wb = XLSX.utils.book_new();
  const wsSummary = XLSX.utils.aoa_to_sheet(summarySheet);
  wsSummary['!cols'] = [
    { wch: 5 }, { wch: 14 }, { wch: 18 }, { wch: 8 }, { wch: 16 },
    { wch: 18 }, { wch: 14 }, { wch: 18 }, { wch: 8 }, { wch: 40 }, { wch: 20 },
  ];
  XLSX.utils.book_append_sheet(wb, wsSummary, 'Ringkasan Rute');

  const wsDetail = XLSX.utils.aoa_to_sheet(detailSheet);
  wsDetail['!cols'] = [
    { wch: 5 }, { wch: 18 }, { wch: 14 }, { wch: 8 }, { wch: 14 }, { wch: 6 },
    { wch: 28 }, { wch: 32 }, { wch: 10 }, { wch: 10 }, { wch: 18 }, { wch: 14 },
    { wch: 18 }, { wch: 14 }, { wch: 18 }, { wch: 20 },
  ];
  XLSX.utils.book_append_sheet(wb, wsDetail, 'Detail Customer');

  XLSX.writeFile(wb, `laporan-rute-pengiriman-${fromDate || 'all'}-${toDate || 'all'}.xlsx`);
};

export const printDeliveryRouteReport = (report, { fromDate, toDate }) => {
  const { routes = [], stop_rows = [], total_routes = 0, total_stops = 0, total_items_qty = 0 } = report;
  const printWindow = window.open('', '_blank', 'width=1100,height=800');
  if (!printWindow) {
    alert('Popup diblokir! Izinkan popup untuk mencetak.');
    return;
  }

  const routeRows = routes
    .map(
      (r, i) => `
      <tr>
        <td class="center">${i + 1}</td>
        <td class="center">${formatReportDate(r.date)}</td>
        <td>${r.route_no}</td>
        <td class="center">Rit ${r.ritase || 1}</td>
        <td class="center">${r.vehicle_type_name}</td>
        <td style="white-space:pre-line;line-height:1.35">${formatSaleTransactionHtml(r)}</td>
        <td class="center">${r.stop_count}</td>
        <td>${r.customers}</td>
        <td>${r.remarks || '-'}</td>
      </tr>`,
    )
    .join('');

  let stopRowNo = 0;
  const stopDetailRows = groupStopRowsByRoute(stop_rows)
    .map((group, gi) => {
      const borderTop = gi > 0 ? 'border-top:3px solid #2563eb;' : '';
      const header = `
      <tr class="route-group-header">
        <td colspan="11" style="background:#e8f0fe;font-weight:700;padding:8px;${borderTop}">
          Rute ${gi + 1}: ${group.route_no} · ${formatReportDate(group.route_date)} · ${group.vehicle_type_name || '-'}${saleGroupMeta(group)} · ${group.stops.length} customer · ${formatItemQuantity(sumStopRowsQty(group.stops))} qty
        </td>
      </tr>`;
      const body = group.stops
        .map((s) => {
          stopRowNo += 1;
          return `
      <tr>
        <td class="center">${stopRowNo}</td>
        <td>${s.route_no}</td>
        <td class="center">${formatReportDate(s.route_date)}</td>
        <td class="center">Rit ${s.ritase || 1}</td>
        <td>${s.vehicle_type_name}</td>
        <td class="center">${s.stop_order}</td>
        <td>${s.customer_name}</td>
        <td style="white-space:pre-line">${formatStopItemsNamesExport(s)}</td>
        <td class="center" style="white-space:pre-line;font-weight:600">${formatStopItemsQtyExport(s)}</td>
        <td>${s.description || '-'}</td>
        <td>${s.entity_code || '-'}</td>
        <td style="white-space:pre-line;line-height:1.35">${formatSaleTransactionHtml(s)}</td>
      </tr>`;
        })
        .join('');
      return header + body;
    })
    .join('');

  printWindow.document.write(`<!DOCTYPE html><html><head>
    <title>Laporan Rute Pengiriman</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; color: #111; }
      h1 { text-align: center; font-size: 20px; margin-bottom: 4px; }
      h2 { font-size: 14px; margin: 24px 0 8px; }
      .meta { text-align: center; color: #555; margin-bottom: 20px; font-size: 12px; }
      .summary { display: flex; gap: 2rem; margin-bottom: 16px; }
      .summary-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 20px; }
      .summary-card label { font-size: 11px; color: #64748b; text-transform: uppercase; }
      .summary-card h2 { margin: 4px 0 0; font-size: 20px; }
      table { width: 100%; border-collapse: collapse; font-size: 11px; table-layout: fixed; margin-bottom: 16px; }
      th, td { border: 1px solid #cbd5e1; padding: 6px 8px; vertical-align: top; word-wrap: break-word; }
      th { background: #334155; color: white; }
      .center { text-align: center; }
      tfoot td { background: #f1f5f9; font-weight: 700; }
      @media print { body { padding: 0; } }
    </style>
  </head><body>
    <h1>Laporan Rute Pengiriman</h1>
    <p class="meta">Periode: ${formatReportDate(fromDate)} - ${formatReportDate(toDate)} | Dicetak: ${new Date().toLocaleString('id-ID')}</p>
    <div class="summary">
      <div class="summary-card"><label>Total Rute</label><h2>${total_routes}</h2></div>
      <div class="summary-card"><label>Total Customer</label><h2>${total_stops}</h2></div>
      <div class="summary-card"><label>Total Qty Barang</label><h2>${formatItemQuantity(total_items_qty)}</h2></div>
    </div>
    <h2>Ringkasan Rute</h2>
    <table>
      <thead><tr><th class="center">No</th><th class="center">Tanggal</th><th>No. Rute</th><th class="center">Rit</th><th class="center">Jenis Kendaraan</th><th>No. Transaksi</th><th class="center">Jml Cust</th><th>Customer</th><th>Keterangan</th></tr></thead>
      <tbody>${routeRows}</tbody>
      <tfoot><tr><td colspan="5" style="text-align:right">TOTAL CUSTOMER</td><td class="center">${total_stops}</td><td colspan="2"></td></tr></tfoot>
    </table>
    ${stop_rows.length > 0 ? `<h2>Detail Customer & Barang</h2>
    <table>
      <thead><tr><th class="center">No</th><th>No. Rute</th><th class="center">Tanggal</th><th class="center">Rit</th><th>Jenis Kendaraan</th><th class="center">Urut</th><th>Customer</th><th>Barang</th><th class="center">Qty</th><th>Nomor SO</th><th>Kode Entity</th><th>No. Transaksi</th></tr></thead>
      <tbody>${stopDetailRows}</tbody>
    </table>` : ''}
  </body></html>`);
  printWindow.document.close();
  printWindow.onload = () => {
    printWindow.focus();
    printWindow.print();
  };
};
