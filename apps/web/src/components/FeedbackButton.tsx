import { useState } from 'react'

export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen(v => !v)}
        className="fixed bottom-4 right-4 z-40 rounded-full bg-brand-600 p-3 text-white shadow-lg hover:bg-brand-700"
        title="Feedback"
      >
        💬
      </button>
      {open && (
        <div className="fixed bottom-16 right-4 z-40 w-80 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
          <div className="text-sm font-bold text-slate-900">Feedback</div>
          <p className="text-xs text-slate-500">As client, your feedback shapes the next feature.</p>
          <textarea value={text} onChange={e=>setText(e.target.value)} rows={3} placeholder="What would you like as a client?" className="mt-2 w-full rounded-xl border border-slate-200 p-2 text-sm" />
          <div className="mt-2 flex gap-2">
            <button onClick={()=>{ if(text.trim()){ setSent(true); setText(''); setTimeout(()=>setOpen(false),1500) }}} className="rounded-xl bg-slate-900 px-3 py-1.5 text-xs font-bold text-white">Send</button>
            <button onClick={()=>setOpen(false)} className="rounded-xl bg-slate-100 px-3 py-1.5 text-xs">Close</button>
          </div>
          {sent && <div className="mt-2 text-xs font-medium text-emerald-600">Thanks! Saved locally.</div>}
        </div>
      )}
    </>
  )
}
