import sys
import re

file_path = r"d:\Programer\Uang Pengiriman\frontend\src\pages\Reports.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add total computations
old_summary_code = """  const handleExportPdf = () => {"""
new_summary_code = """  const totalDriverTrip = Object.values(driverSummary).reduce((acc, curr) => acc + curr.count, 0);
  const totalDriverAmount = Object.values(driverSummary).reduce((acc, curr) => acc + curr.total, 0);
  const totalCustomerTrip = Object.values(customerSummary).reduce((acc, curr) => acc + curr.count, 0);
  const totalCustomerAmount = Object.values(customerSummary).reduce((acc, curr) => acc + curr.total, 0);

  const handleExportPdf = () => {"""
content = content.replace(old_summary_code, new_summary_code)

# 2. Update PDF Export
old_pdf_driver = """        head: [['Ringkasan per Sopir', 'Trip', 'Total']],
        body: Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, formatIDR(data.total)]),
        styles:"""
new_pdf_driver = """        head: [['Ringkasan per Sopir', 'Trip', 'Total']],
        body: Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, formatIDR(data.total)]),
        foot: [[{ content: 'TOTAL', styles: { halign: 'left', fontStyle: 'bold' } }, { content: totalDriverTrip, styles: { halign: 'center', fontStyle: 'bold' } }, { content: formatIDR(totalDriverAmount), styles: { halign: 'right', fontStyle: 'bold' } }]],
        styles:"""
content = content.replace(old_pdf_driver, new_pdf_driver)

old_pdf_customer = """        head: [['Ringkasan per Customer', 'Trip', 'Total']],
        body: Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, formatIDR(data.total)]),
        styles:"""
new_pdf_customer = """        head: [['Ringkasan per Customer', 'Trip', 'Total']],
        body: Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, formatIDR(data.total)]),
        foot: [[{ content: 'TOTAL', styles: { halign: 'left', fontStyle: 'bold' } }, { content: totalCustomerTrip, styles: { halign: 'center', fontStyle: 'bold' } }, { content: formatIDR(totalCustomerAmount), styles: { halign: 'right', fontStyle: 'bold' } }]],
        styles:"""
content = content.replace(old_pdf_customer, new_pdf_customer)

# 3. Update Excel Export
old_excel_driver = """      ...Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
        [], []
      );"""
new_excel_driver = """      ...Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
        ['TOTAL', totalDriverTrip, totalDriverAmount],
        [], []
      );"""
content = content.replace(old_excel_driver, new_excel_driver)

old_excel_customer = """        ...Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total])
      );"""
new_excel_customer = """        ...Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => [name, data.count, data.total]),
        ['TOTAL', totalCustomerTrip, totalCustomerAmount]
      );"""
content = content.replace(old_excel_customer, new_excel_customer)

# 4. Update Print Export
old_print_driver = """              ${Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => `<tr><td>${name}</td><td class="center">${data.count}</td><td class="num">${formatIDR(data.total)}</td></tr>`).join('')}
            </tbody>
          </table>"""
new_print_driver = """              ${Object.entries(driverSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => `<tr><td>${name}</td><td class="center">${data.count}</td><td class="num">${formatIDR(data.total)}</td></tr>`).join('')}
            </tbody>
            <tfoot><tr><td>TOTAL</td><td class="center">${totalDriverTrip}</td><td class="num">${formatIDR(totalDriverAmount)}</td></tr></tfoot>
          </table>"""
content = content.replace(old_print_driver, new_print_driver)

old_print_customer = """              ${Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => `<tr><td>${name}</td><td class="center">${data.count}</td><td class="num">${formatIDR(data.total)}</td></tr>`).join('')}
            </tbody>
          </table>"""
new_print_customer = """              ${Object.entries(customerSummary).sort((a, b) => b[1].total - a[1].total).map(([name, data]) => `<tr><td>${name}</td><td class="center">${data.count}</td><td class="num">${formatIDR(data.total)}</td></tr>`).join('')}
            </tbody>
            <tfoot><tr><td>TOTAL</td><td class="center">${totalCustomerTrip}</td><td class="num">${formatIDR(totalCustomerAmount)}</td></tr></tfoot>
          </table>"""
content = content.replace(old_print_customer, new_print_customer)

# 5. Update UI (Driver)
old_ui_driver = """                {Object.keys(driverSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
            </table>"""
new_ui_driver = """                {Object.keys(driverSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
              {Object.keys(driverSummary).length > 0 && (
                <tfoot style={{ background: 'var(--bg-secondary)', fontWeight: 'bold' }}>
                  <tr>
                    <td>TOTAL</td>
                    <td style={{ textAlign: 'center' }}>{totalDriverTrip}</td>
                    <td style={{ textAlign: 'right' }}>{formatIDR(totalDriverAmount)}</td>
                  </tr>
                </tfoot>
              )}
            </table>"""
content = content.replace(old_ui_driver, new_ui_driver)

# 6. Update UI (Customer)
old_ui_customer = """                {Object.keys(customerSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
            </table>"""
new_ui_customer = """                {Object.keys(customerSummary).length === 0 && (
                  <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.5, padding: '1.5rem' }}>Belum ada data</td></tr>
                )}
              </tbody>
              {Object.keys(customerSummary).length > 0 && (
                <tfoot style={{ background: 'var(--bg-secondary)', fontWeight: 'bold' }}>
                  <tr>
                    <td>TOTAL</td>
                    <td style={{ textAlign: 'center' }}>{totalCustomerTrip}</td>
                    <td style={{ textAlign: 'right' }}>{formatIDR(totalCustomerAmount)}</td>
                  </tr>
                </tfoot>
              )}
            </table>"""
content = content.replace(old_ui_customer, new_ui_customer)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updates applied to Reports.jsx successfully!")
