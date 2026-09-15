import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Card, CardHeader } from '../components/ui'
import { useAnalysis } from '../lib/analysisStore'
import { tr, interpolate, type Language } from '../lib/i18n'

type Video = {
  title: string
  titleTa: string
  titleHi: string
  url: string
  lang: Language
  desc: string
  descTa: string
  descHi: string
  category: 'dairy' | 'retail' | 'loan' | 'farming'
  duration: string
}

// Real, relevant YouTube embeds (verified 2025-26). No rick-roll.
const VIDEOS: Video[] = [
  {
    title: 'How to Start a Dairy Farm — Complete Guide (Tamil)',
    titleTa: 'பால் பண்ணை தொடங்குவது எப்படி — முழு வழிகாட்டி',
    titleHi: 'डेयरी फार्म कैसे शुरू करें — पूरी गाइड (तमिल)',
    url: 'https://www.youtube.com/embed/ULEBWjuIKn8',
    lang: 'ta',
    desc: '2 cows to 20: shed, breed, feed & profit — Erode farmer walkthrough',
    descTa: '2 மாடுகளில் இருந்து 20 வரை — கொட்டகை, இனம், தீவனம் & லாபம்',
    descHi: '2 से 20 गाय — शेड, नस्ल, चारा और मुनाफा',
    category: 'dairy',
    duration: '18:42',
  },
  {
    title: 'Successful Dairy Farming — Farmer Experience (Tamil)',
    titleTa: 'வெற்றிகரமான பால் பண்ணை — விவசாயி அனுபவம்',
    titleHi: 'सफल डेयरी फार्मिंग — किसान अनुभव (तमिल)',
    url: 'https://www.youtube.com/embed/LOxAbSPZ9Pc',
    lang: 'ta',
    desc: 'Cow selection, feed management & daily routine from a Tamil Nadu farmer',
    descTa: 'மாடு தேர்வு, தீவன மேலாண்மை & தினசரி வழக்கம்',
    descHi: 'गाय चयन, चारा प्रबंधन और दिनचर्या',
    category: 'dairy',
    duration: '22:18',
  },
  {
    title: 'Grocery / Kirana Shop in Village — Plan & Inventory (Hindi)',
    titleTa: 'கிராமத்தில் மளிகைக் கடை — திட்டம் & சரக்கு',
    titleHi: 'गाँव में किराना दुकान — योजना और स्टॉक',
    url: 'https://www.youtube.com/embed/JuqYcDguWzk',
    lang: 'hi',
    desc: 'How to open a kirana store in India — with Garima Saini',
    descTa: 'இந்தியாவில் மளிகைக் கடை திறப்பது எப்படி — இந்தியில்',
    descHi: 'भारत में किराना स्टोर कैसे खोलें — हिंदी में',
    category: 'retail',
    duration: '14:05',
  },
  {
    title: 'Supermarket / Grocery Business in Village (Hindi)',
    titleTa: 'கிராமத்தில் சூப்பர்மார்க்கெட் வணிகம்',
    titleHi: 'गाँव में सुपरमार्केट बिज़नेस',
    url: 'https://www.youtube.com/embed/IC5HWqIXvOg',
    lang: 'hi',
    desc: 'Small town supermarket possibilities, POS & credit control',
    descTa: 'சிறு நகர சூப்பர்மார்க்கெட் வாய்ப்புகள்',
    descHi: 'छोटे शहर में सुपरमार्केट संभावनाएँ',
    category: 'retail',
    duration: '12:33',
  },
  {
    title: 'How to Apply for a Mudra Loan — Step-by-Step Guide',
    titleTa: 'முத்ரா கடன் விண்ணப்பிப்பது எப்படி — படிப்படியாக',
    titleHi: 'मुद्रा लोन कैसे अप्लाई करें — स्टेप-बाय-स्टेप',
    url: 'https://www.youtube.com/embed/sgTGrKPmsOQ',
    lang: 'en',
    desc: 'Eligibility, documents, Udyamimitra & branch process',
    descTa: 'தகுதி, ஆவணங்கள், உத்யமிமித்ரா & கிளை செயல்முறை',
    descHi: 'पात्रता, दस्तावेज़, उद्यमिमित्र और ब्रांच प्रक्रिया',
    category: 'loan',
    duration: '9:47',
  },
  {
    title: 'Mudra Loan क्या है? Online Apply कैसे करें (Hindi)',
    titleTa: 'முத்ரா கடன் என்றால் என்ன? ஆன்லைனில் விண்ணப்பிப்பது எப்படி',
    titleHi: 'मुद्रा लोन क्या है? ऑनलाइन अप्लाई कैसे करें',
    url: 'https://www.youtube.com/embed/fWOyvC6-E5Y',
    lang: 'hi',
    desc: 'PM Mudra Yojana explained — Shishu / Kishor / Tarun',
    descTa: 'PM முத்ரா திட்டம் விளக்கம் — சிஷு / கிஷோர் / தருண்',
    descHi: 'PM मुद्रा योजना — शिशु / किशोर / तरुण',
    category: 'loan',
    duration: '11:22',
  },
]

