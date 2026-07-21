import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import { sumRouteFees, getActiveRouteFeeLines } from './routeFeeConfig';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const formatDateId = (dateString) => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('id-ID', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
};

/** Pembulatan ke atas ke ribuan terdekat. */
export function computeUangJalanTotals(baseAmount, extraAmount = 0, routeFeesAmount = 0) {
  const subtotal =
    (Number(baseAmount) || 0) + (Number(extraAmount) || 0) + (Number(routeFeesAmount) || 0);
  if (subtotal <= 0) {
    return { subtotal: 0, rounding: 0, total: 0 };
  }
  const total = Math.ceil(subtotal / 1000) * 1000;
  return { subtotal, rounding: total - subtotal, total };
}

export function buildSaleDocument(form, { vehicles, drivers, customers }) {
  const vehicle = vehicles.find((v) => String(v.id) === String(form.vehicle_id));
  const driver = drivers.find((d) => String(d.id) === String(form.driver_id));

  const filledDetails = form.details.filter((d) => d.customer_id);
  const detailRows = filledDetails.map((d) => {
    const customer = customers.find((c) => String(c.id) === String(d.customer_id));
    const tariff = (customer?.tariffs || []).find(
      (t) => String(t.vehicle_type_id) === String(d.vehicle_type_id)
    );
    const amount = parseFloat(String(d.amount).replace(/[^\d]/g, '')) || 0;
    return {
      customer: customer?.name || '-',
      vehicleType: d.vehicle_type_name || tariff?.vehicle_type_name || '-',
      amount,
    };
  });

  // Group by vehicle type — collect unique vehicle type as header
  const vehicleTypeSet = [...new Set(detailRows.map((d) => d.vehicleType))];
  const vehicleTypeHeader = vehicleTypeSet.join(', ');

  // Customer names list
  const customerNames = detailRows.map((d) => d.customer);

  const amounts = detailRows.map((d) => d.amount).filter((n) => n > 0);
  const maxNominal = amounts.length > 0 ? Math.max(...amounts) : 0;
  const extraAmount = parseFloat(String(form.extra_uang_jalan).replace(/[^\d]/g, '')) || 0;
  const routeFeesAmount = sumRouteFees(form);
  const routeFeeLines = getActiveRouteFeeLines(form);
  const multiCustomer = filledDetails.length > 1;
  const baseUangJalan = multiCustomer ? maxNominal : detailRows[0]?.amount || 0;
  const { rounding, total: totalUangJalan } = computeUangJalanTotals(baseUangJalan, extraAmount, routeFeesAmount);

  const driverBankInfo = [driver?.bank_name, driver?.bank_account].filter(Boolean).join(' ');
  const driverDisplay = driver ? (driverBankInfo ? `${driver.name} (Rek: ${driverBankInfo})` : driver.name) : '-';

  return {
    title: 'Form Transaksi Uang Jalan',
    saleNo: form.sale_no || '(Auto Generate)',
    date: formatDateId(form.date),
    vehicle: vehicle?.plate_number || '-',
    driver: driverDisplay,
    remarks: form.remarks || '-',
    vehicleTypeHeader,
    customerNames,
    details: detailRows,
    uangJalan: baseUangJalan,
    routeFeesTotal: routeFeesAmount,
    routeFeeLines,
    extraUangJalan: extraAmount,
    roundingUangJalan: rounding,
    totalUangJalan,
    showSummary: multiCustomer,
    printedAt: new Date().toLocaleString('id-ID'),
  };
}

/**
 * Build a document for print/export directly from a SaleOut object (API response).
 * Unlike `buildSaleDocument`, this doesn't need separate vehicles/drivers/customers lookups —
 * the SaleOut object already has denormalized names.
 */
