import { useState } from 'react'
import { Card, CardHeader } from '../components/ui'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'

type Story = { id: number; name: string; village: string; district: string; business: string; story: string; profit: string; likes: number; verified?: boolean }

const STORIES: Story[] = [
  { id: 1, name: 'Lakshmi', village: 'Perundurai', district: 'Erode', business: 'Dairy', story: 'Started with 2 cows, now 8. GramBiz showed low competition in my block — GO signal gave me confidence to take loan.', profit: '₹34k/mo', likes: 128, verified: true },
  { id: 2, name: 'Ramesh', village: 'Bhavani', district: 'Erode', business: 'Grocery', story: 'Used map to find gap — no grocery within 3km. Daily sales ₹4.5k in 2nd month.', profit: '₹28k/mo', likes: 96 },
  { id: 3, name: 'Priya', village: 'Gobichettipalayam', district: 'Erode', business: 'Tailoring', story: 'Seasonal demand tip saved me — stocked before Pongal peak, sold out in 10 days.', profit: '₹22k/mo', likes: 84 },
  { id: 4, name: 'Suresh', village: 'Anthiyur', district: 'Erode', business: 'Pharmacy', story: 'Health facility gap meant no pharmacy nearby. Repayment health was AMBER but manageable.', profit: '₹41k/mo', likes: 112, verified: true },
  { id: 5, name: 'Anita', village: 'Chennimalai', district: 'Erode', business: 'Bakery', story: 'Advisory parsed my Tamil voice note perfectly and filled Erode location automatically.', profit: '₹18k/mo', likes: 67 },
  { id: 6, name: 'Kumar', village: 'Sathyamangalam', district: 'Erode', business: 'Fertilizer', story: 'Linked with 12 farmers via community — bulk purchase saved 18% on inputs.', profit: '₹31k/mo', likes: 54 },
]

export function Community() {
  const { lang } = useAnalysis()
  const [filter, setFilter] = useState('All')
  const [liked, setLiked] = useState<Set<number>>(new Set())
  const [stories, setStories] = useState(STORIES)
  const filtered = filter==='All' ? stories : stories.filter(s=>s.business===filter)
  const toggleLike = (id: number)=>{
    const isLiked = liked.has(id)
    setLiked(prev=>{
      const next = new Set(prev)
      if (isLiked) next.delete(id); else next.add(id)
      return next
    })
    setStories(prev=> prev.map(s=> s.id===id ? { ...s, likes: s.likes + (isLiked ? -1 : 1) } : s))
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{tr('communityTitle', lang as any)}</h1>
        <p className="text-sm text-slate-500">{tr('communityDesc', lang as any)}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {['All','Dairy','Grocery','Tailoring','Pharmacy','Bakery','Fertilizer'].map(b=>(
          <button
            key={b}
            data-testid={`filter-${b}`}
            onClick={()=>setFilter(b)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold ${filter===b ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'}`}
          >
            {b}
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map(s=>(
          <Card key={s.id} data-testid="story-card" className="p-4 hover:shadow-md transition-shadow">
            <CardHeader title={`${s.name} • ${s.business}`} subtitle={`${s.village}, ${s.district}`} action={s.verified ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 ring-1 ring-emerald-200">✓ Verified</span> : null} />
            <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">“{s.story}”</p>
            <div className="mt-3 flex items-center justify-between">
              <span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-bold text-brand-700 dark:bg-brand-950/40 dark:text-brand-300">{s.profit}</span>
              <button
                data-testid={`like-${s.id}`}
                onClick={()=>toggleLike(s.id)}
                className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${liked.has(s.id) ? 'bg-red-50 text-red-600 ring-1 ring-red-200' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}`}
              >
                {liked.has(s.id) ? '❤️' : '🤍'} {s.likes}
              </button>
            </div>
            <div className="mt-2 flex gap-2">
              <button className="text-xs text-brand-600 hover:underline dark:text-brand-400">Ask mentor →</button>
              <button className="text-xs text-slate-500" onClick={()=>{
                navigator.clipboard.writeText(`${s.name} in ${s.village}: ${s.story}`)
                alert('Copied to clipboard')
              }}>Share</button>
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-4">
        <CardHeader title="Share your journey" subtitle="Inspire others — 2 lines is enough" />
        <button
          data-testid="share-story"
          onClick={()=>{
            const name = prompt('Your name?') || 'Anonymous'
            const story = prompt('One line about your business?')
            if (story) setStories(prev=>[{ id: Date.now(), name, village: 'Your village', district: 'Erode', business: 'Grocery', story, profit: '—', likes: 0 }, ...prev])
          }}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white hover:bg-slate-800"
        >
          + Share story
        </button>
      </Card>
    </div>
  )
}