const CAT_LABEL: Record<string, { en: string; ta: string; hi: string }> = {
  all: { en: 'All', ta: 'அனைத்தும்', hi: 'सभी' },
  dairy: { en: 'Dairy', ta: 'பால்', hi: 'डेयरी' },
  retail: { en: 'Retail', ta: 'சில்லறை', hi: 'रिटेल' },
  loan: { en: 'Loan', ta: 'கடன்', hi: 'ऋण' },
}

function labelFor(v: Video, lang: Language) {
  if (lang === 'ta') return v.titleTa
  if (lang === 'hi') return v.titleHi
  return v.title
}
function descFor(v: Video, lang: Language) {
  if (lang === 'ta') return v.descTa
  if (lang === 'hi') return v.descHi
  return v.desc
}

export function VideoTutorials() {
  const { lang } = useAnalysis()
  const [filter, setFilter] = useState<'all' | Video['category']>('all')
  const shown = filter === 'all' ? VIDEOS : VIDEOS.filter(v => v.category === filter)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={tr('videoEyebrowTr', lang)}
        title={tr('videoTitleTr', lang)}
        desc={tr('videoDescTr', lang)}
      />

      {/* Filter pills — beautiful */}
      <div className="flex flex-wrap items-center gap-2">
        {(['all', 'dairy', 'retail', 'loan'] as const).map(c => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={`rounded-full px-4 py-1.5 text-xs font-semibold ring-1 transition ${
              filter === c
                ? 'bg-slate-900 text-white ring-slate-900 shadow'
                : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
            }`}
          >
            {CAT_LABEL[c][lang]}
          </button>
        ))}
        <span className="ml-1 text-xs text-slate-500">
          {interpolate(tr('videoCount', lang), { count: shown.length })}
        </span>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {shown.map(v => (
          <Card key={v.title} className="group overflow-hidden p-0 shadow-sm transition hover:shadow-lg hover:-translate-y-0.5">
            <div className="relative aspect-video overflow-hidden bg-slate-900">
              <iframe
                src={v.url}
                title={labelFor(v, lang)}
                className="h-full w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                loading="lazy"
                referrerPolicy="strict-origin-when-cross-origin"
              />
              <div className="pointer-events-none absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {v.duration}
              </div>
            </div>
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="text-sm font-bold leading-snug text-slate-900 group-hover:text-teal-700">
                  {labelFor(v, lang)}
                </div>
                <span className="shrink-0 rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white">
                  {v.lang}
                </span>
              </div>
              <div className="mt-1 text-xs leading-relaxed text-slate-500">{descFor(v, lang)}</div>
              <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-teal-50 px-2 py-0.5 text-[10px] font-semibold text-teal-700 ring-1 ring-teal-200">
                {CAT_LABEL[v.category]?.[lang] ?? v.category} • YouTube
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="border-teal-100 bg-gradient-to-br from-teal-50 via-white to-cyan-50/50">
        <CardHeader
          title={tr('videoRequestTitle', lang)}
          subtitle={tr('videoRequestSub', lang)}
        />
        <p className="text-sm leading-relaxed text-slate-600">
          {tr('videoRequestBody', lang)}
        </p>
      </Card>
    </div>
  )
}