export function buildSaleDocumentFromSaleOut(sale) {
  const detailRows = (sale.details || []).map((d) => ({
    customer: d.customer_name || '-',
    vehicleType: d.vehicle_type_name || '-',
    amount: parseFloat(d.amount) || 0,
  }));

  const vehicleTypeSet = [...new Set(detailRows.map((d) => d.vehicleType))];
  const vehicleTypeHeader = vehicleTypeSet.join(', ');
  const customerNames = detailRows.map((d) => d.customer);

  const amounts = detailRows.map((d) => d.amount).filter((n) => n > 0);
  const maxNominal = amounts.length > 0 ? Math.max(...amounts) : 0;
  const extraAmount = parseFloat(sale.extra_uang_jalan) || 0;
  const routeFeesAmount = sumRouteFees(sale);
  const routeFeeLines = getActiveRouteFeeLines(sale);
  const multiCustomer = detailRows.length > 1;
  const baseUangJalan = multiCustomer ? maxNominal : detailRows[0]?.amount || 0;
  const { rounding, total: totalUangJalan } = computeUangJalanTotals(baseUangJalan, extraAmount, routeFeesAmount);

  const driverBankInfo = [sale.driver_bank_name, sale.driver_bank_account].filter(Boolean).join(' ');
  const driverDisplay = sale.driver_name ? (driverBankInfo ? `${sale.driver_name} (Rek: ${driverBankInfo})` : sale.driver_name) : '-';

  return {
    title: 'Form Transaksi Uang Jalan',
    saleNo: sale.sale_no || '-',
    date: formatDateId(sale.date),
    vehicle: sale.vehicle_plate || '-',
    driver: driverDisplay,
    remarks: sale.remarks || '-',
    vehicleTypeHeader,
    customerNames,
    details: detailRows,
    uangJalan: baseUangJalan,
    routeFeesTotal: routeFeesAmount,
    routeFeeLines,
    extraUangJalan: extraAmount,
    roundingUangJalan: rounding,
    totalUangJalan,
    showSummary: multiCustomer,
    printedAt: new Date().toLocaleString('id-ID'),
  };
}

/* ───────── Bulk export helpers ───────── */

function enrichSaleRow(sale) {
  const details = sale.details || [];
  const amounts = details.map((d) => parseFloat(d.amount) || 0).filter((n) => n > 0);
  const maxNominal = amounts.length > 0 ? Math.max(...amounts) : 0;
  const extra = parseFloat(sale.extra_uang_jalan) || 0;
  const routeFees = sumRouteFees(sale);
  const multi = details.length > 1;
  const base = multi ? maxNominal : (amounts[0] || 0);
  const { rounding, total } = computeUangJalanTotals(base, extra, routeFees);
  const customerNames = details.map((d) => d.customer_name || '-').join(', ');
  const vehicleTypes = [...new Set(details.map((d) => d.vehicle_type_name || '-'))].join(', ');
  const driverBankInfo = [sale.driver_bank_name, sale.driver_bank_account].filter(Boolean).join(' ');
  return {
    ...sale,
    _base: base,
    _extra: extra,
    _routeFees: routeFees,
    _rounding: rounding,
    _total: total,
    _customers: customerNames,
    _vehicleType: vehicleTypes,
    _driverBankInfo: driverBankInfo,
  };
}

export function printBulkSales(sales, { fromLabel, toLabel } = {}) {
  const enriched = sales.map(enrichSaleRow);
  const totalBase = enriched.reduce((s, r) => s + r._base, 0);
  const totalRounding = enriched.reduce((s, r) => s + r._rounding, 0);
  const totalAll = enriched.reduce((s, r) => s + r._total, 0);
  const period = fromLabel && toLabel ? `Periode: ${fromLabel} – ${toLabel}` : '';

  const tableRows = enriched.map((s, i) => `
    <tr>
      <td style="text-align:center">${i + 1}</td>
      <td style="text-align:center">${formatDateId(s.date)}</td>
      <td>${s.sale_no}</td>
      <td style="text-align:center">${s.vehicle_plate || '-'}</td>
      <td>${s.driver_name || '-'}${s._driverBankInfo ? `<br/><small style="color:#555">Rek: ${s._driverBankInfo}</small>` : ''}</td>
      <td>${s._customers}</td>
      <td style="text-align:center">${s._vehicleType}</td>
      <td class="num">${formatIDR(s._base)}</td>
      <td class="num">${formatIDR(s._routeFees)}</td>
      <td class="num">${formatIDR(s._extra)}</td>
      <td class="num">${formatIDR(s._rounding)}</td>
      <td class="num" style="font-weight:600">${formatIDR(s._total)}</td>
    </tr>`).join('');

  const printWindow = window.open('', '_blank', 'width=1100,height=800');
  if (!printWindow) { alert('Popup diblokir browser. Izinkan popup untuk print.'); return; }
  printWindow.document.write(`<!DOCTYPE html><html><head>
    <title>Daftar Uang Jalan</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; color: #111; }
      h1 { text-align: center; font-size: 20px; margin-bottom: 4px; }
      .meta { text-align: center; color: #555; margin-bottom: 20px; font-size: 12px; }
      table { width: 100%; border-collapse: collapse; font-size: 11px; }
      th, td { border: 1px solid #cbd5e1; padding: 6px 8px; }
      th { background: #334155; color: white; }
      .num { text-align: right; }
      tfoot td { background: #f1f5f9; font-weight: 700; }
      @media print { body { padding: 0; } }
    </style>
  </head><body>
    <h1>Daftar Uang Jalan</h1>
    <p class="meta">${period} | Dicetak: ${new Date().toLocaleString('id-ID')}</p>
    <table>
      <thead><tr><th>No</th><th>Tanggal</th><th>No. Transaksi</th><th>Kendaraan</th><th>Sopir</th><th>Customer</th><th>Jenis</th><th class="num">Uang Jalan</th><th class="num">Biaya Rute</th><th class="num">Tambahan</th><th class="num">Pembulatan</th><th class="num">Total</th></tr></thead>
      <tbody>${tableRows}</tbody>
      <tfoot><tr><td colspan="7" class="num">TOTAL</td><td class="num">${formatIDR(totalBase)}</td><td class="num">${formatIDR(enriched.reduce((s, r) => s + r._routeFees, 0))}</td><td class="num">${formatIDR(enriched.reduce((s, r) => s + r._extra, 0))}</td><td class="num">${formatIDR(totalRounding)}</td><td class="num">${formatIDR(totalAll)}</td></tr></tfoot>
    </table>
  </body></html>`);
  printWindow.document.close();
  printWindow.onload = () => { printWindow.focus(); printWindow.print(); };
}

