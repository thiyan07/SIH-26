export function downloadCSV(filename: string, rows: (string|number)[][]) {
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function downloadJSON(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function printElement(id: string) {
  const el = document.getElementById(id)
  if (!el) { window.print(); return }
  const w = window.open('', '_blank')
  if (!w) { window.print(); return }
  w.document.write(`<html><head><title>GramBiz Report</title><style>body{font-family:system-ui;padding:20px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ddd;padding:6px;font-size:12px} h1{font-size:20px}</style></head><body>${el.innerHTML}</body></html>`)
  w.document.close()
  w.focus()
  w.print()
}
