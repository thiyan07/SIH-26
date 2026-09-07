import { useEffect, useState } from 'react'

type Notif = { id: string; title: string; body: string; time: string; read: boolean; type: 'price'|'scheme'|'weather'|'loan' }

const SEED: Notif[] = [
  { id: '1', title: 'Tomato price up 12%', body: 'Perundurai mandi — consider selling this week', time: '2h ago', read: false, type: 'price' },
  { id: '2', title: 'PM Mudra scheme deadline', body: 'Apply before 30 Sep for 2026 cycle', time: '1d ago', read: false, type: 'scheme' },
  { id: '3', title: 'Rain expected Thu-Fri', body: '1-2mm in Erode — cover stock', time: '3h ago', read: true, type: 'weather' },
  { id: '4', title: 'EMI due in 3 days', body: 'Your simulated loan EMI ₹5,069 due', time: '5h ago', read: false, type: 'loan' },
]

function load(): Notif[] {
  try { const raw = localStorage.getItem('grambiz.notifs'); if (raw) return JSON.parse(raw); } catch {}
  return SEED
}

export function NotificationsCenter() {
  const [notifs, setNotifs] = useState<Notif[]>(load)
  const [open, setOpen] = useState(false)
  const unread = notifs.filter(n=>!n.read).length
  useEffect(()=>{ localStorage.setItem('grambiz.notifs', JSON.stringify(notifs)) }, [notifs])
  const markRead = (id: string) => setNotifs(prev=> prev.map(n=> n.id===id ? { ...n, read: true } : n))
  const markAll = () => setNotifs(prev=> prev.map(n=> ({ ...n, read: true })))
  return (
    <div className="relative" data-testid="notifications-center">
      <button
        data-testid="notif-bell"
        onClick={()=>setOpen(v=>!v)}
        className="relative rounded-xl border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
        aria-label="Notifications"
      >
        🔔
        {unread>0 && <span data-testid="notif-badge" className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">{unread}</span>}
      </button>
      {open && (
        <div data-testid="notif-dropdown" className="absolute right-0 top-10 z-40 w-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center justify-between border-b p-3 dark:border-slate-700">
            <div className="text-sm font-bold text-slate-900 dark:text-white">Notifications</div>
            <button data-testid="notif-mark-all" onClick={markAll} className="text-xs font-semibold text-brand-600 hover:underline">Mark all read</button>
          </div>
          <div className="max-h-80 overflow-auto">
            {notifs.map(n=>(
              <div key={n.id} data-testid="notif-item" className={`flex gap-3 p-3 hover:bg-slate-50 dark:hover:bg-slate-800 ${!n.read ? 'bg-brand-50/50 dark:bg-brand-950/20' : ''}`}>
                <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs ${n.type==='price'?'bg-amber-100 text-amber-700':n.type==='scheme'?'bg-blue-100 text-blue-700':n.type==='weather'?'bg-cyan-100 text-cyan-700':'bg-emerald-100 text-emerald-700'}`}>{n.type==='price'?'₹':n.type==='scheme'?'🏛️':n.type==='weather'?'🌧️':'💳'}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1">
                    <span className="text-xs font-semibold text-slate-900 dark:text-white">{n.title}</span>
                    {!n.read && <span className="h-1.5 w-1.5 rounded-full bg-brand-600"></span>}
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-300">{n.body}</div>
                  <div className="text-[11px] text-slate-500">{n.time}</div>
                </div>
                {!n.read && <button data-testid={`notif-read-${n.id}`} onClick={()=>markRead(n.id)} className="self-center rounded-lg bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-200">Read</button>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