export function exportBulkSalesPdf(sales, { fromLabel, toLabel } = {}) {
  const enriched = sales.map(enrichSaleRow);
  const totalBase = enriched.reduce((s, r) => s + r._base, 0);
  const totalRounding = enriched.reduce((s, r) => s + r._rounding, 0);
  const totalAll = enriched.reduce((s, r) => s + r._total, 0);
  const period = fromLabel && toLabel ? `${fromLabel} – ${toLabel}` : '';

  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const pageW = pdf.internal.pageSize.getWidth();
  pdf.setFontSize(16);
  pdf.text('Daftar Uang Jalan', pageW / 2, 14, { align: 'center' });
  pdf.setFontSize(10);
  pdf.setTextColor(100);
  pdf.text(`${period} | Dicetak: ${new Date().toLocaleString('id-ID')}`, pageW / 2, 20, { align: 'center' });
  pdf.setTextColor(0);

  autoTable(pdf, {
    startY: 26,
    head: [['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis', 'Uang Jalan', 'Biaya Rute', 'Tambahan', 'Pembulatan', 'Total']],
    body: enriched.map((s, i) => [
      i + 1, formatDateId(s.date), s.sale_no, s.vehicle_plate || '-', s._driverBankInfo ? `${s.driver_name || '-'}\nRek: ${s._driverBankInfo}` : s.driver_name || '-',
      s._customers, s._vehicleType, formatIDR(s._base), formatIDR(s._routeFees), formatIDR(s._extra), formatIDR(s._rounding), formatIDR(s._total),
    ]),
    foot: [[
      { content: 'TOTAL', colSpan: 7, styles: { halign: 'right', fontStyle: 'bold' } },
      { content: formatIDR(totalBase), styles: { halign: 'right', fontStyle: 'bold' } },
      { content: formatIDR(enriched.reduce((s, r) => s + r._routeFees, 0)), styles: { halign: 'right', fontStyle: 'bold' } },
      { content: formatIDR(enriched.reduce((s, r) => s + r._extra, 0)), styles: { halign: 'right', fontStyle: 'bold' } },
      { content: formatIDR(totalRounding), styles: { halign: 'right', fontStyle: 'bold' } },
      { content: formatIDR(totalAll), styles: { halign: 'right', fontStyle: 'bold' } },
    ]],
    styles: { fontSize: 8, cellPadding: 2, lineColor: [203, 213, 225], lineWidth: 0.1 },
    headStyles: { fillColor: [51, 65, 85], textColor: 255, fontStyle: 'bold', halign: 'center' },
    footStyles: { fillColor: [241, 245, 249], textColor: 20, fontStyle: 'bold' },
  });

  const stamp = new Date().toISOString().slice(0, 10);
  pdf.save(`daftar-uang-jalan-${stamp}.pdf`);
}

