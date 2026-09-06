import { PageHeader } from '../components/PageHeader'
import { Card, CardHeader } from '../components/ui'

const VIDEOS = [
  { title: 'How to start a dairy farm (Tamil)', url: 'https://www.youtube.com/embed/dQw4w9WgXcQ', lang: 'ta', desc: 'Step-by-step for 2 cows, shed, feed' },
  { title: 'Grocery shop setup in village', url: 'https://www.youtube.com/embed/dQw4w9WgXcQ', lang: 'hi', desc: 'Inventory + POS + credit control' },
  { title: 'MUDRA loan application guide', url: 'https://www.youtube.com/embed/dQw4w9WgXcQ', lang: 'en', desc: 'Documents + DIC visit' },
]

export function VideoTutorials() {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Client • Learn" title="Video Tutorials" desc="As a first-time entrepreneur you want to see it done — not just read. Tamil, Hindi, English." />
      <div className="grid gap-4 md:grid-cols-2">
        {VIDEOS.map(v=>(
          <Card key={v.title} className="overflow-hidden p-0">
            <div className="aspect-video bg-slate-900">
              <iframe src={v.url} title={v.title} className="h-full w-full" allowFullScreen />
            </div>
            <div className="p-4">
              <div className="text-sm font-bold text-slate-900">{v.title} <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs">{v.lang}</span></div>
              <div className="text-xs text-slate-500">{v.desc}</div>
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Request a video" subtitle="Tell us what you need — we will add it" />
        <p className="text-sm text-slate-600">Need a video on poultry disease or FSSAI license? Use the feedback button (bottom-right) to request. As client, your request drives the next video.</p>
      </Card>
    </div>
  )
}
