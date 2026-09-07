import { useEffect, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'

interface Profile {
  name: string
  streak: number
  analyses: number
  badges: string[]
  level: number
}

function loadProfile(): Profile {
  try {
    const raw = localStorage.getItem('grambiz.profile')
    if (raw) return JSON.parse(raw)
  } catch {}
  return { name: 'Entrepreneur', streak: 3, analyses: 0, badges: ['🌱 Starter'], level: 1 }
}

function saveProfile(p: Profile) {
  localStorage.setItem('grambiz.profile', JSON.stringify(p))
}

export function useGamification() {
  const [profile, setProfile] = useState<Profile>(loadProfile)
  const { result } = useAnalysis()
  useEffect(()=>{
    if (result) {
      setProfile(prev=>{
        const next = { ...prev, analyses: prev.analyses + 1 }
        if (next.analyses >= 1 && !next.badges.includes('📊 First Analysis')) next.badges.push('📊 First Analysis')
        if (next.analyses >= 5 && !next.badges.includes('🔥 Explorer')) next.badges.push('🔥 Explorer')
        if ((result.opportunity_score?.overall_score ?? 0) >= 65 && !next.badges.includes('✅ GO Getter')) next.badges.push('✅ GO Getter')
        next.level = Math.min(5, Math.floor(next.analyses/2)+1)
        // streak logic: increment if last visit was yesterday (simplified: always increment on new analysis)
        next.streak = Math.min(30, prev.streak + 1)
        saveProfile(next)
        return next
      })
    }
  }, [result?.opportunity_score?.overall_score])
  return { profile, setProfile }
}

export function GamificationCard() {
  const { profile } = useGamification()
  return (
    <div data-testid="gamification-card" className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 p-4 dark:border-amber-900 dark:from-amber-950/30 dark:to-orange-950/20">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-amber-700 dark:text-amber-300">Your Progress • Lv {profile.level}</div>
          <div className="mt-1 text-sm font-bold text-slate-900 dark:text-white">{profile.name} • 🔥 {profile.streak} day streak</div>
          <div className="text-xs text-slate-600 dark:text-slate-300">{profile.analyses} analyses completed</div>
        </div>
        <div className="text-2xl">🏆</div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {profile.badges.map(b=>(
          <span key={b} className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-amber-700 shadow-sm ring-1 ring-amber-200 dark:bg-slate-800 dark:text-amber-200">{b}</span>
        ))}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white dark:bg-slate-700">
        <div className="h-2 bg-gradient-to-r from-amber-500 to-orange-500" style={{ width: `${Math.min(100, profile.analyses*20)}%` }} />
      </div>
      <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">Complete 5 analyses to unlock Explorer badge</p>
    </div>
  )
}

export function ProfileEditor() {
  const { profile, setProfile } = useGamification()
  const [name, setName] = useState(profile.name)
  return (
    <div data-testid="profile-editor" className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
      <input data-testid="profile-name-input" value={name} onChange={e=>setName(e.target.value)} placeholder="Your name" className="flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white" />
      <button
        data-testid="profile-save"
        onClick={()=>{
          const next = { ...profile, name: name || 'Entrepreneur' }
          setProfile(next)
          saveProfile(next)
        }}
        className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-bold text-white"
      >
        Save
      </button>
    </div>
  )
}
