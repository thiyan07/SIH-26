import { useAnalysis } from '../lib/analysisStore'
import { tr, interpolate } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Card, CardHeader } from '../components/ui'
import { Map, MapMarker } from '../mapcn'
import { Marker, Polygon, useMapEvents } from 'react-leaflet'

function PolygonEditor({ points, setPoints }: { points: [number, number][], setPoints: (p: [number, number][]) => void }) {
  useMapEvents({
    click(e) {
      if (points.length < 4) setPoints([...points, [e.latlng.lng, e.latlng.lat]])
    },
  })
  return (
    <>
      {points.length >= 3 && <Polygon positions={points.map(([lng, lat]) => [lat, lng] as [number, number])} pathOptions={{ color: '#0d9488', weight: 2, fillOpacity: 0.15 }} />}
      {points.map(([lng, lat], i) => (
        <Marker
          key={i}
          position={[lat, lng]}
          draggable
          eventHandlers={{
            dragend: (e: any) => {
              const { lat: nlat, lng: nlng } = e.target.getLatLng()
              const next = [...points]
              next[i] = [nlng, nlat]
              setPoints(next)
            },
          }}
        />
      ))}
    </>
  )
}

export function BusinessProfilePage() {
  const { lang } = useAnalysis()
  const { id } = useParams()
  const [business, setBusiness] = useState<any>(null)
  const [profile, setProfile] = useState<any>(null)
  const [type, setType] = useState<'agriculture' | 'textile' | 'restaurant' | 'other'>('agriculture')
  const [landSize, setLandSize] = useState<string>('')
  const [landUnit, setLandUnit] = useState('acres')
  const [declaredArea, setDeclaredArea] = useState<string>('')
  const [polygon, setPolygon] = useState<[number, number][]>([])
  const [waterSource, setWaterSource] = useState('')
  const [crop, setCrop] = useState('')
  const [season, setSeason] = useState('')
  const [profileData, setProfileData] = useState<string>('{}')
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api.get(`/user/businesses/${id}`).then(setBusiness).catch(() => {})
    api.get(`/user/business-profiles/${id}`).then(setProfile).catch(() => {})
  }, [id])

  const handleSave = async () => {
    setError(null); setMsg(null)
    try {
      let data: any = undefined
      try { data = profileData ? JSON.parse(profileData) : null } catch { throw new Error('Profile data must be valid JSON') }
      const body: any = {
        business_id: id,
        business_type: type,
        land_size: landSize ? Number(landSize) : undefined,
        land_unit: landUnit,
        land_polygon: polygon.length >= 3 ? polygon : undefined,
        declared_area: declaredArea ? Number(declaredArea) : undefined,
        water_source: waterSource || undefined,
        crop: crop || undefined,
        season: season || undefined,
        profile_data: data,
      }
      const res: any = await api.post('/user/business-profiles', body)
      setProfile(res)
      setMsg(`Saved — calculated area ${res.calculated_area ? (res.calculated_area/4046.86).toFixed(2) + ' acres' : '—'} ${res.area_discrepancy_pct != null ? `· discrepancy ${res.area_discrepancy_pct}%` : ''}`)
    } catch (e: any) { setError(e.message) }
  }

  if (!id) return null
  const center = business ? { latitude: business.latitude, longitude: business.longitude } : { latitude: 11.34, longitude: 77.71 }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={tr('bpTitle', lang)} subtitle={business ? `${business.name} · ${business.category_code}` : tr('bpSubtitle', lang)} />
        {profile && (
          <div className="rounded-lg bg-green-50 p-3 text-xs text-green-800">{tr('bpExisting', lang)} {profile.business_type} {profile.calculated_area ? `· ${ (profile.calculated_area/4046.86).toFixed(2)} acres calculated` : ''} {profile.area_discrepancy_pct != null ? `· ${profile.area_discrepancy_pct}% discrepancy` : ''}</div>
        )}
      </Card>

      <Card>
        <CardHeader title={tr('bpTypeTitle', lang)} subtitle={tr('bpTypeSubtitle', lang)} />
        <div className="grid gap-2 sm:grid-cols-3">
          {(['agriculture','textile','restaurant'] as const).map(t => (
            <button key={t} onClick={() => setType(t)} className={`rounded-xl border p-4 text-left ${type===t ? 'border-brand-600 bg-brand-50' : 'border-slate-200 bg-white'}`}>
              <div className="font-semibold capitalize">{t}</div><div className="text-xs text-gray-500">{t==='agriculture'?'Land, water, soil, crop':'Textile: capacity & raw · Restaurant: location & gaps'}</div>
            </button>
          ))}
        </div>
      </Card>

      {type === 'agriculture' && (
        <Card>
          <CardHeader title={tr('bpLandWaterTitle', lang)} subtitle={tr('bpLandWaterSub', lang)} />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs font-semibold">{tr('bpDeclaredSize', lang)}</label><input value={landSize} onChange={e=>setLandSize(e.target.value)} placeholder="e.g. 2.5" className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></div>
                <div><label className="text-xs font-semibold">{tr('bpUnit', lang)}</label><select value={landUnit} onChange={e=>setLandUnit(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"><option value="acres">acres</option><option value="hectares">hectares</option><option value="sqm">sqm</option></select></div>
              </div>
              <div><label className="text-xs font-semibold">{tr('bpDeclaredArea', lang)}</label><input value={declaredArea} onChange={e=>setDeclaredArea(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" placeholder={tr('bpDeclaredAreaPh', lang)} /></div>
              <div><label className="text-xs font-semibold">{tr('bpWaterSource', lang)}</label><select value={waterSource} onChange={e=>setWaterSource(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"><option value="">{tr('bpWaterSelect', lang)}</option><option value="well">Well</option><option value="borewell">Borewell</option><option value="canal">Canal</option><option value="rainfed">Rainfed</option></select></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs font-semibold">{tr('bpCrop', lang)}</label><input value={crop} onChange={e=>setCrop(e.target.value)} placeholder={tr('bpCropPh', lang)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" /></div>
                <div><label className="text-xs font-semibold">{tr('bpSeason', lang)}</label><select value={season} onChange={e=>setSeason(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"><option value="">—</option><option value="kharif">Kharif</option><option value="rabi">Rabi</option><option value="zaid">Zaid</option></select></div>
              </div>
              <div className="text-xs text-gray-500">{interpolate(tr('bpPoints', lang), {count: polygon.length})} {polygon.length>=3 ? '· '+tr('bpPolygonReady', lang) : '· '+tr('bpNeedMore', lang) } <button onClick={()=>setPolygon([])} className="ml-2 underline">{tr('bpClear', lang)}</button></div>
              {profile?.calculated_area && <div className="text-xs">{tr('bpCalculated', lang)} {(profile.calculated_area/4046.86).toFixed(3)} acres · {profile.calculated_area.toFixed(0)} sqm</div>}
            </div>
            <div style={{ height: 360, borderRadius: 12, overflow: 'hidden' }}>
              <Map latitude={center.latitude} longitude={center.longitude} zoom={16}>
                <MapMarker latitude={center.latitude} longitude={center.longitude} color="#111827" label="Business location" />
                <PolygonEditor points={polygon} setPoints={setPolygon} />
              </Map>
            </div>
          </div>
        </Card>
      )}

      {type !== 'agriculture' && (
        <Card>
          <CardHeader title={interpolate(tr('bpBusinessDetails', lang), {type})} subtitle={tr('bpBusinessDetailsSub', lang)} />
          <textarea value={profileData} onChange={e=>setProfileData(e.target.value)} rows={6} className="w-full rounded-lg border px-3 py-2 font-mono text-xs" placeholder='{"production_capacity": 100, "current_production": 60, "selling_price": 250, "raw_material_cost": 120}' />
          <p className="mt-2 text-xs text-gray-500">{tr('bpJsonHint', lang)}</p>
        </Card>
      )}

      <div className="flex gap-3">
        <button onClick={handleSave} className="rounded-xl bg-brand-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-brand-700">{tr('bpSave', lang)}</button>
        <Link to="/post-loan" className="rounded-xl border border-slate-200 bg-white px-6 py-2.5 text-sm font-bold">{tr('bpBack', lang)}</Link>
      </div>
      {msg && <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{msg}</div>}
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <p className="text-xs text-gray-500">{tr('bpNote', lang)}</p>
    </div>
  )
}
