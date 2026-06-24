import sys

file_path = r"d:\Programer\Uang Pengiriman\frontend\src\pages\Reports.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add exportType state
content = content.replace(
    "const [summaryFilter, setSummaryFilter] = useState(null);",
    "const [summaryFilter, setSummaryFilter] = useState(null);\n  const [exportType, setExportType] = useState('all');"
)

# 2. Update PDF export
old_pdf_code = """    const summaryCol = tableWidth / 4;

    autoTable(pdf, {"""
new_pdf_code = """    const summaryCol = tableWidth / 4;

    if (exportType === 'all' || exportType === 'detail') {
      autoTable(pdf, {"""

content = content.replace(old_pdf_code, new_pdf_code)

content = content.replace("""        didParseCell(data) {
          if (data.section === 'head' && [7, 8, 9, 10].includes(data.column.index)) {
            data.cell.styles.halign = 'right';
          }
        },
    });

    autoTable(pdf, {
      startY: pdf.lastAutoTable.finalY + 10,""", """        didParseCell(data) {
          if (data.section === 'head' && [7, 8, 9, 10].includes(data.column.index)) {
            data.cell.styles.halign = 'right';
          }
        },
      });
    }

    if (exportType === 'all' || exportType === 'driver') {
      autoTable(pdf, {
        startY: pdf.lastAutoTable ? pdf.lastAutoTable.finalY + 10 : 26,""")

content = content.replace("""    autoTable(pdf, {
      startY: pdf.lastAutoTable.finalY + 10,
      margin: { left: marginX, right: marginX },
      tableWidth,
      head: [['Ringkasan per Customer', 'Trip', 'Total']],""", """    }

    if (exportType === 'all' || exportType === 'customer') {
      autoTable(pdf, {
        startY: pdf.lastAutoTable ? pdf.lastAutoTable.finalY + 10 : 26,
        margin: { left: marginX, right: marginX },
        tableWidth,
        head: [['Ringkasan per Customer', 'Trip', 'Total']],""")

content = content.replace("""      headStyles: { fillColor: [51, 65, 85], textColor: 255, fontStyle: 'bold', halign: 'center', cellPadding: 4 },
      columnStyles: { 1: { halign: 'center', cellWidth: 30 }, 2: { halign: 'right', cellWidth: 40 } }
    });

    pdf.save(`laporan-uang-jalan-${fromDate}-${toDate}.pdf`);""", """      headStyles: { fillColor: [51, 65, 85], textColor: 255, fontStyle: 'bold', halign: 'center', cellPadding: 4 },
      columnStyles: { 1: { halign: 'center', cellWidth: 30 }, 2: { halign: 'right', cellWidth: 40 } }
      });
    }

    pdf.save(`laporan-uang-jalan-${fromDate}-${toDate}.pdf`);""")

# 3. Update Excel export
old_excel_code = """  const handleExportExcel = () => {
    const rows = [
      ['Laporan Uang Jalan'],
      [`Periode: ${formatDate(fromDate)} - ${formatDate(toDate)}`],
      [`Dicetak: ${new Date().toLocaleString('id-ID')}`],
      [],
      ['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis Kendaraan', 'Uang Jalan', 'Tambahan', 'Pembulatan', 'Total Uang Jalan'],"""
new_excel_code = """  const handleExportExcel = () => {
    const rows = [
      ['Laporan Uang Jalan'],
      [`Periode: ${formatDate(fromDate)} - ${formatDate(toDate)}`],
      [`Dicetak: ${new Date().toLocaleString('id-ID')}`],
      [],
    ];

    if (exportType === 'all' || exportType === 'detail') {
      rows.push(
        ['No', 'Tanggal', 'No. Transaksi', 'Kendaraan', 'Sopir', 'Customer', 'Jenis Kendaraan', 'Uang Jalan', 'Tambahan', 'Pembulatan', 'Total Uang Jalan'],"""
content = content.replace(old_excel_code, new_excel_code)

content = content.replace("""      [],
      ['', '', '', '', '', '', 'TOTAL', totalBaseUangJalan, totalExtra, totalRounding, totalUangJalan],
      [], [],
      ['Ringkasan per Sopir', '', ''],""", """      [],
        ['', '', '', '', '', '', 'TOTAL', totalBaseUangJalan, totalExtra, totalRounding, totalUangJalan],
        [], []
      );
    }

    if (exportType === 'all' || exportType === 'driver') {
      rows.push(
        ['Ringkasan per Sopir', '', ''],""")

