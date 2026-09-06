import { useState } from "react"

type Col<T> = { key: keyof T; header: string; render?: (v: any, row: T) => React.ReactNode; sortable?: boolean; className?: string }

export function DataTable<T extends Record<string, any>>({ data, columns, pageSize = 10, className = "" }: { data: T[]; columns: Col<T>[]; pageSize?: number; className?: string }) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null)
  const [dir, setDir] = useState<"asc" | "desc">("asc")
  const [q, setQ] = useState("")
  const [page, setPage] = useState(0)

  let filtered = data.filter((r) => !q || columns.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q.toLowerCase())))
  if (sortKey) {
    filtered = [...filtered].sort((a, b) => {
      const av = a[sortKey]; const bv = b[sortKey]
      if (av == null) return 1; if (bv == null) return -1
      if (typeof av === "number" && typeof bv === "number") return dir === "asc" ? av - bv : bv - av
      return dir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    })
  }
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const pageData = filtered.slice(page * pageSize, (page + 1) * pageSize)

  const toggle = (k: keyof T) => {
    if (sortKey === k) setDir(dir === "asc" ? "desc" : "asc")
    else { setSortKey(k); setDir("asc") }
  }

  return (
    <div className={className}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} placeholder="Search..." className="w-64 rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:border-brand-300 focus:outline-none" />
        <div className="text-xs text-gray-500">{filtered.length} / {data.length}</div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500">
            <tr>
              {columns.map((c) => (
                <th key={String(c.key)} className={`px-3 py-2 text-left font-medium ${c.className || ""} ${c.sortable !== false ? "cursor-pointer select-none hover:text-gray-700" : ""}`} onClick={() => c.sortable !== false && toggle(c.key)}>
                  {c.header} {sortKey === c.key ? (dir === "asc" ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {pageData.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50">
                {columns.map((c) => (
                  <td key={String(c.key)} className={`px-3 py-2 ${c.className || ""}`}>{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>
                ))}
              </tr>
            ))}
            {pageData.length === 0 && <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-sm text-gray-400">No results</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <button disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded border px-2.5 py-1 disabled:opacity-40">Prev</button>
        <span className="text-gray-500">Page {page + 1} / {totalPages}</span>
        <button disabled={page + 1 >= totalPages} onClick={() => setPage(page + 1)} className="rounded border px-2.5 py-1 disabled:opacity-40">Next</button>
      </div>
    </div>
  )
}
