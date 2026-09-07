

const SUPPLIERS = [
  { name: 'Erode Agro Traders', item: 'Seeds, Fertilizer', dist: '2.3km', phone: '98765 43210', rating: 4.6 },
  { name: 'Perundurai Milk Union', item: 'Milk cans, Fodder', dist: '4.1km', phone: '98765 43211', rating: 4.8 },
  { name: 'Bhavani Textile Mills', item: 'Yarn, Fabric', dist: '7.2km', phone: '98765 43212', rating: 4.5 },
  { name: 'Kongu Packaging', item: 'Boxes, Bags', dist: '5.0km', phone: '98765 43213', rating: 4.7 },
]

export function SupplierMarketplace() {
  return (
    <div data-testid="supplier-marketplace" className="space-y-3">
      <div className="text-sm font-bold text-slate-900 dark:text-white">Supplier Marketplace • {SUPPLIERS.length} near you</div>
      <div className="grid gap-2 md:grid-cols-2">
        {SUPPLIERS.map(s=>(
          <div key={s.name} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white">{s.name}</div>
              <div className="text-xs text-slate-500">{s.item} • {s.dist} • ★ {s.rating}</div>
              <div className="text-xs text-slate-500">{s.phone}</div>
            </div>
            <a href={`https://wa.me/91${s.phone.replace(/\s/g,'')}`} target="_blank" rel="noreferrer" data-testid={`supplier-wa-${s.name}`} className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700">WhatsApp</a>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-500">Mock suppliers — real data via supplier onboarding (P0 for demo)</p>
    </div>
  )
}
