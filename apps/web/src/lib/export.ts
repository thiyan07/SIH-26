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
  // Collect existing stylesheets to preserve Tailwind / app styles
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
    .map(s => s.outerHTML)
    .join('\n')
  const printCSS = `
    <style>
      @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        #report-print { max-width: 100% !important; }
        .space-y-6 > * + * { margin-top: 1rem !important; }
        .grid { display: block !important; }
        .grid > * + * { margin-top: 0.75rem !important; }
        .h-\\[300px\\] { height: 220px !important; }
        .leaflet-container { max-height: 220px !important; overflow: hidden !important; }
        /* Prevent card overlap */
        .rounded-xl, .rounded-2xl, .border { break-inside: avoid; page-break-inside: avoid; }
        /* Hide interactive controls in print */
        button, a[href="/videos"] { display: none !important; }
        body { padding: 12px !important; font-family: system-ui, -apple-system, sans-serif !important; }
        table { border-collapse: collapse; width: 100%; }
        td, th { border: 1px solid #e5e7eb; padding: 6px; font-size: 11px; }
        h1 { font-size: 18px; margin-bottom: 4px; }
      }
      @page { margin: 12mm; }
      body { font-family: system-ui, -apple-system, sans-serif; padding: 16px; color: #1e293b; line-height: 1.5; }
      /* Screen styles for print window */
      .space-y-6 > * + * { margin-top: 1rem; }
      table { border-collapse: collapse; width: 100%; }
      td, th { border: 1px solid #e5e7eb; padding: 6px; font-size: 11px; }
      h1 { font-size: 18px; }
    </style>
  `
  w.document.write(`<html><head><title>GramBiz Report</title>${styles}${printCSS}</head><body><div style="max-width:800px;margin:0 auto;">${el.innerHTML}</div></body></html>`)
  w.document.close()
  // Wait for styles and leaflet tiles to load before printing
  const doPrint = () => { w.focus(); w.print(); }
  if (w.document.readyState === 'complete') {
    setTimeout(doPrint, 400)
  } else {
    w.onload = () => setTimeout(doPrint, 400)
  }
}
