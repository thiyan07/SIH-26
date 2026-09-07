import { useState, useEffect } from 'react'
import { Card, CardHeader } from '../components/ui'
import { PageHeader } from '../components/PageHeader'
import { downloadJSON } from '../lib/export'
import { useAnalysis } from '../lib/analysisStore'

export function Security() {
  const [twoFA, setTwoFA] = useState(()=> localStorage.getItem('grambiz.2fa')==='1')
  const [shareData, setShareData] = useState(()=> localStorage.getItem('grambiz.share')!=='0')
  const { result } = useAnalysis()
  useEffect(()=> localStorage.setItem('grambiz.2fa', twoFA?'1':'0'), [twoFA])
  useEffect(()=> localStorage.setItem('grambiz.share', shareData?'1':'0'), [shareData])

  const exportData = () => {
    const data = {
      profile: JSON.parse(localStorage.getItem('grambiz.profile')||'{}'),
      expenses: JSON.parse(localStorage.getItem('grambiz.expenses')||'[]'),
      history: JSON.parse(localStorage.getItem('grambiz.history')||'[]'),
      result,
      exportedAt: new Date().toISOString(),
    }
    downloadJSON(`grambiz-data-${Date.now()}.json`, data)
  }

  const deleteAll = () => {
    if (!confirm('Delete all local data? This cannot be undone. Type OK to confirm.')) return
    const ok = prompt('Type DELETE to confirm')
    if (ok!=='DELETE') { alert('Cancelled'); return }
    localStorage.clear()
    alert('Local data cleared — reload app')
    location.reload()
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Secure • Private" title="Security & Privacy" desc="Your data stays in your browser. Control what you share and export or delete anytime." />
      <Card>
        <CardHeader title="Two-Factor Demo" subtitle="Extra protection for loan actions (demo, no SMS)" />
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-700 dark:text-slate-200">Require OTP for Generate Report</div>
          <button
            data-testid="2fa-toggle"
            onClick={()=>setTwoFA(v=>!v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${twoFA ? 'bg-brand-600' : 'bg-slate-200'}`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${twoFA ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
        </div>
        {twoFA && (
          <div data-testid="2fa-code" className="mt-3 rounded-xl bg-slate-50 p-3 text-center dark:bg-slate-800">
            <div className="text-xs text-slate-500">Demo OTP</div>
            <div className="text-2xl font-mono font-bold tracking-widest text-slate-900 dark:text-white">{Math.floor(100000 + Math.random()*900000)}</div>
            <div className="text-[11px] text-slate-500">Valid for 5 min • demo only</div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Data Sharing" subtitle="Control anonymized usage for improving GramBiz" />
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-700 dark:text-slate-200">Share anonymized analytics</div>
          <button
            data-testid="share-toggle"
            onClick={()=>setShareData(v=>!v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${shareData ? 'bg-brand-600' : 'bg-slate-200'}`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${shareData ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">When off, no usage pings are sent. All analysis stays local.</p>
      </Card>

      <Card>
        <CardHeader title="Your Data" subtitle="Export or delete everything stored locally" />
        <div className="flex flex-wrap gap-2">
          <button data-testid="export-data" onClick={exportData} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white hover:bg-slate-800">Export all data (JSON)</button>
          <button data-testid="delete-data" onClick={deleteAll} className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-bold text-red-600 hover:bg-red-100">Delete all local data</button>
        </div>
        <p className="mt-2 text-xs text-slate-500">Includes profile, expenses, history and last analysis. Never uploaded without your consent.</p>
      </Card>

      <Card>
        <CardHeader title="Privacy Note" subtitle="GDPR-style plain language" />
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-300">
          <li>Location is used only to find nearby businesses — not tracked.</li>
          <li>Documents in Vault are stored in browser `localStorage` only.</li>
          <li>AI calls send only the analysis evidence you choose — no personal identifiers.</li>
        </ul>
      </Card>
    </div>
  )
}
