import { useState, useEffect } from 'react'
import { Card, CardHeader } from '../components/ui'
import { PageHeader } from '../components/PageHeader'

type Doc = { id: string; name: string; type: string; size: number; date: string; preview?: string }

export function DocumentVault() {
  const [docs, setDocs] = useState<Doc[]>(()=>{
    try { return JSON.parse(localStorage.getItem('grambiz.docs')||'[]') } catch { return [] }
  })
  const [dragOver, setDragOver] = useState(false)
  useEffect(()=>{ localStorage.setItem('grambiz.docs', JSON.stringify(docs)) }, [docs])

  const onFiles = (files: FileList | null) => {
    if (!files) return
    Array.from(files).forEach(f=>{
      const reader = new FileReader()
      reader.onload = () => {
        const preview = f.type.startsWith('image/') ? reader.result as string : undefined
        setDocs(prev=> [{ id: Date.now()+Math.random().toString(), name: f.name, type: f.type || 'unknown', size: f.size, date: new Date().toLocaleDateString(), preview }, ...prev])
      }
      if (f.type.startsWith('image/')) reader.readAsDataURL(f); else reader.onload(null as any)
      if (!f.type.startsWith('image/')) {
        setDocs(prev=> [{ id: Date.now()+Math.random().toString(), name: f.name, type: f.type, size: f.size, date: new Date().toLocaleDateString() }, ...prev])
      }
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Secure • Local" title="Document Vault" desc="Aadhaar, land record, bank passbook — kept locally in your browser, never uploaded." />
      <Card>
        <div
          data-testid="vault-drop"
          onDragOver={e=>{ e.preventDefault(); setDragOver(true)}}
          onDragLeave={()=>setDragOver(false)}
          onDrop={e=>{ e.preventDefault(); setDragOver(false); onFiles(e.dataTransfer.files)}}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center ${dragOver ? 'border-brand-600 bg-brand-50' : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800'}`}
        >
          <div className="text-2xl">📁</div>
          <div className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Drag & drop or click to upload</div>
          <div className="text-xs text-slate-500">PDF, JPG, PNG — max 5MB (stored locally)</div>
          <label className="mt-3 cursor-pointer rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white">
            Choose files
            <input data-testid="vault-input" type="file" multiple className="hidden" onChange={e=>onFiles(e.target.files)} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Your documents (${docs.length})`} subtitle="Preview, download or delete" />
        {docs.length===0 ? <p className="text-sm text-slate-500">No documents yet — upload your Aadhaar or passbook scan.</p> : (
          <div className="grid gap-3 md:grid-cols-2">
            {docs.map(d=>(
              <div key={d.id} data-testid="vault-item" className="flex gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                {d.preview ? <img src={d.preview} alt={d.name} className="h-12 w-12 rounded-lg object-cover" /> : <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 text-lg dark:bg-slate-700">📄</div>}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-slate-900 dark:text-white">{d.name}</div>
                  <div className="text-xs text-slate-500">{d.type} • {(d.size/1024).toFixed(1)}KB • {d.date}</div>
                </div>
                <button
                  data-testid={`vault-delete-${d.id}`}
                  onClick={()=>{
                    if (confirm(`Delete ${d.name}?`)) setDocs(prev=> prev.filter(x=>x.id!==d.id))
                  }}
                  className="self-center rounded-lg bg-red-50 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-100"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