content = content.replace("""      ...Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
      [], [],
      ['Ringkasan per Customer', '', ''],""", """      ...Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
        [], []
      );
    }

    if (exportType === 'all' || exportType === 'customer') {
      rows.push(
        ['Ringkasan per Customer', '', ''],""")

content = content.replace("""      ['Customer', 'Trip', 'Total'],
      ...Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
    ];

    const ws = XLSX.utils.aoa_to_sheet(rows);""", """      ['Customer', 'Trip', 'Total'],
        ...Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total])
      );
    }

    const ws = XLSX.utils.aoa_to_sheet(rows);""")

# 4. Update Print export
content = content.replace("""      <div class="summary">
        <div class="summary-card"><label>Total Transaksi</label><h2>${totalTransaksi}</h2></div>
        <div class="summary-card"><label>Total Uang Jalan</label><h2>${formatIDR(totalUangJalan)}</h2></div>
        <div class="summary-card"><label>Total Pembulatan</label><h2>${formatIDR(totalRounding)}</h2></div>
      </div>
      <table>""", """      <div class="summary">
        <div class="summary-card"><label>Total Transaksi</label><h2>${totalTransaksi}</h2></div>
        <div class="summary-card"><label>Total Uang Jalan</label><h2>${formatIDR(totalUangJalan)}</h2></div>
        <div class="summary-card"><label>Total Pembulatan</label><h2>${formatIDR(totalRounding)}</h2></div>
      </div>
      ${(exportType === 'all' || exportType === 'detail') ? `
      <table>""")

content = content.replace("""        <tfoot><tr><td colspan="7" class="num">TOTAL</td><td class="num">${formatIDR(totalBaseUangJalan)}</td><td class="num">${formatIDR(totalExtra)}</td><td class="num">${formatIDR(totalRounding)}</td><td class="num">${formatIDR(totalUangJalan)}</td></tr></tfoot>
      </table>

      <div style="display: flex; gap: 20px; margin-top: 20px; page-break-inside: avoid;">
        <div style="flex: 1;">""", """        <tfoot><tr><td colspan="7" class="num">TOTAL</td><td class="num">${formatIDR(totalBaseUangJalan)}</td><td class="num">${formatIDR(totalExtra)}</td><td class="num">${formatIDR(totalRounding)}</td><td class="num">${formatIDR(totalUangJalan)}</td></tr></tfoot>
      </table>` : ''}

      ${(exportType === 'all' || exportType === 'driver' || exportType === 'customer') ? `
      <div style="display: flex; gap: 20px; margin-top: 20px; page-break-inside: avoid;">
        ${(exportType === 'all' || exportType === 'driver') ? `
        <div style="flex: 1;">""")

content = content.replace("""            </tbody>
          </table>
        </div>
        <div style="flex: 1;">
          <h3 style="font-size: 14px; margin-bottom: 8px; color: #334155;">Ringkasan per Customer</h3>""", """            </tbody>
          </table>
        </div>` : ''}
        ${(exportType === 'all' || exportType === 'customer') ? `
        <div style="flex: 1;">
          <h3 style="font-size: 14px; margin-bottom: 8px; color: #334155;">Ringkasan per Customer</h3>""")

content = content.replace("""            </tbody>
          </table>
        </div>
      </div>
    </body></html>`);""", """            </tbody>
          </table>
        </div>` : ''}
      </div>` : ''}
    </body></html>`);""")

# 5. UI dropdown update
content = content.replace("""        {activeTab === 'sales' && canSalesReport && (
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button className="btn btn-secondary" onClick={handlePrint}""", """        {activeTab === 'sales' && canSalesReport && (
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <select 
              className="form-input" 
              style={{ marginBottom: 0, padding: '0.4rem 2rem 0.4rem 0.75rem', fontSize: '0.85rem' }} 
              value={exportType} 
              onChange={(e) => setExportType(e.target.value)}
            >
              <option value="all">Semua Laporan</option>
              <option value="detail">Detail Uang Jalan</option>
              <option value="driver">Ringkasan Sopir</option>
              <option value="customer">Ringkasan Customer</option>
            </select>
            <button className="btn btn-secondary" onClick={handlePrint}""")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updates applied to Reports.jsx successfully!")
