import { useState, useEffect } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Card, CardHeader } from '../components/ui'

type Entry = { id: string; date: string; desc: string; amount: number; type: 'income' | 'expense' }

export function ExpenseTracker() {
  const [entries, setEntries] = useState<Entry[]>(() => {
    try { return JSON.parse(localStorage.getItem('grambiz.expenses') || '[]') } catch { return [] }
  })
  const [desc, setDesc] = useState('')
  const [amount, setAmount] = useState('')
  const [type, setType] = useState<'income'|'expense'>('expense')

  useEffect(() => { localStorage.setItem('grambiz.expenses', JSON.stringify(entries)) }, [entries])

  const add = () => {
    if (!desc || !amount) return
    setEntries(e => [{ id: Date.now().toString(), date: new Date().toLocaleDateString(), desc, amount: parseFloat(amount), type }, ...e])
    setDesc(''); setAmount('')
  }
  const totalIncome = entries.filter(e => e.type==='income').reduce((s,e)=>s+e.amount,0)
  const totalExpense = entries.filter(e => e.type==='expense').reduce((s,e)=>s+e.amount,0)
  const balance = totalIncome - totalExpense

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Client • Finance" title="Daily Bookkeeping" desc="As a shop owner you want a simple ledger — income vs expense, no complicated accounting." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4 text-center"><div className="text-xs text-slate-500">Income</div><div className="text-xl font-bold text-emerald-600">₹{totalIncome.toLocaleString('en-IN')}</div></Card>
        <Card className="p-4 text-center"><div className="text-xs text-slate-500">Expense</div><div className="text-xl font-bold text-red-600">₹{totalExpense.toLocaleString('en-IN')}</div></Card>
        <Card className={`p-4 text-center ${balance>=0?'bg-emerald-50':'bg-red-50'}`}><div className="text-xs text-slate-500">Balance</div><div className={`text-xl font-bold ${balance>=0?'text-emerald-700':'text-red-700'}`}>₹{balance.toLocaleString('en-IN')}</div></Card>
      </div>
      <Card>
        <CardHeader title="Add entry" subtitle="Milk sales, feed purchase, rent, etc." />
        <div className="flex flex-wrap gap-2">
          <input value={desc} onChange={e=>setDesc(e.target.value)} placeholder="Description (e.g. Milk sales)" className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          <input value={amount} onChange={e=>setAmount(e.target.value)} placeholder="Amount" type="number" className="w-32 rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          <select value={type} onChange={e=>setType(e.target.value as any)} className="rounded-xl border border-slate-200 px-3 py-2 text-sm">
            <option value="expense">Expense</option><option value="income">Income</option>
          </select>
          <button onClick={add} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white">Add</button>
        </div>
      </Card>
      <Card>
        <CardHeader title="History" subtitle={`${entries.length} entries`} />
        {entries.length===0 ? <p className="text-sm text-slate-500">No entries yet — add your first sale.</p> : (
          <div className="divide-y divide-slate-100">
            {entries.slice(0,30).map(e=>(
              <div key={e.id} className="flex items-center justify-between py-2 text-sm">
                <div><span className="font-medium text-slate-900">{e.desc}</span> <span className="text-xs text-slate-500">· {e.date}</span></div>
                <span className={`font-bold ${e.type==='income'?'text-emerald-600':'text-red-600'}`}>{e.type==='income'?'+': '-'}₹{e.amount.toLocaleString('en-IN')}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