export function exportBulkSalesExcel(sales, { fromLabel, toLabel } = {}) {
  const enriched = sales.map(enrichSaleRow);
  const totalBase = enriched.reduce((s, r) => s + r._base, 0);
  const totalRounding = enriched.reduce((s, r) => s + r._rounding, 0);
  const totalAll = enriched.reduce((s, r) => s + r._total, 0);
  const period = fromLabel && toLabel ? `${fromLabel} – ${toLabel}` : '';

  const rows = [
    ['Daftar Uang Jalan'],
    [period ? `Periode: ${period}` : `Dicetak: ${new Date().toLocaleString('id-ID')}`],
    [],
    ['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis Kendaraan', 'Uang Jalan', 'Biaya Rute', 'Tambahan', 'Pembulatan', 'Total'],
    ...enriched.map((s, i) => [
      i + 1, formatDateId(s.date), s.sale_no, s.vehicle_plate || '-', s._driverBankInfo ? `${s.driver_name || '-'} (Rek: ${s._driverBankInfo})` : s.driver_name || '-',
      s._customers, s._vehicleType, s._base, s._routeFees, s._extra, s._rounding, s._total,
    ]),
    [],
    ['', '', '', '', '', '', 'TOTAL', totalBase, enriched.reduce((s, r) => s + r._routeFees, 0), enriched.reduce((s, r) => s + r._extra, 0), totalRounding, totalAll],
  ];

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws['!cols'] = [
    { wch: 5 }, { wch: 16 }, { wch: 22 }, { wch: 14 }, { wch: 16 },
    { wch: 30 }, { wch: 16 }, { wch: 16 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 18 },
  ];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Uang Jalan');
  const stamp = new Date().toISOString().slice(0, 10);
  XLSX.writeFile(wb, `daftar-uang-jalan-${stamp}.xlsx`);
}

function fileBaseName(doc) {
  const no = doc.saleNo.replace(/[^\w-]/g, '_');
  return no === '_Auto_Generate_' ? `uang-jalan-${Date.now()}` : no;
}

const signaturePrintHtml = `
  <div class="signatures">
    <div class="sign-box">
      <p class="sign-role">Pembuat</p>
      <div class="sign-line"></div>
      <p class="sign-name">&nbsp;</p>
    </div>
    <div class="sign-box">
      <p class="sign-role">Penerima</p>
      <div class="sign-line"></div>
      <p class="sign-name">&nbsp;</p>
    </div>
  </div>`;

function addSignatureToPdf(pdf, startY) {
  const y = startY + 18;
  pdf.setFontSize(10);
  pdf.text('Pembuat', 52, y, { align: 'center' });
  pdf.text('Penerima', 158, y, { align: 'center' });
  pdf.line(22, y + 22, 82, y + 22);
  pdf.line(128, y + 22, 188, y + 22);
  pdf.setFontSize(9);

}

function signatureExcelRows() {
  return [
    [],
    ['Pembuat', '', 'Penerima'],
    ['', '', ''],
    ['', '', ''],

  ];
}

function buildSummaryRows(doc) {
  return [
    [{ content: 'Total Uang Jalan', styles: { fontStyle: 'bold' } }, { content: formatIDR(doc.totalUangJalan), styles: { fontStyle: 'bold', halign: 'right', fontSize: 11 } }],
  ];
}

function buildSummaryHtml(doc) {
  return `
    <table class="data" style="margin-top:16px;">
      <tbody>
        <tr>
          <td style="width:60%"><strong>Total Uang Jalan</strong></td>
          <td style="text-align:right;font-size:15px;"><strong>${formatIDR(doc.totalUangJalan)}</strong></td>
        </tr>
      </tbody>
    </table>`;
}

export function printSaleDocument(doc) {
  const printWindow = window.open('', '_blank', 'width=900,height=700');
  if (!printWindow) {
    alert('Popup diblokir browser. Izinkan popup untuk print.');
    return;
  }

  // Customer list (numbered)
  const customerListHtml = doc.customerNames
    .map((name, i) => `<tr><td style="text-align:center">${i + 1}</td><td>${name}</td></tr>`)
    .join('');

  printWindow.document.write(`
    <!DOCTYPE html>
    <html><head>
      <title>${doc.title} - ${doc.saleNo}</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 24px; color: #111; }
        h1 { text-align: center; margin-bottom: 4px; font-size: 22px; }
        .meta { text-align: center; color: #555; margin-bottom: 24px; font-size: 13px; }
        .info { width: 100%; margin-bottom: 20px; border-collapse: collapse; }
        .info td { padding: 6px 8px; vertical-align: top; }
        .info td:first-child { width: 160px; font-weight: 600; }
        table.data { width: 100%; border-collapse: collapse; margin-top: 8px; }
        table.data th, table.data td { border: 1px solid #ccc; padding: 8px; font-size: 13px; }
        table.data th { background: #f1f5f9; text-align: left; }
        .section-title { margin: 16px 0 8px; font-size: 14px; font-weight: 600; color: #333; }
        .signatures { display: flex; justify-content: space-between; margin-top: 48px; gap: 24px; }
        .sign-box { flex: 1; text-align: center; }
        .sign-role { font-weight: 600; margin-bottom: 8px; }
        .sign-line { border-bottom: 1px solid #111; height: 64px; margin: 0 auto 8px; max-width: 260px; }
        .sign-name { font-size: 12px; color: #444; margin: 0; }
      </style>
    </head><body>
      <h1>${doc.title}</h1>
      <p class="meta">Dicetak: ${doc.printedAt}</p>
      <table class="info">
        <tr><td>Nomor Transaksi</td><td>${doc.saleNo}</td></tr>
        <tr><td>Tanggal</td><td>${doc.date}</td></tr>
        <tr><td>Kendaraan</td><td>${doc.vehicle}</td></tr>
        <tr><td>Sopir</td><td>${doc.driver}</td></tr>
        <tr><td>Jenis Kendaraan</td><td><strong>${doc.vehicleTypeHeader}</strong></td></tr>
        <tr><td>Keterangan</td><td>${doc.remarks}</td></tr>
      </table>
      <p class="section-title">Tujuan Pengiriman</p>
      <table class="data">
        <thead><tr><th style="width:40px;text-align:center">No</th><th>Customer</th></tr></thead>
        <tbody>${customerListHtml || '<tr><td colspan="2">Belum ada data customer</td></tr>'}</tbody>
      </table>
      ${buildSummaryHtml(doc)}
      ${signaturePrintHtml}
    </body></html>
  `);
  printWindow.document.close();
  printWindow.onload = () => {
    printWindow.focus();
    printWindow.print();
  };
}

export function exportSalePdf(doc) {
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  pdf.setFontSize(16);
  pdf.text(doc.title, 105, 16, { align: 'center' });
  pdf.setFontSize(10);
  pdf.setTextColor(100);
  pdf.text(`Dicetak: ${doc.printedAt}`, 105, 22, { align: 'center' });
  pdf.setTextColor(0);

  const meta = [
    ['Nomor Transaksi', doc.saleNo],
    ['Tanggal', doc.date],
    ['Kendaraan', doc.vehicle],
    ['Sopir', doc.driver],
    ['Jenis Kendaraan', doc.vehicleTypeHeader],
    ['Keterangan', doc.remarks],
  ];

  autoTable(pdf, {
    startY: 28,
    body: meta,
    theme: 'plain',
    styles: { fontSize: 10, cellPadding: 1.5 },
    columnStyles: { 0: { fontStyle: 'bold', cellWidth: 45 } },
  });

  // Customer list table
  const customerTable = doc.customerNames.map((name, i) => [String(i + 1), name]);

  pdf.setFontSize(11);
  pdf.text('Tujuan Pengiriman', 14, pdf.lastAutoTable.finalY + 8);

  autoTable(pdf, {
    startY: pdf.lastAutoTable.finalY + 12,
    head: [['No', 'Customer']],
    body: customerTable.length ? customerTable : [['', 'Belum ada data customer']],
    styles: { fontSize: 9 },
    headStyles: { fillColor: [241, 245, 249], textColor: 20 },
    columnStyles: { 0: { cellWidth: 15, halign: 'center' } },
  });

  // Summary table
  const summaryBody = buildSummaryRows(doc);

  autoTable(pdf, {
    startY: pdf.lastAutoTable.finalY + 6,
    body: summaryBody,
    theme: 'grid',
    styles: { fontSize: 10, cellPadding: 3 },
    columnStyles: { 0: { cellWidth: 100 } },
  });

  addSignatureToPdf(pdf, pdf.lastAutoTable.finalY);

  pdf.save(`${fileBaseName(doc)}.pdf`);
}

export function exportSaleExcel(doc) {
  const rows = [
    [doc.title],
    [`Dicetak: ${doc.printedAt}`],
    [],
    ['Nomor Transaksi', doc.saleNo],
    ['Tanggal', doc.date],
    ['Kendaraan', doc.vehicle],
    ['Sopir', doc.driver],
    ['Jenis Kendaraan', doc.vehicleTypeHeader],
    ['Keterangan', doc.remarks],
    [],
    ['Tujuan Pengiriman'],
    ['No', 'Customer'],
    ...doc.customerNames.map((name, i) => [i + 1, name]),
    [],
    ['Total Uang Jalan', '', doc.totalUangJalan],
  ];

  rows.push(...signatureExcelRows());

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws['!cols'] = [{ wch: 36 }, { wch: 28 }, { wch: 18 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Uang Jalan');
  XLSX.writeFile(wb, `${fileBaseName(doc)}.xlsx`);
}
